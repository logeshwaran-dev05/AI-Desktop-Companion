"""
Policy engine and request validator for Windows Automation.

Enforces:
1. Strict explicit application allowlist (Notepad for Milestone 1).
2. Rejection of arbitrary executable paths, shell commands, scripts, piping.
3. Verification of security authorization decisions (denials, missing approvals, invalid states).
"""

from typing import Tuple, Optional, Set
import os
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
        # Disallow arbitrary directory traversal or executable paths unless matching canonical allowlist
        if "/" in clean_target or ("\\" in clean_target and clean_target not in [p.lower() for p in self.ALLOWLISTED_APPLICATIONS["notepad"]["known_paths"]]):
            return (
                False,
                "ERR_TARGET_NOT_ALLOWLISTED",
                "Arbitrary executable paths and directory traversals are strictly prohibited.",
            )

        # Check target against explicit allowlist
        app_entry = None
        for key, conf in self.ALLOWLISTED_APPLICATIONS.items():
            if clean_target == key or clean_target == conf["executable_name"].lower():
                app_entry = conf
                break

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

    def resolve_executable_path(self, target: str) -> Optional[str]:
        """Resolve allowlisted application to its verified Windows executable path."""
        clean_target = target.strip().lower()
        for key, conf in self.ALLOWLISTED_APPLICATIONS.items():
            if clean_target == key or clean_target == conf["executable_name"].lower():
                for candidate in conf["known_paths"]:
                    if os.path.exists(candidate):
                        return candidate
                # Fallback to standard executable name on PATH
                return conf["executable_name"]
        return None
