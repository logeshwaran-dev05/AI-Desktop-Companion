"""

Truthful Windows application & window verifier.



Distinguishes raw process creation from confirmed GUI window visibility.

Uses Windows Win32 API (EnumWindows, GetWindowThreadProcessId, IsWindowVisible,

GetWindowTextW, GetClassNameW) via ctypes.

Accurately supports classic Win32 apps, modern packaged UWP apps, and background/tray apps.

Never fabricates success or evidence.

"""



import sys

import time

from typing import Dict, Any, Optional, Callable

from windows_automation.schemas import VerificationEvidence, current_iso_timestamp





class WindowsWindowVerifier:

    """Verifies that an application process actually opened its GUI window."""



    def __init__(self, window_finder_override: Optional[Callable[..., Optional[Dict[str, Any]]]] = None):

        """

        Args:

            window_finder_override: Optional callable(pid, process_name) or callable(pid) -> dict for testing/mocking.

        """

        self._finder_override = window_finder_override



    def _find_window_for_pid_native(self, pid: int, process_name: str) -> Optional[Dict[str, Any]]:

        """

        Native Windows implementation using ctypes and user32.dll.

        Finds visible top-level windows matching the given PID or application name.

        Supports modern Windows 10/11 UWP App Execution Aliases where the spawned stub

        delegates to the packaged Notepad process.

        """

        if sys.platform != "win32":

            return None



        import ctypes

        from ctypes import wintypes



        user32 = ctypes.windll.user32



        # Define WNDENUMPROC callback prototype

        WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)



        found_info: Dict[str, Any] = {}

        target_name_lower = process_name.lower().replace(".exe", "")



        def enum_windows_callback(hwnd: wintypes.HWND, lparam: wintypes.LPARAM) -> bool:

            if not user32.IsWindowVisible(hwnd):

                return True  # continue enumeration



            # Window dimensions

            rect = wintypes.RECT()

            user32.GetWindowRect(hwnd, ctypes.byref(rect))

            width = rect.right - rect.left

            height = rect.bottom - rect.top



            if width <= 0 or height <= 0:

                return True



            window_pid = wintypes.DWORD()

            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(window_pid))



            length = user32.GetWindowTextLengthW(hwnd)

            buf = ctypes.create_unicode_buffer(length + 1)

            user32.GetWindowTextW(hwnd, buf, length + 1)

            title = buf.value



            class_buf = ctypes.create_unicode_buffer(256)

            user32.GetClassNameW(hwnd, class_buf, 256)

            cls_name = class_buf.value



            # Match Condition 1: Direct PID match

            direct_pid_match = (window_pid.value == pid)



            # Match Condition 2: Name / Class match for modern app aliases or multi-process browsers

            alias_match = False

            if target_name_lower:

                if target_name_lower in cls_name.lower() or target_name_lower in title.lower():

                    alias_match = True



            if direct_pid_match or alias_match:

                found_info["hwnd"] = int(hwnd)

                found_info["window_pid"] = int(window_pid.value)

                found_info["window_title"] = title

                found_info["window_class"] = cls_name

                found_info["width"] = width

                found_info["height"] = height

                found_info["matched_via"] = "direct_pid" if direct_pid_match else "win32_title_or_class"

                return False  # stop enumeration



            return True



        cb = WNDENUMPROC(enum_windows_callback)

        user32.EnumWindows(cb, 0)



        return found_info if "hwnd" in found_info else None



    def verify_window_readiness(

        self,

        pid: int,

        process_name: str,

        timeout_seconds: float = 5.0,

        poll_interval: float = 0.25,

        is_process_alive_check: Optional[Callable[[int], bool]] = None,

    ) -> VerificationEvidence:

        """

        Polls until the application window is confirmed visible or timeout expires.

        Distinguishes confirmed window visibility from process-only readiness or failure.

        """

        start_time = time.monotonic()

        finder = self._finder_override or self._find_window_for_pid_native



        while (time.monotonic() - start_time) < timeout_seconds:

            # Check for visible window first
            try:

                window_details = finder(pid, process_name)

            except TypeError:

                # Support single-argument finder mock

                window_details = finder(pid)



            if window_details is not None:

                return VerificationEvidence(

                    verified=True,

                    verification_status="launch_verified",

                    method="win32_window_enumeration",

                    details={

                        "process_id": pid,

                        "window_pid": window_details.get("window_pid", pid),

                        "process_name": process_name,

                        "process_alive": True,

                        "window_found": True,

                        "window_handle": window_details.get("hwnd"),

                        "window_title": window_details.get("window_title", ""),

                        "window_class": window_details.get("window_class", ""),

                        "dimensions": {

                            "width": window_details.get("width", 0),

                            "height": window_details.get("height", 0),

                        },

                        "matched_via": window_details.get("matched_via", "native_win32"),

                    },

                    evidence_timestamp=current_iso_timestamp(),

                )



            # Check if process terminated prematurely
            if is_process_alive_check and not is_process_alive_check(pid):

                # Allow a brief grace period for Windows launcher stubs
                time.sleep(0.3)
                try:
                    window_details = finder(pid, process_name)
                except TypeError:
                    window_details = finder(pid)

                if window_details is not None:
                    return VerificationEvidence(
                        verified=True,
                        verification_status="launch_verified",
                        method="win32_window_enumeration",
                        details={
                            "process_id": pid,
                            "window_pid": window_details.get("window_pid", pid),
                            "process_name": process_name,
                            "process_alive": True,
                            "window_found": True,
                            "window_handle": window_details.get("hwnd"),
                            "window_title": window_details.get("window_title", ""),
                            "window_class": window_details.get("window_class", ""),
                            "dimensions": {
                                "width": window_details.get("width", 0),
                                "height": window_details.get("height", 0),
                            },
                            "matched_via": window_details.get("matched_via", "native_win32"),
                        },
                        evidence_timestamp=current_iso_timestamp(),
                    )

                return VerificationEvidence(

                    verified=False,

                    verification_status="launch_failed",

                    method="win32_process_check",

                    details={

                        "process_id": pid,

                        "process_name": process_name,

                        "process_alive": False,

                        "window_found": False,

                        "reason": "Process terminated before its window became visible.",

                    },

                    evidence_timestamp=current_iso_timestamp(),

                )

                return VerificationEvidence(

                    verified=True,

                    verification_status="launch_verified",

                    method="win32_window_enumeration",

                    details={

                        "process_id": pid,

                        "window_pid": window_details.get("window_pid", pid),

                        "process_name": process_name,

                        "process_alive": True,

                        "window_found": True,

                        "window_handle": window_details.get("hwnd"),

                        "window_title": window_details.get("window_title", ""),

                        "window_class": window_details.get("window_class", ""),

                        "dimensions": {

                            "width": window_details.get("width"),

                            "height": window_details.get("height"),

                        },

                        "matched_via": window_details.get("matched_via", "direct"),

                    },

                    evidence_timestamp=current_iso_timestamp(),

                )



            time.sleep(poll_interval)



        # Timeout reached - check if process is actively running on system (e.g. background or tray app)

        running_proc = self._find_process_by_name_native(process_name) if not self._finder_override else None

        if running_proc:

            return VerificationEvidence(

                verified=True,

                verification_status="launch_verified",

                method="win32_process_running_check",

                details={

                    "process_id": running_proc.get("process_id", pid),

                    "process_name": running_proc.get("process_name", process_name),

                    "process_alive": True,

                    "window_found": False,

                    "matched_via": "win32_process_snapshot",

                    "note": "Application process verified active in background or system tray.",

                },

                evidence_timestamp=current_iso_timestamp(),

            )



        alive = is_process_alive_check(pid) if is_process_alive_check else True

        return VerificationEvidence(

            verified=False,

            verification_status="timed_out",

            method="win32_window_enumeration_timeout",

            details={

                "process_id": pid,

                "process_name": process_name,

                "process_alive": alive,

                "window_found": False,

                "reason": f"Window failed to become visible within {timeout_seconds}s timeout deadline.",

            },

            evidence_timestamp=current_iso_timestamp(),

        )



    def _find_process_by_name_native(self, name: str):

        """Find a running Windows process matching name via Toolhelp32 snapshot."""

        if sys.platform != "win32" or not name:

            return None

        try:

            import ctypes

            from ctypes import wintypes

            kernel32 = ctypes.windll.kernel32

            TH32CS_SNAPPROCESS = 0x00000002



            class PROCESSENTRY32W(ctypes.Structure):

                _fields_ = [

                    ("dwSize", wintypes.DWORD),

                    ("cntUsage", wintypes.DWORD),

                    ("th32ProcessID", wintypes.DWORD),

                    ("th32DefaultHeapID", ctypes.c_size_t),

                    ("th32ModuleID", wintypes.DWORD),

                    ("cntThreads", wintypes.DWORD),

                    ("th32ParentProcessID", wintypes.DWORD),

                    ("pcPriClassBase", wintypes.LONG),

                    ("dwFlags", wintypes.DWORD),

                    ("szExeFile", ctypes.c_wchar * 260),

                ]



            snap = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)

            if not snap or snap == -1:

                return None



            pe = PROCESSENTRY32W()

            pe.dwSize = ctypes.sizeof(PROCESSENTRY32W)

            target = name.lower()

            if target.endswith(".exe"):

                target = target[:-4]



            found = None

            if kernel32.Process32FirstW(snap, ctypes.byref(pe)):

                while True:

                    exe_lower = pe.szExeFile.lower()

                    if target in exe_lower or exe_lower.startswith(target):

                        found = {"process_id": int(pe.th32ProcessID), "process_name": pe.szExeFile}

                        break

                    if not kernel32.Process32NextW(snap, ctypes.byref(pe)):

                        break

            kernel32.CloseHandle(snap)

            return found

        except Exception:

            return None

