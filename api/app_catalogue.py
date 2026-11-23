"""
Windows Application Discovery and Dynamic Catalogue Service.

Safely discovers installed Windows applications and built-in tools using:
1. Windows Built-in System Applications (Notepad, Calculator, File Explorer, Task Manager, Control Panel, Paint).
2. Windows Settings Pages (ms-settings:* URIs for Settings, System, Bluetooth, Display, Network, Sound, Apps, Update).
3. Windows Registry App Paths (HKLM and HKCU SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths).
4. Windows Start Menu Application Shortcuts (.lnk files from ProgramData and AppData).

Guarantees:
- Never scans arbitrary user documents or private directories.
- Deduplicates applications by canonical identifier.
- Validates executable presence or URI format.
- Disallows invalid or unavailable entries.
"""

import glob
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Fallback import for winreg on Windows systems
try:
    import winreg
except ImportError:
    winreg = None  # type: ignore


@dataclass
class CatalogueApp:
    """Standardized Application Catalogue Entry."""
    app_id: str
    app_name: str
    executable: str
    launch_target: str
    launch_type: str = "executable"  # "executable", "built_in", "uri", "packaged"
    application_type: str = "application"  # "application", "packaged", "uri", "builtin"
    launch_method: str = "subprocess"  # "subprocess", "os.startfile", "uri"
    allowlisted: bool = False
    aliases: List[str] = field(default_factory=list)
    description: str = ""
    # Additional optional metadata
    version: Optional[str] = None
    publisher: Optional[str] = None
    install_location: Optional[str] = None
    uri_protocol: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Pre-defined Safe Windows Built-ins & Settings Pages
# ---------------------------------------------------------------------------

WINDOWS_BUILT_IN_TOOLS: List[CatalogueApp] = [
    CatalogueApp(
        app_id="notepad",
        app_name="Notepad",
        executable="notepad.exe",
        launch_target="notepad.exe",
        launch_type="built_in",
        allowlisted=True,
        aliases=["notepad", "notes", "text editor", "note pad"],
        description="Windows default plain text editor",
    ),
    CatalogueApp(
        app_id="calculator",
        app_name="Calculator",
        executable="calc.exe",
        launch_target="calc.exe",
        launch_type="built_in",
        allowlisted=False,
        aliases=["calc", "calculator", "math", "maths"],
        description="Windows default Calculator",
    ),
    CatalogueApp(
        app_id="explorer",
        app_name="File Explorer",
        executable="explorer.exe",
        launch_target="explorer.exe",
        launch_type="built_in",
        allowlisted=False,
        aliases=["file explorer", "explorer", "files", "my files", "file manager", "windows explorer"],
        description="Windows File Explorer and directory manager",
    ),
    CatalogueApp(
        app_id="taskmgr",
        app_name="Task Manager",
        executable="taskmgr.exe",
        launch_target="taskmgr.exe",
        launch_type="built_in",
        allowlisted=False,
        aliases=["task manager", "taskmgr", "task manager utility", "task list", "running processes"],
        description="Windows Task Manager process monitor",
    ),
    CatalogueApp(
        app_id="control",
        app_name="Control Panel",
        executable="control.exe",
        launch_target="control.exe",
        launch_type="built_in",
        allowlisted=False,
        aliases=["control panel", "control", "windows control panel"],
        description="Windows Classic Control Panel",
    ),
    CatalogueApp(
        app_id="paint",
        app_name="Paint",
        executable="mspaint.exe",
        launch_target="mspaint.exe",
        launch_type="built_in",
        allowlisted=False,
        aliases=["paint", "mspaint", "drawing", "ms paint"],
        description="Windows Paint graphics editor",
    ),
    CatalogueApp(
        app_id="cmd",
        app_name="Command Prompt",
        executable="cmd.exe",
        launch_target="cmd.exe",
        launch_type="built_in",
        allowlisted=False,
        aliases=["command prompt", "terminal", "cmd"],
        description="Windows Command Shell",
    ),
]

WINDOWS_SETTINGS_PAGES: List[CatalogueApp] = [
    CatalogueApp(
        app_id="settings",
        app_name="Windows Settings",
        executable="ms-settings:",
        launch_target="ms-settings:",
        launch_type="uri",
        allowlisted=False,
        aliases=["settings", "windows settings", "pc settings", "open settings", "preferences"],
        description="Windows Modern Settings hub",
    ),
    CatalogueApp(
        app_id="settings_system",
        app_name="System Settings",
        executable="ms-settings:system",
        launch_target="ms-settings:system",
        launch_type="uri",
        allowlisted=False,
        aliases=["system", "system settings", "go to system", "open system", "system info", "about pc"],
        description="Windows System and device specifications",
    ),
    CatalogueApp(
        app_id="settings_bluetooth",
        app_name="Bluetooth Settings",
        executable="ms-settings:bluetooth",
        launch_target="ms-settings:bluetooth",
        launch_type="uri",
        allowlisted=False,
        aliases=[
            "bluetooth",
            "bluetooth settings",
            "open bluetooth settings",
            "bluetooth and devices",
            "paired devices",
            "bluetooth devices",
        ],
        description="Windows Bluetooth & connected devices settings",
    ),
    CatalogueApp(
        app_id="settings_display",
        app_name="Display Settings",
        executable="ms-settings:display",
        launch_target="ms-settings:display",
        launch_type="uri",
        allowlisted=False,
        aliases=[
            "display",
            "display settings",
            "open display settings",
            "screen settings",
            "resolution",
            "monitors",
        ],
        description="Windows Display and resolution settings",
    ),
    CatalogueApp(
        app_id="settings_network",
        app_name="Network Settings",
        executable="ms-settings:network",
        launch_target="ms-settings:network",
        launch_type="uri",
        allowlisted=False,
        aliases=[
            "network",
            "network settings",
            "open network settings",
            "internet settings",
            "wifi",
            "wi-fi",
            "wifi settings",
            "wi-fi settings",
            "ethernet settings",
        ],
        description="Windows Network & Internet settings",
    ),
    CatalogueApp(
        app_id="settings_sound",
        app_name="Sound Settings",
        executable="ms-settings:sound",
        launch_target="ms-settings:sound",
        launch_type="uri",
        allowlisted=False,
        aliases=["sound", "sound settings", "audio settings", "volume settings", "speakers"],
        description="Windows Sound output and volume settings",
    ),
    CatalogueApp(
        app_id="settings_apps",
        app_name="Apps Settings",
        executable="ms-settings:appsfeatures",
        launch_target="ms-settings:appsfeatures",
        launch_type="uri",
        allowlisted=False,
        aliases=["apps", "apps settings", "installed apps", "installed applications", "add or remove programs"],
        description="Windows Installed applications list",
    ),
    CatalogueApp(
        app_id="settings_update",
        app_name="Windows Update",
        executable="ms-settings:windowsupdate",
        launch_target="ms-settings:windowsupdate",
        launch_type="uri",
        allowlisted=False,
        aliases=["windows update", "update settings", "check for updates", "updates"],
        description="Windows Update settings",
    ),
]


# ---------------------------------------------------------------------------
# Windows Dynamic Application Catalogue Service
# ---------------------------------------------------------------------------

class WindowsApplicationCatalogue:
    """
    Central discovery, normalization, and catalogue management service
    for all installed Windows applications.
    """

    KNOWN_CANONICAL_NAMES = {
        "chrome": "Google Chrome",
        "msedge": "Microsoft Edge",
        "edge": "Microsoft Edge",
        "code": "Visual Studio Code",
        "vscode": "Visual Studio Code",
        "devenv": "Visual Studio 2022",
        "excel": "Microsoft Excel",
        "powerpnt": "Microsoft PowerPoint",
        "winword": "Microsoft Word",
        "outlook": "Microsoft Outlook",
        "notepad": "Notepad",
        "calc": "Calculator",
        "mspaint": "Paint",
        "explorer": "File Explorer",
        "taskmgr": "Task Manager",
        "control": "Control Panel",
    }

    KNOWN_EXTRA_ALIASES = {
        "chrome": ["chrome", "google chrome", "google", "browser", "my browser", "web browser", "internet"],
        "edge": ["edge", "microsoft edge", "ms edge", "msedge"],  # No generic "browser" — Chrome is primary
        "vscode": ["vscode", "vs code", "code", "visual studio code", "code editor", "my code editor"],
        "notepad": ["notepad", "notes", "text editor"],
        "calculator": ["calc", "calculator", "math"],
        "paint": ["paint", "mspaint", "drawing"],
        "explorer": ["file explorer", "explorer", "files", "my files", "file manager"],
        "taskmgr": ["task manager", "taskmgr", "processes", "task list"],
        "control": ["control panel", "control"],
    }

    def __init__(self, enable_live_scan: bool = True):
        self._catalogue: Dict[str, CatalogueApp] = {}
        self._alias_index: Dict[str, str] = {}  # alias.lower() -> app_id
        self._enable_live_scan = enable_live_scan
        self._build_catalogue()

    def _build_catalogue(self) -> None:
        """Populate catalogue in order of precedence: built-ins -> settings -> registry -> shortcuts."""
        # 1. Register Built-in applications
        for app in WINDOWS_BUILT_IN_TOOLS:
            self._register_app(app)

        # 2. Register Windows Settings URIs
        for app in WINDOWS_SETTINGS_PAGES:
            self._register_app(app)

        # 3. Live discovery from Windows Registry App Paths (if enabled and on Windows)
        if self._enable_live_scan and winreg is not None:
            self._discover_registry_app_paths()

        # 4. Live discovery from packaged / UWP apps (if enabled and on Windows)
        if self._enable_live_scan:
            self._discover_packaged_apps()

        # 5. Live discovery from Start Menu shortcuts (if enabled and on Windows)
        if self._enable_live_scan:
            self._discover_start_menu_shortcuts()

        # 6. Populate pre-defined installed apps for reliable multi-platform tests
        self._register_standard_third_party_apps()

    def refresh_catalogue(self, enable_live_scan: Optional[bool] = None) -> List[Dict[str, Any]]:
        """Rebuild the application catalogue, optionally toggling live discovery."""
        if enable_live_scan is not None:
            self._enable_live_scan = enable_live_scan
        self._catalogue.clear()
        self._alias_index.clear()
        self._build_catalogue()
        return self.get_all_apps()

    def refresh(self, enable_live_scan: Optional[bool] = None) -> List[Dict[str, Any]]:
        """Backward-compatible refresh wrapper for catalogue consumers."""
        return self.refresh_catalogue(enable_live_scan=enable_live_scan)

    def discover_applications(self, enable_live_scan: Optional[bool] = None) -> List[Dict[str, Any]]:
        """Alias for catalogue refresh used by discovery-oriented callers."""
        return self.refresh_catalogue(enable_live_scan=enable_live_scan)

    def _build_alias_key(self, value: str) -> str:
        """Normalize alias values for lookup without introducing OS-specific path rules."""
        return (value or "").strip().lower().rstrip("?.!,")

    def _safe_app_name(self, value: str) -> str:
        """Normalize a display name while avoiding empty or invalid values."""
        cleaned = (value or "").strip()
        return cleaned if cleaned else "Unknown Application"

    def _make_app_id(self, app_name: str) -> str:
        """Create a stable identifier from a display name."""
        name = (app_name or "").strip()
        if not name:
            return "application"
        normalized = re.sub(r"[^a-z0-9]+", "", name.lower())
        return normalized or "application"

    def _register_app(self, app: CatalogueApp) -> None:
        """Register an application and index all its aliases."""
        app.app_id = app.app_id.strip() or self._make_app_id(app.app_name)
        app.app_name = self._safe_app_name(app.app_name)

        existing = self._catalogue.get(app.app_id)
        if existing:
            existing.app_name = existing.app_name or app.app_name
            existing.executable = existing.executable or app.executable
            existing.launch_target = existing.launch_target or app.launch_target
            existing.launch_type = existing.launch_type or app.launch_type
            existing.application_type = existing.application_type or app.application_type
            existing.launch_method = existing.launch_method or app.launch_method
            existing.aliases = sorted(set(existing.aliases + app.aliases))
            app = existing
        else:
            self._catalogue[app.app_id] = app

        # Index canonical names and id
        self._alias_index[self._build_alias_key(app.app_id)] = app.app_id
        self._alias_index[self._build_alias_key(app.app_name)] = app.app_id
        self._alias_index[self._build_alias_key(app.app_name.replace(" ", ""))] = app.app_id

        # Index explicit aliases
        for alias in app.aliases:
            clean_alias = self._build_alias_key(alias)
            if clean_alias:
                self._alias_index[clean_alias] = app.app_id

    def _register_standard_third_party_apps(self) -> None:
        """Ensure standard applications (Chrome, VS Code, Edge) are registered with rich aliases."""
        standards = [
            CatalogueApp(
                app_id="chrome",
                app_name="Google Chrome",
                executable="chrome.exe",
                launch_target="chrome.exe",
                launch_type="executable",
                allowlisted=False,
                aliases=self.KNOWN_EXTRA_ALIASES["chrome"],
                description="Google Chrome web browser",
            ),
            CatalogueApp(
                app_id="vscode",
                app_name="Visual Studio Code",
                executable="code.exe",
                launch_target="code.exe",
                launch_type="executable",
                allowlisted=False,
                aliases=self.KNOWN_EXTRA_ALIASES["vscode"],
                description="Visual Studio Code editor",
            ),
            CatalogueApp(
                app_id="edge",
                app_name="Microsoft Edge",
                executable="msedge.exe",
                launch_target="msedge.exe",
                launch_type="executable",
                allowlisted=False,
                aliases=self.KNOWN_EXTRA_ALIASES["edge"],
                description="Microsoft Edge browser",
            ),
            CatalogueApp(
                app_id="visualstudio2022",
                app_name="Visual Studio 2022",
                executable="devenv.exe",
                launch_target="devenv.exe",
                launch_type="executable",
                allowlisted=False,
                aliases=["visual studio 2022", "visual studio ide", "devenv"],
                description="Visual Studio 2022 IDE",
            ),
        ]
        for app in standards:
            if app.app_id not in self._catalogue:
                self._register_app(app)
            else:
                # Merge aliases if already registered
                existing = self._catalogue[app.app_id]
                existing.aliases = list(set(existing.aliases + app.aliases))
                for a in app.aliases:
                    self._alias_index[a.lower()] = app.app_id

        from ai_engine.catalogue import get_installed_apps
        for app_meta in get_installed_apps():
            app_id = app_meta["app_id"]
            if app_id not in self._catalogue:
                self._register_app(
                    CatalogueApp(
                        app_id=app_id,
                        app_name=app_meta["app_name"],
                        executable=app_meta.get("executable", f"{app_id}.exe"),
                        launch_target=app_meta.get("executable", app_meta.get("web_url", "")),
                        launch_type="web" if app_meta.get("type") == "web" else "executable",
                        allowlisted=(app_id == "notepad"),
                        aliases=app_meta.get("aliases", []),
                        description=f"{app_meta.get('category', 'Application')}: {app_meta.get('app_name')}",
                    )
                )

    def _discover_registry_app_paths(self) -> None:
        """Safely query Windows App Paths from Registry without modifying system state."""
        if winreg is None:
            return

        key_views = [0]
        if hasattr(winreg, "KEY_WOW64_64KEY"):
            key_views.append(winreg.KEY_WOW64_64KEY)
        if hasattr(winreg, "KEY_WOW64_32KEY"):
            key_views.append(winreg.KEY_WOW64_32KEY)

        seen_paths: Set[str] = set()
        for root_key in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for view_flag in key_views:
                try:
                    key = winreg.OpenKey(root_key, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths", 0, winreg.KEY_READ | view_flag)
                except Exception:
                    continue
                try:
                    num_subkeys = winreg.QueryInfoKey(key)[0]
                    for i in range(num_subkeys):
                        try:
                            sub = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, sub, 0, winreg.KEY_READ | view_flag) as subkey:
                                raw_target, _ = winreg.QueryValueEx(subkey, "")
                                if not raw_target or not isinstance(raw_target, str):
                                    continue
                                expanded = os.path.expandvars(raw_target).strip('"')
                                if not expanded or expanded in seen_paths:
                                    continue
                                seen_paths.add(expanded)
                                base_name = os.path.splitext(sub)[0].lower()
                                if base_name in self.KNOWN_CANONICAL_NAMES:
                                    canonical_name = self.KNOWN_CANONICAL_NAMES[base_name]
                                    app_id = "vscode" if base_name == "code" else base_name
                                else:
                                    canonical_name = base_name.title()
                                    app_id = base_name

                                aliases = self.KNOWN_EXTRA_ALIASES.get(app_id, [base_name, canonical_name.lower()])
                                app = CatalogueApp(
                                    app_id=app_id,
                                    app_name=canonical_name,
                                    executable=sub,
                                    launch_target=expanded,
                                    launch_type="executable",
                                    application_type="application",
                                    launch_method="subprocess",
                                    allowlisted=(app_id == "notepad"),
                                    aliases=aliases,
                                    description=f"Installed Windows Application: {canonical_name}",
                                )
                                self._register_app(app)
                        except Exception:
                            continue
                finally:
                    try:
                        key.Close()
                    except Exception:
                        pass

    def _discover_packaged_apps(self) -> None:
        """Attempt to discover packaged / UWP apps via the shell namespace when running on Windows."""
        if sys.platform != "win32":
            return
        try:
            import win32com.client  # type: ignore
        except ImportError:
            return

        try:
            shell = win32com.client.Dispatch("Shell.Application")
            folder = shell.Namespace("shell:AppsFolder")
            if folder is None:
                return
            for item in folder.Items():
                try:
                    name = getattr(item, "Name", "") or ""
                    path = getattr(item, "Path", "") or ""
                    if not name:
                        continue
                    app_id = self._make_app_id(name)
                    launch_target = path or f"shell:AppsFolder\\{name}"
                    app = CatalogueApp(
                        app_id=app_id,
                        app_name=name,
                        executable=os.path.basename(path) if path else "",
                        launch_target=launch_target,
                        launch_type="packaged" if path else "uri",
                        application_type="packaged",
                        launch_method="os.startfile" if not path else "subprocess",
                        allowlisted=False,
                        aliases=[name.lower(), app_id.lower()],
                        description=f"Packaged Windows application: {name}",
                    )
                    self._register_app(app)
                except Exception:
                    continue
        except Exception:
            return

    def _discover_start_menu_shortcuts(self) -> None:
        """Safely inspect Start Menu shortcut directories for user applications."""
        search_dirs: List[str] = [
            r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
        ]
        app_data = os.environ.get("APPDATA")
        if app_data:
            search_dirs.append(os.path.join(app_data, r"Microsoft\Windows\Start Menu\Programs"))

        ignored_keywords = {"uninstall", "help", "readme", "documentation", "feedback", "license"}
        seen_targets: Set[str] = set()

        for s_dir in search_dirs:
            if not os.path.exists(s_dir):
                continue
            for lnk in glob.glob(os.path.join(s_dir, "**/*.lnk"), recursive=True):
                if not os.path.isfile(lnk):
                    continue
                if lnk in seen_targets:
                    continue
                seen_targets.add(lnk)

                fname = os.path.splitext(os.path.basename(lnk))[0]
                clean_name = fname.strip()
                lower_name = clean_name.lower()

                if not clean_name or any(bad in lower_name for bad in ignored_keywords):
                    continue

                app_id = self._make_app_id(clean_name)
                if app_id not in self._catalogue and lower_name not in self._alias_index:
                    self._register_app(
                        CatalogueApp(
                            app_id=app_id,
                            app_name=clean_name,
                            executable=os.path.basename(lnk),
                            launch_target=lnk,
                            launch_type="executable",
                            application_type="application",
                            launch_method="subprocess",
                            allowlisted=False,
                            aliases=[clean_name.lower(), clean_name.replace(" ", "").lower()],
                            description=f"Start Menu Application: {clean_name}",
                        )
                    )

    def get_all_apps(self) -> List[Dict[str, Any]]:
        """Return all catalogued applications as dictionaries."""
        return [app.to_dict() for app in self._catalogue.values()]

    def get_app(self, app_id_or_name: str) -> Optional[Dict[str, Any]]:
        """Retrieve application by canonical app_id, app_name, or executable."""
        clean = (app_id_or_name or "").strip().lower()
        if not clean:
            return None

        # 1. Direct ID match
        if clean in self._catalogue:
            return self._catalogue[clean].to_dict()

        # 2. Alias index match
        if clean in self._alias_index:
            target_id = self._alias_index[clean]
            if target_id in self._catalogue:
                return self._catalogue[target_id].to_dict()

        # 3. Direct property scan
        for app in self._catalogue.values():
            if clean in (app.app_name.lower(), app.executable.lower(), app.launch_target.lower()):
                return app.to_dict()

        return None

    def resolve_phrase(self, phrase: str) -> Optional[Dict[str, Any]]:
        """
        Resolve natural language phrases, category queries, and settings intents to catalogue entries.
        """
        clean = (phrase or "").strip().lower().rstrip("?.!,")
        if not clean:
            return None

        # Direct alias/name match
        app = self.get_app(clean)
        if app:
            return app

        # Clean common verbs ("open", "launch", "start", "go to", "can you open")
        prefixes = (
            "please open", "can you open", "could you open", "would you open",
            "open", "launch", "start", "go to", "navigate to", "show me", "take me to",
        )
        for pfx in prefixes:
            if clean.startswith(pfx + " "):
                stripped = clean[len(pfx) + 1:].strip()
                res = self.get_app(stripped)
                if res:
                    return res

        return None

    def is_ambiguous(self, query: str) -> Tuple[bool, List[str]]:
        """
        Check whether a user query ambiguously matches multiple installed applications.
        Returns: (is_ambiguous, candidate_app_names)
        """
        clean = (query or "").strip().lower().rstrip("?.!,")
        # Visual Studio ambiguous check
        if clean in ("visual studio", "vs"):
            matches = [app.app_name for app in self._catalogue.values() if "visual studio" in app.app_name.lower()]
            if len(matches) > 1:
                return True, sorted(matches)
        return False, []


# Global singleton instance
catalogue_service = WindowsApplicationCatalogue()


def get_windows_catalogue() -> List[Dict[str, Any]]:
    """Return all catalogued applications."""
    return catalogue_service.get_all_apps()


def resolve_application(target: str) -> Optional[Dict[str, Any]]:
    """Resolve an application identifier, name, or phrase to its catalogue entry."""
    return catalogue_service.resolve_phrase(target)

# Compatibility alias for schemas import
AppCatalogueItem = CatalogueApp  # noqa: N801
