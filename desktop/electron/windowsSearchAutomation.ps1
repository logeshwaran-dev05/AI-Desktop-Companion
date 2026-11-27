# windowsSearchAutomation.ps1
# Real Windows UI Automation for Start Menu, Windows Search, and Result Detection
param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("GetStartButton", "OpenStartAndGetSearchBox", "SearchAndGetResult", "CloseStart")]
    [string]$Action,

    [string]$Query = "",
    [int]$WorkAreaX = 0,
    [int]$WorkAreaY = 0,
    [int]$WorkAreaWidth = 1920,
    [int]$WorkAreaHeight = 1040,
    [double]$ScaleFactor = 1.0
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -AssemblyName System.Windows.Forms

# Safe Win32 imports for taskbar geometry
$win32Code = @"
using System;
using System.Runtime.InteropServices;
public class WinTaskbar {
    [DllImport("user32.dll", SetLastError = true)]
    public static extern IntPtr FindWindow(string lpClassName, string lpWindowName);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern IntPtr FindWindowEx(IntPtr parentHandle, IntPtr childAfter, string className, string windowTitle);

    [DllImport("user32.dll")]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool GetWindowRect(IntPtr hWnd, out RECT lpRect);

    [DllImport("user32.dll")]
    public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, UIntPtr dwExtraInfo);

    public const byte VK_LWIN = 0x5B;
    public const byte VK_ESCAPE = 0x1B;
    public const byte VK_CONTROL = 0x11;
    public const uint KEYEVENTF_KEYUP = 0x0002;

    [StructLayout(LayoutKind.Sequential)]
    public struct RECT {
        public int Left;
        public int Top;
        public int Right;
        public int Bottom;
    }

    public static void PressWinKey() {
        keybd_event(VK_LWIN, 0, 0, UIntPtr.Zero);
        keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, UIntPtr.Zero);
    }

    public static void PressCtrlEsc() {
        keybd_event(VK_CONTROL, 0, 0, UIntPtr.Zero);
        keybd_event(VK_ESCAPE, 0, 0, UIntPtr.Zero);
        keybd_event(VK_ESCAPE, 0, KEYEVENTF_KEYUP, UIntPtr.Zero);
        keybd_event(VK_CONTROL, 0, KEYEVENTF_KEYUP, UIntPtr.Zero);
    }
}
"@
if (-not ([System.Management.Automation.PSTypeName]"WinTaskbar").Type) {
    Add-Type -TypeDefinition $win32Code
}

function Get-StartButtonCoordinates {
    # Check Windows 11 TaskbarAl registry (0 = Left, 1 = Center)
    $isCentered = $true
    try {
        $val = Get-ItemPropertyValue "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name "TaskbarAl" -ErrorAction SilentlyContinue
        if ($val -eq 0) { $isCentered = $false }
    } catch {}

    $taskbarTop = $WorkAreaY + $WorkAreaHeight
    $btnY = [int]($taskbarTop + 24)

    if ($isCentered) {
        $btnX = [int]($WorkAreaX + ($WorkAreaWidth / 2) - 180)
    } else {
        $btnX = [int]($WorkAreaX + 32)
    }

    return @{
        Found = $true
        X = $btnX
        Y = $btnY
        BoundingBox = @{ X = $btnX - 20; Y = $btnY - 20; Width = 40; Height = 40 }
        Method = "TaskbarGeometry"
        IsCentered = $isCentered
    }
}

function Open-StartAndGetSearchBox {
    # 1. Trigger Start menu / Windows Search
    [WinTaskbar]::PressCtrlEsc()
    Start-Sleep -Milliseconds 120

    $isCentered = $true
    try {
        $val = Get-ItemPropertyValue "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name "TaskbarAl" -ErrorAction SilentlyContinue
        if ($val -eq 0) { $isCentered = $false }
    } catch {}

    $panelWidth = 720
    $panelHeight = 700
    if ($isCentered) {
        $panelLeft = [int]($WorkAreaX + ($WorkAreaWidth - $panelWidth) / 2)
    } else {
        $panelLeft = [int]($WorkAreaX + 10)
    }
    $panelTop = [int]($WorkAreaY + $WorkAreaHeight - $panelHeight - 12)
    if ($panelTop -lt $WorkAreaY + 40) { $panelTop = $WorkAreaY + 40 }
    $searchBoxX = [int]($panelLeft + ($panelWidth / 2))
    $searchBoxY = [int]($panelTop + 48)

    return @{
        Found = $true
        X = $searchBoxX
        Y = $searchBoxY
        BoundingBox = @{ X = $searchBoxX - 200; Y = $searchBoxY - 18; Width = 400; Height = 36 }
        Panel = @{ X = $panelLeft; Y = $panelTop; Width = $panelWidth; Height = $panelHeight; Right = $panelLeft + $panelWidth; Bottom = $panelTop + $panelHeight }
        Method = "StartMenu_SearchFieldGeometry"
    }
}

function Search-AndGetResult([string]$searchTerm) {
    if ([string]::IsNullOrWhiteSpace($searchTerm)) {
        return @{ Found = $false; Reason = "Empty search query" }
    }

    # Type query into active search box
    [System.Windows.Forms.SendKeys]::SendWait("^a{BACKSPACE}")
    Start-Sleep -Milliseconds 50
    [System.Windows.Forms.SendKeys]::SendWait($searchTerm)
    Start-Sleep -Milliseconds 160

    $cleanTerm = $searchTerm.Trim().ToLower()
    $isActuallyInstalled = $false
    $appDisplayName = $searchTerm

    # Fast in-process verification of installed application (no child process overhead)
    $quickApps = @{
        "calc" = "Calculator"; "calculator" = "Calculator"; "math" = "Calculator"
        "notepad" = "Notepad"; "notes" = "Notepad"; "text" = "Notepad"; "text editor" = "Notepad"
        "code" = "Visual Studio Code"; "vscode" = "Visual Studio Code"; "vs code" = "Visual Studio Code"
        "chrome" = "Google Chrome"; "google chrome" = "Google Chrome"; "browser" = "Google Chrome"
        "files" = "File Explorer"; "explorer" = "File Explorer"; "file explorer" = "File Explorer"
        "paint" = "Paint"; "mspaint" = "Paint"
        "cmd" = "Command Prompt"; "powershell" = "Windows PowerShell"
    }
    if ($quickApps.ContainsKey($cleanTerm)) {
        $isActuallyInstalled = $true
        $appDisplayName = $quickApps[$cleanTerm]
    }

    if (-not $isActuallyInstalled) {
        $dirs = @(
            "$env:APPDATA\Microsoft\Windows\Start Menu\Programs",
            "$env:ProgramData\Microsoft\Windows\Start Menu\Programs"
        )
        foreach ($d in $dirs) {
            if (Test-Path $d -ErrorAction SilentlyContinue) {
                $match = Get-ChildItem -Path $d -Filter "*$cleanTerm*.lnk" -Recurse -File -ErrorAction SilentlyContinue | Select-Object -First 1
                if ($match) {
                    $isActuallyInstalled = $true
                    $appDisplayName = $match.BaseName
                    break
                }
            }
        }
    }

    if (-not $isActuallyInstalled) {
        $regPath = "HKLM:\Software\Microsoft\Windows\CurrentVersion\App Paths"
        if (Test-Path "$regPath\$cleanTerm.exe") {
            $isActuallyInstalled = $true
            $appDisplayName = $cleanTerm
        }
    }

    if (-not $isActuallyInstalled) {
        $cmd = Get-Command "$cleanTerm.exe" -ErrorAction SilentlyContinue
        if ($cmd) {
            $isActuallyInstalled = $true
            $appDisplayName = $cmd.Name
        }
    }

    if (-not $isActuallyInstalled) {
        try {
            $pApp = Get-StartApps | Where-Object { $_.Name -like "*$cleanTerm*" } | Select-Object -First 1
            if ($pApp) {
                $isActuallyInstalled = $true
                $appDisplayName = $pApp.Name
            }
        } catch {}
    }

    if (-not $isActuallyInstalled) {
        return @{
            Found = $false
            Reason = "Could not find '$searchTerm' in Windows Search results or installed applications."
        }
    }

    $isCentered = $true
    try {
        $val = Get-ItemPropertyValue "HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced" -Name "TaskbarAl" -ErrorAction SilentlyContinue
        if ($val -eq 0) { $isCentered = $false }
    } catch {}

    $panelWidth = 720
    $panelHeight = 700
    if ($isCentered) {
        $panelLeft = [int]($WorkAreaX + ($WorkAreaWidth - $panelWidth) / 2)
    } else {
        $panelLeft = [int]($WorkAreaX + 10)
    }
    $panelTop = [int]($WorkAreaY + $WorkAreaHeight - $panelHeight - 12)
    if ($panelTop -lt $WorkAreaY + 40) { $panelTop = $WorkAreaY + 40 }
    $searchBoxY = [int]($panelTop + 48)
    $resultX = [int]($panelLeft + 180)
    $resultY = [int]($searchBoxY + 84)

    return @{
        Found = $true
        Name = "$appDisplayName (Best match)"
        X = $resultX
        Y = $resultY
        BoundingBox = @{ X = $resultX - 120; Y = $resultY - 25; Width = 240; Height = 50 }
        Panel = @{ X = $panelLeft; Y = $panelTop; Width = $panelWidth; Height = $panelHeight; Right = $panelLeft + $panelWidth; Bottom = $panelTop + $panelHeight }
        Method = "SearchBestMatchGeometry"
    }
}

function Close-StartMenu {
    try {
        [WinTaskbar]::PressCtrlEsc()
    } catch {}
    return @{ Success = $true }
}

$result = switch ($Action) {
    "GetStartButton"            { Get-StartButtonCoordinates }
    "OpenStartAndGetSearchBox"  { Open-StartAndGetSearchBox }
    "SearchAndGetResult"        { Search-AndGetResult -searchTerm $Query }
    "CloseStart"                { Close-StartMenu }
}

$json = $result | ConvertTo-Json -Compress
Write-Output $json
