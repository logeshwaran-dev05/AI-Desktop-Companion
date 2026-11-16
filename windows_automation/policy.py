"""
Policy engine and request validator for Windows Automation.

Enforces:
1. Strict explicit application allowlist (Notepad for Milestone 1).
2. Rejection of arbitrary executable paths, shell commands, scripts, piping.
3. Verification of security authorization decisions (denials, missing approvals, invalid states).
"""

from typing import Tuple, Optional, Set
import os
import shutil
from windows_automation.schemas import ActionRequest, AuthorizationDecision


class WindowsActionPolicy:
    """Validates incoming action requests against security policies and allowlists."""

    # Explicit allowlist of supported actions in Milestone 1
    SUPPORTED_ACTIONS: Set[str] = {"open_application"}

    # Explicit allowlist of permitted applications in Milestone 1
    ALLOWLISTED_APPLICATIONS = {
        "notepad": {
            "canonical_name": "Notepad",
            "executable_name": "notepad.exe",
            "known_paths": [
                r"C:\Windows\System32\notepad.exe",
                r"C:\Windows\notepad.exe",
                "notepad.exe",
            ],
            "requires_user_approval_by_default": False,
        }
    }

    def __init__(self):
        self._dynamic_applications = {}

    def register_application(self, app_id: str, canonical_name: str, executable_name: str, known_paths=None,
                            requires_user_approval_by_default: bool = False, launch_type: str = "executable",
                            application_type: str = "application", launch_method: str = "subprocess"):
        """Register a safe, discovered application for later validation and launch."""
        if not app_id or not canonical_name or not executable_name:
            return
        clean_app_id = app_id.strip().lower()
        registry = {
            "canonical_name": canonical_name,
            "executable_name": executable_name,
            "known_paths": list(known_paths or [executable_name]),
            "requires_user_approval_by_default": bool(requires_user_approval_by_default),
            "launch_type": launch_type,
            "application_type": application_type,
            "launch_method": launch_method,
        }
        self.ALLOWLISTED_APPLICATIONS[clean_app_id] = registry
        self._dynamic_applications[clean_app_id] = registry

    def get_registered_application(self, target: str):
        """Return the allowlisted application metadata for a matched target."""
        clean_target = (target or "").strip().lower()
        if not clean_target:
            return None
        for key, conf in self.ALLOWLISTED_APPLICATIONS.items():
            candidates = {
                key.lower(),
                conf["canonical_name"].lower(),
                conf["executable_name"].lower(),
                *[str(p).lower() for p in conf.get("known_paths", [])],
            }
            if clean_target in candidates:
                return {
                    "app_id": key,
                    "canonical_name": conf["canonical_name"],
                    "executable_name": conf["executable_name"],
                    "known_paths": conf.get("known_paths", []),
                    "launch_type": conf.get("launch_type", "executable"),
                    "application_type": conf.get("application_type", "application"),
                    "launch_method": conf.get("launch_method", "subprocess"),
                    "requires_user_approval_by_default": conf.get("requires_user_approval_by_default", False),
                }
        return None

    def _match_allowlisted_target(self, target: str):
        """Return matching allowlist entry for a canonical id, name, or executable name."""
        clean_target = (target or "").strip().lower()
        if not clean_target:
            return None
        for key, conf in self.ALLOWLISTED_APPLICATIONS.items():
            candidates = {
                key.lower(),
                conf["canonical_name"].lower(),
                conf["executable_name"].lower(),
                *[p.lower() for p in conf.get("known_paths", [])],
            }
            if clean_target in candidates:
                return conf
        return None

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

    def validate_request(self, request: ActionRequest) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Validate request structure, action name, parameters, and target.
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

        clean_target = request.target.strip().lower()
        # Disallow arbitrary directory traversal or executable paths unless matching a registered safe app path.
        is_path_like = ("/" in clean_target) or ("\\" in clean_target)
        if is_path_like:
            allow_path = False
            for conf in self.ALLOWLISTED_APPLICATIONS.values():
                known = [str(p).lower() for p in conf.get("known_paths", [])]
                if clean_target in known or clean_target == os.path.normpath(str(conf.get("executable_name", "")).lower()):
                    allow_path = True
                    break
            if not allow_path:
                return (
                    False,
                    "ERR_TARGET_NOT_ALLOWLISTED",
                    "Arbitrary executable paths and directory traversals are strictly prohibited.",
                )

        # Check target against explicit allowlist
        app_entry = self._match_allowlisted_target(request.target)

        if not app_entry:
            return (
                False,
                "ERR_TARGET_NOT_ALLOWLISTED",
                f"Target '{request.target}' is not in the explicit application allowlist. Permitted: {[k.title() for k in self.ALLOWLISTED_APPLICATIONS]}",
            )

        # Validate parameters - reject dangerous shell arguments or commands
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

        return True, None, None

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

    def load_catalogue_entries(self, catalogue_entries=None):
        """Register a set of discovered app entries without hardcoding paths.

        This bridges the dynamic discovery catalogue into the executor policy so the app
        launcher can execute discovered Windows applications safely and consistently.
        """
        if catalogue_entries is None:
            try:
                from api.app_catalogue import catalogue_service
                catalogue_entries = catalogue_service.get_all_apps()
            except Exception:
                catalogue_entries = []

        for app in catalogue_entries or []:
            try:
                app_id = (app.get("app_id") or app.get("app_name") or "").strip()
                canonical_name = (app.get("app_name") or "").strip()
                launch_target = (app.get("launch_target") or app.get("executable") or "").strip()
                executable_name = (app.get("executable") or os.path.basename(launch_target) or "").strip()
                launch_type = app.get("launch_type") or "executable"
                if not app_id or not canonical_name:
                    continue

                # Keep known safe built-ins and settings URIs available, but do not register
                # every generic built-in tool as directly launchable without review.
                is_safe_builtin = app.get("allowlisted") is True or app_id in {"notepad", "settings", "settings_system", "settings_bluetooth", "settings_display", "settings_network", "settings_sound", "settings_apps", "settings_update"}
                if launch_type == "built_in" and not is_safe_builtin:
                    continue
                if launch_type == "uri":
                    if not executable_name and not launch_target:
                        continue
                elif not executable_name:
                    continue

                known_paths = []
                if launch_target:
                    known_paths.append(launch_target)
                if executable_name and executable_name not in known_paths:
                    known_paths.append(executable_name)
                if launch_type == "uri" and launch_target:
                    known_paths.append(launch_target)

                self.register_application(
                    app_id=app_id,
                    canonical_name=canonical_name,
                    executable_name=executable_name,
                    known_paths=known_paths,
                    requires_user_approval_by_default=bool(app.get("allowlisted") is not True and launch_type == "executable"),
                    launch_type=launch_type,
                    application_type=app.get("application_type") or "application",
                    launch_method=app.get("launch_method") or ("os.startfile" if launch_type == "uri" else "subprocess"),
                )
            except Exception:
                continue

    def resolve_executable_path(self, target: str) -> Optional[str]:
        """Resolve allowlisted application to its verified Windows executable path."""
        clean_target = (target or "").strip().lower()
        for key, conf in self.ALLOWLISTED_APPLICATIONS.items():
            candidates = {
                key.lower(),
                conf["canonical_name"].lower(),
                conf["executable_name"].lower(),
                *[str(p).lower() for p in conf.get("known_paths", [])],
            }
            if clean_target in candidates:
                for candidate in conf["known_paths"]:
                    if candidate and os.path.exists(candidate):
                        return candidate
                if conf["executable_name"].lower().endswith(".exe"):
                    resolved = shutil.which(conf["executable_name"]) or conf["executable_name"]
                    if resolved:
                        return resolved
                if conf["known_paths"]:
                    return str(conf["known_paths"][0])
        return None
