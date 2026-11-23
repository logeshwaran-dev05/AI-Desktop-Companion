"""
Browser Profile Discovery and Management Module.
================================================
Discovers and manages profiles for Chromium-based browsers (Google Chrome & Microsoft Edge).
Allows launching directly into a specific profile (e.g. "Logesh", "LOKI", "Aimtech")
bypassing the "Who's using Chrome?" Profile Picker window.
"""

import os
import json
import re
from typing import Dict, List, Optional, Any
from difflib import SequenceMatcher


def get_chrome_user_data_path() -> str:
    """Returns the default Chrome User Data directory on Windows."""
    local_app_data = os.environ.get("LOCALAPPDATA") or os.path.expandvars(r"%LOCALAPPDATA%")
    return os.path.join(local_app_data, "Google", "Chrome", "User Data")


def get_edge_user_data_path() -> str:
    """Returns the default Microsoft Edge User Data directory on Windows."""
    local_app_data = os.environ.get("LOCALAPPDATA") or os.path.expandvars(r"%LOCALAPPDATA%")
    return os.path.join(local_app_data, "Microsoft", "Edge", "User Data")


def get_browser_profiles(browser: str = "chrome") -> List[Dict[str, Any]]:
    """
    Reads browser profile metadata from 'Local State' JSON without launching the browser.
    Returns a list of profile dictionaries:
    [
        {
            "directory": "Default",
            "name": "Logeshwaran",
            "email": "...",
            "avatar_icon": "..."
        },
        ...
    ]
    """
    user_data_dir = get_chrome_user_data_path() if browser.lower() == "chrome" else get_edge_user_data_path()
    local_state_file = os.path.join(user_data_dir, "Local State")

    if not os.path.exists(local_state_file):
        return []

    try:
        with open(local_state_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        info_cache = data.get("profile", {}).get("info_cache", {})
        profiles = []

        for dir_key, profile_info in info_cache.items():
            name = profile_info.get("name") or dir_key
            user_name = profile_info.get("user_name", "")
            gaia_name = profile_info.get("gaia_name", "")

            # Display name preference: custom name > gaia_name > user_name > dir_key
            display_name = name or gaia_name or user_name or dir_key

            profiles.append({
                "directory": dir_key,
                "name": display_name.strip(),
                "user_name": user_name,
                "gaia_name": gaia_name,
                "is_ephemeral": profile_info.get("is_ephemeral", False),
            })

        return profiles
    except Exception:
        return []


def get_default_profile_directory(browser: str = "chrome") -> Optional[str]:
    """
    Returns the most appropriate profile directory to avoid the Profile Picker dialog.
    Reads 'last_used' from Local State, or falls back to 'Default' or the first available profile directory.
    """
    user_data_dir = get_chrome_user_data_path() if browser.lower() == "chrome" else get_edge_user_data_path()
    local_state_file = os.path.join(user_data_dir, "Local State")
    if os.path.exists(local_state_file):
        try:
            with open(local_state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            last_used = data.get("profile", {}).get("last_used")
            if last_used:
                return last_used
            last_active = data.get("profile", {}).get("last_active_profiles", [])
            if last_active and len(last_active) > 0:
                return last_active[0]
        except Exception:
            pass

    profiles = get_browser_profiles(browser)
    if profiles:
        return profiles[0]["directory"]
    return None


def resolve_profile_directory(browser: str = "chrome", requested_profile: Optional[str] = None) -> Optional[str]:
    """
    Fuzzy matches a user-requested profile name (e.g. 'loki', 'logesh', 'aimtech')
    against installed browser profiles and returns the exact directory key (e.g. 'Profile 2').
    """
    if not requested_profile:
        return None

    profiles = get_browser_profiles(browser)
    if not profiles:
        return None

    clean_req = re.sub(r"[^a-zA-Z0-9]", "", requested_profile.lower().strip())

    best_match = None
    best_score = 0.0

    for prof in profiles:
        dir_name = prof["directory"]
        disp_name = prof["name"]

        # Exact match
        clean_disp = re.sub(r"[^a-zA-Z0-9]", "", disp_name.lower().strip())
        clean_dir = re.sub(r"[^a-zA-Z0-9]", "", dir_name.lower().strip())

        if clean_req == clean_disp or clean_req == clean_dir:
            return dir_name

        # Substring match
        if clean_req in clean_disp or clean_disp in clean_req:
            score = 0.9
        else:
            score = SequenceMatcher(None, clean_req, clean_disp).ratio()

        if score > best_score:
            best_score = score
            best_match = dir_name

    if best_score >= 0.65:
        return best_match

    return None


def build_chrome_launch_args(profile_dir: Optional[str] = None, url: Optional[str] = None) -> List[str]:
    """
    Builds command-line arguments to launch Chrome directly into a specific profile,
    bypassing the Chrome Profile Picker window completely.
    """
    args = []
    if profile_dir:
        args.append(f'--profile-directory={profile_dir}')
    if url:
        args.append(url)
    return args
