"""
Windows Native GUI Automation Primitives.
=========================================
Implements pure Windows Win32 API interactions via ctypes:
- Unicode keyboard typing (SendInput)
- Hotkeys and special keys (Ctrl+C, Ctrl+V, Enter, etc.)
- Native Windows Unicode Clipboard Read/Write
- Window focusing and elevation
- Simulated mouse clicks

Zero third-party pip dependencies required; works natively on Windows 10 and 11.
"""

import time
import ctypes
from ctypes import wintypes
from typing import Optional, List, Tuple

# Win32 Constants
INPUT_KEYBOARD = 1
INPUT_MOUSE = 0
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
CF_UNICODETEXT = 13
GMEM_MOVEABLE = 0x0002

# Mouse flags
MOUSEEVENTF_ABSOLUTE = 0x8000
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004

user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None
kernel32 = ctypes.windll.kernel32 if hasattr(ctypes, "windll") else None

if kernel32:
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalUnlock.restype = wintypes.BOOL

if user32:
    user32.GetClipboardData.argtypes = [wintypes.UINT]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.OpenClipboard.restype = wintypes.BOOL
    user32.CloseClipboard.restype = wintypes.BOOL
    user32.EmptyClipboard.restype = wintypes.BOOL


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG),
        ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


class INPUT(ctypes.Structure):
    class _INPUT(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]
    _anonymous_ = ("_input",)
    _fields_ = [("type", wintypes.DWORD), ("_input", _INPUT)]


VK_CODES = {
    "enter": 0x0D,
    "return": 0x0D,
    "tab": 0x09,
    "esc": 0x1B,
    "escape": 0x1B,
    "space": 0x20,
    "backspace": 0x08,
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "shift": 0x10,
    "c": 0x43,
    "v": 0x56,
    "a": 0x41,
    "x": 0x58,
    "s": 0x53,
    "z": 0x5A,
}


def send_unicode_char(char: str) -> None:
    """Send a single Unicode character using SendInput."""
    if not user32:
        return

    code = ord(char)
    inp1 = INPUT(type=INPUT_KEYBOARD)
    inp1.ki.wVk = 0
    inp1.ki.wScan = code
    inp1.ki.dwFlags = KEYEVENTF_UNICODE

    inp2 = INPUT(type=INPUT_KEYBOARD)
    inp2.ki.wVk = 0
    inp2.ki.wScan = code
    inp2.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP

    arr = (INPUT * 2)(inp1, inp2)
    user32.SendInput(2, arr, ctypes.sizeof(INPUT))


def press_vk_key(vk_code: int) -> None:
    """Simulate keydown and keyup for a virtual key code."""
    if not user32:
        return

    inp1 = INPUT(type=INPUT_KEYBOARD)
    inp1.ki.wVk = vk_code
    inp1.ki.dwFlags = 0

    inp2 = INPUT(type=INPUT_KEYBOARD)
    inp2.ki.wVk = vk_code
    inp2.ki.dwFlags = KEYEVENTF_KEYUP

    arr = (INPUT * 2)(inp1, inp2)
    user32.SendInput(2, arr, ctypes.sizeof(INPUT))


def type_text(text: str, press_enter: bool = False, delay: float = 0.01) -> None:
    """
    Type a string into the currently focused window with optional trailing Enter.
    Handles Unicode, punctuation, and multi-line text safely.
    """
    for ch in text:
        if ch == "\n":
            press_vk_key(VK_CODES["enter"])
        elif ch == "\t":
            press_vk_key(VK_CODES["tab"])
        else:
            send_unicode_char(ch)
        if delay > 0:
            time.sleep(delay)

    if press_enter:
        time.sleep(0.05)
        press_vk_key(VK_CODES["enter"])


def press_hotkey(*keys: str) -> None:
    """
    Simulate a hotkey combination like press_hotkey('ctrl', 'c') or press_hotkey('ctrl', 'v').
    """
    if not user32:
        return

    vk_list = [VK_CODES.get(k.lower(), ord(k.upper())) for k in keys]

    # Key down all
    for vk in vk_list:
        inp = INPUT(type=INPUT_KEYBOARD)
        inp.ki.wVk = vk
        inp.ki.dwFlags = 0
        user32.SendInput(1, (INPUT * 1)(inp), ctypes.sizeof(INPUT))
        time.sleep(0.02)

    time.sleep(0.05)

    # Key up in reverse
    for vk in reversed(vk_list):
        inp = INPUT(type=INPUT_KEYBOARD)
        inp.ki.wVk = vk
        inp.ki.dwFlags = KEYEVENTF_KEYUP
        user32.SendInput(1, (INPUT * 1)(inp), ctypes.sizeof(INPUT))
        time.sleep(0.02)


def get_clipboard_text() -> str:
    """Read UTF-16 Unicode text from the Windows Clipboard."""
    if not user32 or not kernel32:
        return ""

    if not user32.OpenClipboard(0):
        return ""

    try:
        h = user32.GetClipboardData(CF_UNICODETEXT)
        if not h:
            return ""
        ptr = kernel32.GlobalLock(h)
        if not ptr:
            return ""
        text = ctypes.wstring_at(ptr)
        kernel32.GlobalUnlock(h)
        return text
    finally:
        user32.CloseClipboard()


def set_clipboard_text(text: str) -> bool:
    """Write UTF-16 Unicode text to the Windows Clipboard."""
    if not user32 or not kernel32:
        return False

    if not user32.OpenClipboard(0):
        return False

    try:
        user32.EmptyClipboard()
        data = text.encode("utf-16le") + b"\x00\x00"
        h = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(data))
        if not h:
            return False
        ptr = kernel32.GlobalLock(h)
        if not ptr:
            return False
        ctypes.memmove(ptr, data, len(data))
        kernel32.GlobalUnlock(h)
        user32.SetClipboardData(CF_UNICODETEXT, h)
        return True
    finally:
        user32.CloseClipboard()


def focus_window_by_title(title_substring: str) -> bool:
    """
    Search all top-level windows for one matching title_substring (case-insensitive)
    and bring it to the foreground.
    """
    if not user32:
        return False

    found_hwnd = None

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def enum_windows_callback(hwnd, _lparam):
        nonlocal found_hwnd
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                if title_substring.lower() in buf.value.lower():
                    found_hwnd = hwnd
                    return False  # stop enumeration
        return True

    user32.EnumWindows(enum_windows_callback, 0)

    if found_hwnd:
        # Restore window if minimized
        SW_RESTORE = 9
        user32.ShowWindow(found_hwnd, SW_RESTORE)
        user32.SetForegroundWindow(found_hwnd)
        time.sleep(0.1)
        return True

    return False
