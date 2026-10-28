"""
Policy engine and request validator for Windows Automation.

Enforces:
1. Dynamic catalogue allowlisting & strict target validation.
2. Rejection of arbitrary executable paths, shell scripts, batch files, command chaining.
3. Verification of security authorization decisions (denials, missing approvals, invalid states).
"""

from typing import Tuple, Optional, Set, List
import os
from windows_automation.schemas import ActionRequest, AuthorizationDecision, ApplicationRecord
from windows_automation.catalogue import ApplicationCatalogue


class WindowsActionPolicy:
    """Validates incoming action requests against security policies and application allowlists."""

    # Explicit allowlist of supported actions
    SUPPORTED_ACTIONS: Set[str] = {"open_application"}

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
        self.catalogue = catalogue

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

        # Disallow arbitrary directory traversals unless matching resolved catalogue record
        if ("../" in lower_target or "..\\" in lower_target):
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

        # Target verification against Catalogue or Builtin
        if request.resolved_record:
            # Check the resolved record target
            record = request.resolved_record
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
        Never invents approvals. Missing, denied, or invalid permissions prevent execution.
        Returns: (is_authorized, error_code, error_message)
        """
        auth = request.authorization
        if auth is None:
            return (
                False,
                "ERR_PERMISSION_DENIED",
                "No authorization decision provided with action request.",
            )

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
        """Resolve validated target to its verified Windows executable path."""
        if request and request.resolved_record:
            return request.resolved_record.executable_path

        if self.catalogue:
            resolution = self.catalogue.resolve(target)
            if resolution.status == "resolved" and resolution.matched_record:
                return resolution.matched_record.executable_path

        clean_lower = target.strip().lower()
        if clean_lower in ["notepad", "notepad.exe", r"c:\windows\system32\notepad.exe"]:
            candidate = r"C:\Windows\System32\notepad.exe"
            return candidate if os.path.exists(candidate) else "notepad.exe"

        return None
