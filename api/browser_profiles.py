"""Browser profile discovery utilities.

Provides a simple function to discover Chrome user profiles on a Windows system.
The function returns a list of dictionaries with ``name`` and ``path`` keys.
It is deliberately lightweight and mock‑friendly for unit tests.
"""

import os
from pathlib import Path
from typing import List, Dict

def get_browser_profiles(browser_name: str) -> List[Dict[str, str]]:
    """Return discovered profiles for the given *browser_name*.

    Currently only supports ``"chrome"`` (case‑insensitive). Chrome stores
    profiles under ``%LOCALAPPDATA%\\Google\\Chrome\\User Data`` where the
    default profile is named ``Default`` and additional profiles are named
    ``Profile 1``, ``Profile 2`` … etc.

    The function returns a list of ``{"name": <profile_name>, "path": <full_path>}``
    dictionaries. If the browser is not recognised, an empty list is returned.
    Missing directories are treated as no profiles (empty list) – callers can
    decide how to surface this to the UI.
    """
    if not browser_name or browser_name.lower() != "chrome":
        # Unsupported or unknown browser – return empty list for safety
        return []

    # Resolve the base Chrome user‑data directory
    local_app_data = os.getenv("LOCALAPPDATA")
    if not local_app_data:
        # Environment variable missing – treat as no profiles
        return []

    base_path = Path(local_app_data) / "Google" / "Chrome" / "User Data"
    if not base_path.is_dir():
        return []

    profiles: List[Dict[str, str]] = []
    try:
        for entry in base_path.iterdir():
            if not entry.is_dir():
                continue
            name = entry.name
            # Chrome uses "Default" for the primary profile and "Profile N" for others
            if name == "Default" or name.startswith("Profile "):
                profiles.append({"name": name, "path": str(entry)})
    except PermissionError:
        # If we cannot read the directory, return empty – callers will surface an error
        return []
    return profiles
