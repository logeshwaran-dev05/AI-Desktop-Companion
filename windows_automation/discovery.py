"""
Installed-Application Discovery Module for Windows Automation.

Discovers registered applications, Start Menu shortcuts, App Paths, and AppX/MSIX
packages using trusted, reviewable Windows sources without executing binaries.
"""

import os
import re
import sys
import struct
from typing import Dict, List, Optional, Tuple, Set
from windows_automation.schemas import ApplicationRecord, DiscoveryResult, current_iso_timestamp


def normalize_app_name(name: str) -> str:
    """Normalize application name for safe comparison, indexing, and alias matching."""
    if not name:
        return ""
    # Lowercase and replace non-alphanumeric characters with spaces
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", name.lower())
    # Collapse multiple spaces and trim
    return " ".join(cleaned.split())


def generate_stable_app_id(name: str) -> str:
    """Generate a clean, stable application identifier from its display name."""
    norm = normalize_app_name(name)
    slug = norm.replace(" ", "_")
    return f"app_{slug}" if slug else "app_unknown"


def parse_lnk_file(filepath: str) -> Optional[str]:
    """
    Safely extract target executable path from a Windows .lnk Shell Link file
    using pure Python binary parsing of the MS-SHLLINK specification.
    Returns the resolved target path if valid, else None.
    """
    try:
        with open(filepath, "rb") as f:
            data = f.read()

        # Check Shell Link Header size (76 bytes) and signature (0x0000004C)
        if len(data) < 76 or data[:4] != b"\x4c\x00\x00\x00":
            return None

        flags = struct.unpack("<I", data[0x14:0x18])[0]
        pos = 76

        # HasLinkTargetIDList (Bit 0)
        if flags & 0x01:
            if pos + 2 > len(data):
                return None
            id_list_size = struct.unpack("<H", data[pos : pos + 2])[0]
            pos += 2 + id_list_size

        # HasLinkInfo (Bit 1)
        if flags & 0x02:
            link_info_start = pos
            if link_info_start + 28 <= len(data):
                (
                    link_info_size,
                    header_size,
                    info_flags,
                    vol_offset,
                    base_path_offset,
                ) = struct.unpack("<IIIII", data[link_info_start : link_info_start + 20])

                if base_path_offset and (link_info_start + base_path_offset < len(data)):
                    target_bytes = data[link_info_start + base_path_offset : link_info_start + link_info_size]
                    target_str = target_bytes.split(b"\x00")[0].decode("ansi", errors="ignore")
                    if target_str:
                        return target_str
    except Exception:
        return None
    return None


class ApplicationDiscoverer:
    """
    Scans and catalogues Windows installed applications from reviewable sources.
    Never executes binaries during discovery.
    """

    # Safe built-in Windows utilities available on standard installations
    BUILTIN_UTILITIES = [
        {
            "display_name": "Notepad",
            "executable_name": "notepad.exe",
            "aliases": ["notepad", "text editor", "note", "editor"],
            "known_paths": [
                r"C:\Windows\System32\notepad.exe",
                r"C:\Windows\notepad.exe",
            ],
            "app_type": "executable",
            "launch_method": "subprocess_executable",
        },
        {
            "display_name": "Calculator",
            "executable_name": "calc.exe",
            "aliases": ["calc", "calculator", "math"],
            "known_paths": [
                r"C:\Windows\System32\calc.exe",
            ],
            "app_type": "packaged_app",
            "launch_method": "subprocess_executable",
        },
        {
            "display_name": "Paint",
            "executable_name": "mspaint.exe",
            "aliases": ["paint", "mspaint", "draw"],
            "known_paths": [
                r"C:\Windows\System32\mspaint.exe",
            ],
            "app_type": "executable",
            "launch_method": "subprocess_executable",
        },
        {
            "display_name": "Task Manager",
            "executable_name": "taskmgr.exe",
            "aliases": ["task manager", "taskmgr", "task"],
            "known_paths": [
                r"C:\Windows\System32\taskmgr.exe",
            ],
            "app_type": "executable",
            "launch_method": "subprocess_executable",
        },
    ]

    def __init__(
        self,
        include_builtins: bool = True,
        include_start_menu: bool = True,
        include_registry: bool = True,
        include_app_paths: bool = True,
        include_packaged_apps: bool = True,
        custom_search_dirs: Optional[List[str]] = None,
    ):
        self.include_builtins = include_builtins
        self.include_start_menu = include_start_menu
        self.include_registry = include_registry
        self.include_app_paths = include_app_paths
        self.include_packaged_apps = include_packaged_apps
        self.custom_search_dirs = custom_search_dirs or []

    def discover_all(self) -> DiscoveryResult:
        """
        Run discovery across all configured Windows sources, deduplicate results,
        and return a structured DiscoveryResult.
        """
        sources_scanned: List[str] = []
        errors: List[str] = []
        discovered_map: Dict[str, ApplicationRecord] = {}  # unique_key -> ApplicationRecord

        # 1. Discover System Built-ins
        if self.include_builtins:
            sources_scanned.append("system_builtin")
            try:
                self._discover_builtins(discovered_map)
            except Exception as exc:
                errors.append(f"system_builtin: {str(exc)}")

        # 2. Discover from Start Menu Shortcuts
        if self.include_start_menu:
            start_menu_dirs = [
                (os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs"), "start_menu_all_users"),
                (os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"), "start_menu_user"),
            ]
            for dir_path, src_name in start_menu_dirs:
                sources_scanned.append(src_name)
                try:
                    self._discover_from_directory(dir_path, src_name, discovered_map)
                except Exception as exc:
                    errors.append(f"{src_name}: {str(exc)}")

        # 3. Discover from Windows App Paths Registry
        if self.include_app_paths and sys.platform == "win32":
            sources_scanned.append("app_paths")
            try:
                self._discover_from_app_paths(discovered_map)
            except Exception as exc:
                errors.append(f"app_paths: {str(exc)}")

        # 4. Discover from Windows Uninstall Registry Keys
        if self.include_registry and sys.platform == "win32":
            sources_scanned.append("windows_registry")
            try:
                self._discover_from_registry(discovered_map)
            except Exception as exc:
                errors.append(f"windows_registry: {str(exc)}")

        # 5. Discover from Packaged / AppX Applications
        if self.include_packaged_apps and sys.platform == "win32":
            sources_scanned.append("appx_packages")
            try:
                self._discover_from_packaged_apps(discovered_map)
            except Exception as exc:
                errors.append(f"appx_packages: {str(exc)}")

            sources_scanned.append("start_apps")
            try:
                self._discover_from_start_apps(discovered_map)
            except Exception as exc:
                errors.append(f"start_apps: {str(exc)}")

        # 6. Custom search directories
        for custom_dir in self.custom_search_dirs:
            sources_scanned.append(f"custom:{custom_dir}")
            try:
                self._discover_from_directory(custom_dir, "custom_directory", discovered_map)
            except Exception as exc:
                errors.append(f"custom:{custom_dir}: {str(exc)}")

        apps = sorted(discovered_map.values(), key=lambda a: a.display_name.lower())

        return DiscoveryResult(
            applications=apps,
            total_discovered=len(apps),
            sources_scanned=sources_scanned,
            discovery_errors=errors,
            timestamp=current_iso_timestamp(),
        )

    def _discover_builtins(self, result_map: Dict[str, ApplicationRecord]):
        """Register known safe Windows built-in utilities."""
        for b in self.BUILTIN_UTILITIES:
            resolved_path = None
            for p in b["known_paths"]:
                if os.path.exists(p):
                    resolved_path = p
                    break
            if not resolved_path:
                resolved_path = b["executable_name"]

            key = (resolved_path or b["executable_name"]).lower()
            if key not in result_map:
                app_id = generate_stable_app_id(b["display_name"])
                rec = ApplicationRecord(
                    app_id=app_id,
                    display_name=b["display_name"],
                    normalized_name=normalize_app_name(b["display_name"]),
                    executable_path=resolved_path,
                    source="system_builtin",
                    app_type=b.get("app_type", "executable"),
                    status="available",
                    launch_method=b.get("launch_method", "subprocess_executable"),
                    aliases=list(b["aliases"]),
                    metadata={"executable_name": b["executable_name"]},
                )
                result_map[key] = rec

    def _discover_from_directory(
        self,
        base_dir: str,
        source_name: str,
        result_map: Dict[str, ApplicationRecord],
    ):
        """Recursively scan directory for application .lnk shortcuts."""
        if not os.path.exists(base_dir):
            return

        for root, _, files in os.walk(base_dir):
            for file_name in files:
                if not file_name.lower().endswith(".lnk"):
                    continue

                full_path = os.path.join(root, file_name)
                base_lower = file_name.lower()
                # Exclude obvious uninstaller / updater / doc shortcuts
                if any(k in base_lower for k in ["uninstall", "remove", "help", "readme", "documentation", "manual"]):
                    continue

                target = parse_lnk_file(full_path)
                clean_name = os.path.splitext(file_name)[0]
                norm_name = normalize_app_name(clean_name)
                app_id = generate_stable_app_id(clean_name)

                aliases = [norm_name]
                words = norm_name.split()
                if len(words) > 1:
                    aliases.append(words[0])
                    aliases.append(words[-1])

                # Target may be an EXE or a shell link to an AUMID
                if target and target.lower().endswith(".exe"):
                    key = target.lower()
                    if key in result_map:
                        existing = result_map[key]
                        for al in aliases:
                            if al not in existing.aliases:
                                existing.aliases.append(al)
                        if not existing.shortcut_path:
                            existing.shortcut_path = full_path
                    else:
                        rec = ApplicationRecord(
                            app_id=app_id,
                            display_name=clean_name,
                            normalized_name=norm_name,
                            executable_path=target,
                            source=source_name,
                            app_type="shortcut",
                            status="available" if os.path.exists(target) else "target_missing",
                            launch_method="subprocess_executable",
                            shortcut_path=full_path,
                            aliases=list(set(aliases)),
                            icon_path=target,
                            metadata={"shortcut_file": full_path},
                        )
                        result_map[key] = rec
                elif not target:
                    # Windows Store / Modern app shortcut
                    key = full_path.lower()
                    if key not in result_map:
                        rec = ApplicationRecord(
                            app_id=app_id,
                            display_name=clean_name,
                            normalized_name=norm_name,
                            executable_path="",
                            source=source_name,
                            app_type="shortcut",
                            status="available",
                            launch_method="start_menu_shortcut",
                            shortcut_path=full_path,
                            aliases=list(set(aliases)),
                            metadata={"shortcut_file": full_path},
                        )
                        result_map[key] = rec

    def _discover_from_app_paths(self, result_map: Dict[str, ApplicationRecord]):
        """Scan Windows App Paths in HKLM and HKCU."""
        import winreg

        hives = [
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\App Paths"),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\App Paths"),
        ]

        for hive, subkey_path in hives:
            try:
                with winreg.OpenKey(hive, subkey_path) as root_key:
                    num_subkeys = winreg.QueryInfoKey(root_key)[0]
                    for i in range(num_subkeys):
                        try:
                            key_name = winreg.EnumKey(root_key, i)
                            if not key_name.lower().endswith(".exe"):
                                continue

                            with winreg.OpenKey(root_key, key_name) as app_key:
                                try:
                                    target_exe = winreg.QueryValueEx(app_key, "")[0]
                                except Exception:
                                    target_exe = None

                                if target_exe and isinstance(target_exe, str):
                                    clean_exe = target_exe.strip('"')
                                    if clean_exe.lower().endswith(".exe"):
                                        key = clean_exe.lower()
                                        clean_name = os.path.splitext(key_name)[0]
                                        norm_name = normalize_app_name(clean_name)
                                        app_id = generate_stable_app_id(clean_name)

                                        if key in result_map:
                                            existing = result_map[key]
                                            if norm_name not in existing.aliases:
                                                existing.aliases.append(norm_name)
                                        else:
                                            rec = ApplicationRecord(
                                                app_id=app_id,
                                                display_name=clean_name,
                                                normalized_name=norm_name,
                                                executable_path=clean_exe,
                                                source="app_paths",
                                                app_type="app_path",
                                                status="available" if os.path.exists(clean_exe) else "target_missing",
                                                launch_method="subprocess_executable",
                                                aliases=[norm_name, key_name.lower()],
                                            )
                                            result_map[key] = rec
                        except Exception:
                            continue
            except Exception:
                continue

    def _discover_from_registry(self, result_map: Dict[str, ApplicationRecord]):
        """Scan standard Windows Uninstall registry keys for installed software."""
        import winreg

        keys = [
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]

        for hive, subkey_path in keys:
            try:
                with winreg.OpenKey(hive, subkey_path) as root_key:
                    num_subkeys = winreg.QueryInfoKey(root_key)[0]
                    for i in range(num_subkeys):
                        try:
                            key_name = winreg.EnumKey(root_key, i)
                            with winreg.OpenKey(root_key, key_name) as app_key:
                                def get_val(val_name):
                                    try:
                                        return winreg.QueryValueEx(app_key, val_name)[0]
                                    except Exception:
                                        return None

                                disp_name = get_val("DisplayName")
                                if not disp_name or not isinstance(disp_name, str):
                                    continue

                                if disp_name.startswith("KB") or "Update for Windows" in disp_name:
                                    continue

                                install_loc = get_val("InstallLocation")
                                disp_icon = get_val("DisplayIcon")
                                version = get_val("DisplayVersion")
                                publisher = get_val("Publisher")

                                target_exe = None
                                if disp_icon and isinstance(disp_icon, str):
                                    clean_icon = disp_icon.split(",")[0].strip('"')
                                    if clean_icon.lower().endswith(".exe") and os.path.exists(clean_icon):
                                        target_exe = clean_icon

                                if not target_exe and install_loc and isinstance(install_loc, str):
                                    if os.path.isdir(install_loc):
                                        for cand in os.listdir(install_loc):
                                            if cand.lower().endswith(".exe") and not any(
                                                x in cand.lower() for x in ["unins", "setup", "helper", "crash", "update"]
                                            ):
                                                full_cand = os.path.join(install_loc, cand)
                                                if os.path.isfile(full_cand):
                                                    target_exe = full_cand
                                                    break

                                if target_exe:
                                    key = target_exe.lower()
                                    if key in result_map:
                                        existing = result_map[key]
                                        if not existing.version and version:
                                            existing.version = str(version)
                                        if not existing.publisher and publisher:
                                            existing.publisher = str(publisher)
                                    else:
                                        app_id = generate_stable_app_id(disp_name)
                                        norm_name = normalize_app_name(disp_name)
                                        rec = ApplicationRecord(
                                            app_id=app_id,
                                            display_name=disp_name,
                                            normalized_name=norm_name,
                                            executable_path=target_exe,
                                            source="registry",
                                            app_type="executable",
                                            status="available",
                                            launch_method="subprocess_executable",
                                            version=str(version) if version else None,
                                            publisher=str(publisher) if publisher else None,
                                            icon_path=disp_icon,
                                            aliases=[norm_name],
                                        )
                                        result_map[key] = rec
                        except Exception:
                            continue
            except Exception:
                continue

    def _discover_from_packaged_apps(self, result_map: Dict[str, ApplicationRecord]):
        """Discover WindowsApp execution aliases from %LOCALAPPDATA%\\Microsoft\\WindowsApps."""
        windows_apps_dir = os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WindowsApps")
        if not os.path.exists(windows_apps_dir):
            return

        for fname in os.listdir(windows_apps_dir):
            if fname.lower().endswith(".exe"):
                full_path = os.path.join(windows_apps_dir, fname)
                clean_name = os.path.splitext(fname)[0]
                norm_name = normalize_app_name(clean_name)
                app_id = generate_stable_app_id(clean_name)

                key = full_path.lower()
                if key not in result_map:
                    rec = ApplicationRecord(
                        app_id=app_id,
                        display_name=clean_name,
                        normalized_name=norm_name,
                        executable_path=full_path,
                        source="appx_package",
                        app_type="packaged_app",
                        status="available",
                        launch_method="subprocess_executable",
                        aliases=[norm_name, fname.lower()],
                        metadata={"is_windows_app_alias": True},
                    )
                    result_map[key] = rec

    def _discover_from_start_apps(self, result_map: Dict[str, ApplicationRecord]):
        """
        Discover modern Store/UWP apps and Start Menu apps via Windows Get-StartApps.
        Uses a local JSON cache for sub-millisecond startup, refreshing when cache is older than 24 hours.
        """
        import json
        import tempfile
        import subprocess

        cache_path = os.path.join(tempfile.gettempdir(), "ai_companion_start_apps_cache.json")
        items = []

        # Check cache
        if os.path.exists(cache_path):
            try:
                mtime = os.path.getmtime(cache_path)
                if time.time() - mtime < 86400:  # 24 hours
                    with open(cache_path, "r", encoding="utf-8") as f:
                        items = json.load(f)
            except Exception:
                items = []

        if not items:
            try:
                res = subprocess.run(
                    ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "Get-StartApps | ConvertTo-Json -Compress"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if res.returncode == 0 and res.stdout.strip():
                    raw = json.loads(res.stdout)
                    items = raw if isinstance(raw, list) else [raw]
                    try:
                        with open(cache_path, "w", encoding="utf-8") as f:
                            json.dump(items, f)
                    except Exception:
                        pass
            except Exception:
                items = []

        COMMON_SMART_ALIASES = {
            "whatsapp": ["whatsapp", "whats app", "wa"],
            "calculator": ["calc", "calculator"],
            "google chrome": ["chrome", "google chrome", "browser", "my browser"],
            "visual studio code": ["vs code", "vscode", "code"],
            "adobe photoshop 2025": ["photoshop", "adobe photoshop", "ps"],
            "spotify": ["spotify", "music", "spotify music"],
            "settings": ["settings", "windows settings", "pc settings"],
            "word": ["word", "ms word", "microsoft word"],
            "excel": ["excel", "ms excel", "microsoft excel"],
            "powerpoint": ["powerpoint", "ppt", "ms powerpoint"],
        }

        for item in items:
            name = item.get("Name")
            aid = item.get("AppID")
            if not name or not aid:
                continue

            app_id = generate_stable_app_id(name)
            norm_name = normalize_app_name(name)
            key = f"startapp:{name.lower()}"

            # Generate smart aliases
            aliases = [norm_name]
            lower_name = name.lower()

            for target_k, smart_list in COMMON_SMART_ALIASES.items():
                if target_k == lower_name or (len(target_k) > 4 and target_k in lower_name):
                    aliases.extend(smart_list)

            # Clean duplicate aliases
            aliases = list(dict.fromkeys(aliases))

            is_packaged = "!" in aid or aid.startswith("Microsoft.") or aid.startswith("5319275A.") or "App" in aid
            launch_method = "appx_packaged" if is_packaged else "shell_apps_folder"

            rec = ApplicationRecord(
                app_id=app_id,
                display_name=name,
                normalized_name=norm_name,
                executable_path=aid,
                source="start_apps",
                app_type="packaged_app" if is_packaged else "desktop_app",
                status="available",
                launch_method=launch_method,
                app_user_model_id=aid,
                aliases=aliases,
                metadata={"start_apps_id": aid},
            )
            result_map[key] = rec
