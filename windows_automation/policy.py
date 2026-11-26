"""
Policy engine and request validator for Windows Automation.

Enforces:
1. Dynamic catalogue allowlisting & strict target validation.
2. Rejection of arbitrary shell commands, scripts (.bat, .cmd, .ps1, .vbs), directory traversal.
3. Permitted normal launches without requiring unnecessary user approvals.
4. Preserved authorization checks for sensitive operations and policy denials.
"""

from typing import Tuple, Optional, Set, List, Any
import os
from windows_automation.schemas import ActionRequest, AuthorizationDecision, ApplicationRecord
from windows_automation.catalogue import ApplicationCatalogue


class WindowsActionPolicy:
    """Validates incoming action requests against security policies and application allowlists."""

    SUPPORTED_ACTIONS: Set[str] = {
        "open_application",
        "search_web_app",
        "navigate_url",
        "type_text",
        "clipboard_copy",
        "clipboard_paste",
        "press_hotkey",
        "click_element",
        "click_youtube_result",
        "wait",
        "prompt_ai_chat",
        "open_website",
        "search",
        "play_video",
        "ask_prompt",
    }

    # Forbidden shell execution tokens / dangerous argument patterns
    FORBIDDEN_SUBSTRINGS = {
        "cmd.exe",
        "powershell",
        "bash",
        "sh",
        "curl",
        "wget",
        "rmdir",
        "del",
        "reg",
        "format",
        ";",
        "&",
        "|",
        ">",
        "<",
        "`",
        "$",
    }

    # Prohibited executable extensions
    DISALLOWED_EXTENSIONS = {
        ".bat",
        ".cmd",
        ".ps1",
        ".vbs",
        ".vbe",
        ".js",
        ".jse",
        ".wsf",
        ".wsh",
        ".msc",
        ".reg",
        ".cpl",
        ".scr",
    }

    def __init__(self, catalogue: Optional[ApplicationCatalogue] = None):
        self.catalogue = catalogue or ApplicationCatalogue()

    @property
    def ALLOWLISTED_APPLICATIONS(self) -> Set[str]:
        if not self.catalogue:
            return set()
        return {r.app_id for r in self.catalogue.get_all()}

    def register_application(
        self,
        app_id: str,
        canonical_name: str,
        executable_name: Optional[str] = None,
        known_paths: Optional[List[str]] = None,
        **kwargs
    ) -> None:
        if not self.catalogue:
            self.catalogue = ApplicationCatalogue()
        exe = (known_paths and known_paths[0]) or executable_name or f"{app_id}.exe"
        record = ApplicationRecord(
            app_id=app_id,
            display_name=canonical_name,
            normalized_name=canonical_name.strip().lower(),
            executable_path=exe,
            source="system_builtin",
            aliases=[canonical_name.lower(), app_id.lower()],
        )
        self.catalogue.register(record)

    def load_catalogue_entries(self, entries: Optional[List[Any]] = None) -> None:
        """Loads and registers catalogue entries for testing or runtime discovery."""
        if not self.catalogue:
            self.catalogue = ApplicationCatalogue()
        if entries:
            for entry in entries:
                if isinstance(entry, ApplicationRecord):
                    self.catalogue.register(entry)
                elif isinstance(entry, dict):
                    self.catalogue.register(ApplicationRecord.from_dict(entry))

    def validate_request(self, request: ActionRequest) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validate request structure, action name, parameters, and target against safe catalogue.
        Returns: (is_valid, error_code, error_message)
        """
        if not request.action_id or not request.task_id:
            return False, "ERR_INVALID_REQUEST", "Missing action_id or task_id."

        if not request.action_name:
            return False, "ERR_INVALID_REQUEST", "Missing action_name in request."

        if request.action_name not in self.SUPPORTED_ACTIONS:
            return (
                False,
                "ERR_UNSUPPORTED_ACTION",
                f"Action '{request.action_name}' is not supported. Supported actions: {list(self.SUPPORTED_ACTIONS)}",
            )

        if not request.target or not request.target.strip():
            if request.action_name in {"clipboard_copy", "wait", "type_text", "press_hotkey", "clipboard_paste", "click_youtube_result", "prompt_ai_chat", "open_website", "search", "play_video", "ask_prompt"}:
                request.target = "active_window"
            else:
                return False, "ERR_INVALID_REQUEST", "Target cannot be empty."

        clean_target = request.target.strip()
        lower_target = clean_target.lower()

        # Reject dangerous shell command strings or argument piping
        for forbidden in self.FORBIDDEN_SUBSTRINGS:
            if forbidden in lower_target:
                return (
                    False,
                    "ERR_TARGET_NOT_ALLOWLISTED",
                    f"Target contains forbidden shell command token: '{forbidden}'. Arbitrary shell commands are prohibited.",
                )

        # Check for disallowed script extensions
        ext = os.path.splitext(clean_target)[1].lower()
        if ext in self.DISALLOWED_EXTENSIONS:
            return (
                False,
                "ERR_TARGET_NOT_ALLOWLISTED",
                f"Executable extension '{ext}' is prohibited for security reasons.",
            )

        # Disallow arbitrary directory traversals
        if "../" in lower_target or "..\\" in lower_target:
            return (
                False,
                "ERR_TARGET_NOT_ALLOWLISTED",
                "Directory traversal in application target is strictly prohibited.",
            )

        # Check parameters
        params = request.parameters or {}
        args = params.get("args", [])
        if not isinstance(args, list):
            return False, "ERR_INVALID_REQUEST", "Parameters 'args' must be a list."

        for arg in args:
            arg_str = str(arg).lower()
            if any(bad in arg_str for bad in self.FORBIDDEN_SUBSTRINGS):
                return (
                    False,
                    "ERR_INVALID_REQUEST",
                    f"Parameter contains prohibited shell command characters or tokens: '{arg}'",
                )

        # GUI, clipboard, and web actions do not require local executable files in catalogue
        if request.action_name in {
            "search_web_app",
            "navigate_url",
            "type_text",
            "clipboard_copy",
            "clipboard_paste",
            "press_hotkey",
            "click_element",
            "click_youtube_result",
            "wait",
            "prompt_ai_chat",
            "open_website",
            "search",
            "play_video",
            "ask_prompt",
        }:
            return True, None, None

        # Target verification against resolved record or Catalogue
        if request.resolved_record:
            record = request.resolved_record
            if record.app_type == "shortcut" and record.shortcut_path:
                if not os.path.exists(record.shortcut_path):
                    return False, "ERR_TARGET_UNAVAILABLE", f"Shortcut file missing: '{record.shortcut_path}'"
                return True, None, None

            if record.launch_method in ["appx_packaged", "shell_apps_folder"] or record.app_type == "packaged_app":
                target_id = record.app_user_model_id or record.executable_path
                if not target_id:
                    return False, "ERR_TARGET_UNAVAILABLE", f"Packaged application '{record.display_name}' has no AppID or AUMID."
                # Verify safe characters in AppID (alphanumerics, dots, underscores, dashes, exclamation, curly braces, colons, slashes)
                if any(c in target_id for c in self.FORBIDDEN_SUBSTRINGS):
                    return False, "ERR_TARGET_NOT_ALLOWLISTED", f"Packaged app target '{target_id}' contains unsafe characters."
                return True, None, None

            if not record.executable_path:
                return False, "ERR_TARGET_UNAVAILABLE", f"Application '{record.display_name}' has no executable path."
            record_ext = os.path.splitext(record.executable_path)[1].lower()
            if record_ext and record_ext not in [".exe"]:
                return (
                    False,
                    "ERR_TARGET_NOT_ALLOWLISTED",
                    f"Resolved target '{record.executable_path}' does not have a safe executable extension (.exe).",
                )
            return True, None, None

        if self.catalogue:
            resolution = self.catalogue.resolve(clean_target)
            if resolution.status == "resolved" and resolution.matched_record:
                request.resolved_record = resolution.matched_record
                return True, None, None
            elif resolution.status == "ambiguous":
                cand_names = [c.display_name for c in resolution.candidates]
                return (
                    False,
                    "ERR_AMBIGUOUS_TARGET",
                    f"Target '{clean_target}' is ambiguous. Candidates: {cand_names}",
                )
            elif resolution.status == "unsupported":
                return (
                    False,
                    "ERR_TARGET_UNAVAILABLE",
                    resolution.reason or f"Target '{clean_target}' is unavailable or unsupported.",
                )

        # Fallback for explicit built-in Notepad
        if lower_target in ["notepad", "notepad.exe", r"c:\windows\system32\notepad.exe"]:
            return True, None, None

        # Check against AI Engine catalogue for web and hybrid apps
        try:
            from ai_engine.catalogue import get_installed_apps
            for app_meta in get_installed_apps():
                candidates = [app_meta["app_name"].lower(), app_meta["app_id"].lower(), *[a.lower() for a in app_meta.get("aliases", [])]]
                if lower_target in candidates:
                    return True, None, None
        except Exception:
            pass

        if self.catalogue:
            return (
                False,
                "ERR_TARGET_NOT_FOUND",
                f"Target '{clean_target}' was not found in the installed application catalogue.",
            )

        return (
            False,
            "ERR_TARGET_NOT_ALLOWLISTED",
            f"Target '{clean_target}' is not in the explicit application allowlist.",
        )

    def check_authorization(self, request: ActionRequest) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Check authorization decision.
        Under revised assignment rules, launching normal validated applications does not require approval.
        Preserves authorization checks for policy denials or missing approvals if explicitly flagged.
        Returns: (is_authorized, error_code, error_message)
        """
        auth = request.authorization
        if auth is None:
            # Default to granted for validated application launches if no security restriction specified
            return True, None, None

        if auth.permission_status == "denied":
            reason = auth.reason or "Security policy denied this action."
            return False, "ERR_PERMISSION_DENIED", f"Action authorization denied: {reason}"

        if auth.permission_status == "requires_approval":
            if not auth.approval_reference:
                return (
                    False,
                    "ERR_MISSING_APPROVAL",
                    "User approval is required for this action but no valid approval reference was provided.",
                )

        if auth.permission_status != "granted":
            return (
                False,
                "ERR_PERMISSION_DENIED",
                f"Invalid or ungranted permission status: '{auth.permission_status}'.",
            )

        if auth.requires_user_approval and not auth.approval_reference:
            return (
                False,
                "ERR_MISSING_APPROVAL",
                "Action requires explicit user approval reference before execution.",
            )

        return True, None, None

    def resolve_executable_path(self, target: str, request: Optional[ActionRequest] = None) -> Optional[str]:
        """Resolve validated target to its verified executable or shortcut path."""
        if request and request.resolved_record:
            rec = request.resolved_record
            if rec.app_type == "shortcut" and rec.shortcut_path:
                return rec.shortcut_path
            return rec.executable_path

        if self.catalogue:
            resolution = self.catalogue.resolve(target)
            if resolution.status == "resolved" and resolution.matched_record:
                rec = resolution.matched_record
                if rec.app_type == "shortcut" and rec.shortcut_path:
                    return rec.shortcut_path
                return rec.executable_path

        clean_lower = target.strip().lower()
        if clean_lower in ["notepad", "notepad.exe", r"c:\windows\system32\notepad.exe"]:
            candidate = r"C:\Windows\System32\notepad.exe"
            return candidate if os.path.exists(candidate) else "notepad.exe"

        if clean_lower in ["chrome", "chrome.exe", "google chrome"]:
            for cand in [
                r"C:\Program Files\Google\Chrome\Application\chrome.exe",
                r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            ]:
                if os.path.exists(cand):
                    return cand
            return "chrome.exe"

        return None
