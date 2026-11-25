# appFinder.ps1
# Discovers installed Windows applications across:
# 1. Start Menu shortcuts (User & System)
# 2. Windows Registered Applications (Uninstall registry)
# 3. App Paths registry entries
# 4. Executables available through PATH
# 5. Windows Packaged Applications (AppUserModelIDs via Get-StartApps)

param(
    [Parameter(Mandatory=$true)]
    [string]$query
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$COMMON_ALIASES = @{
    "calc" = "Calculator"
    "calculator" = "Calculator"
    "math" = "Calculator"
    "notes" = "Notepad"
    "text editor" = "Notepad"
    "notepad" = "Notepad"
    "code" = "Visual Studio Code"
    "vscode" = "Visual Studio Code"
    "vs code" = "Visual Studio Code"
    "chrome" = "Google Chrome"
    "google chrome" = "Google Chrome"
    "browser" = "Google Chrome"
    "terminal" = "Command Prompt"
    "cmd" = "Command Prompt"
    "powershell" = "Windows PowerShell"
    "files" = "File Explorer"
    "explorer" = "File Explorer"
    "paint" = "Paint"
    "mspaint" = "Paint"
}

function Search-InstalledApplications {
    param([string]$target)

    $raw = $target.Trim()
    $cleanLower = $raw.ToLower()

    # Expand alias if known
    $searchTerms = [System.Collections.Generic.List[string]]::new()
    $searchTerms.Add($raw)
    if ($COMMON_ALIASES.ContainsKey($cleanLower)) {
        $searchTerms.Add($COMMON_ALIASES[$cleanLower])
    }
    # Also add stripped version
    $stripped = $cleanLower -replace '[^a-z0-9]', ''
    if ($stripped -and $stripped -ne $cleanLower) {
        $searchTerms.Add($stripped)
    }

    # ─────────────────────────────────────────────────────────────────────────
    # 1. START MENU SHORTCUTS (Current User and All Users)
    # ─────────────────────────────────────────────────────────────────────────
    $startMenuDirs = @(
        "$env:APPDATA\Microsoft\Windows\Start Menu\Programs",
        "$env:ProgramData\Microsoft\Windows\Start Menu\Programs"
    )
    foreach ($term in $searchTerms) {
        $termLower = $term.ToLower()
        foreach ($dir in $startMenuDirs) {
            $dirExists = $false
            try { $dirExists = Test-Path -Path $dir -PathType Container -ErrorAction SilentlyContinue } catch {}
            if ($dirExists) {
                $shortcuts = Get-ChildItem -Path $dir -Recurse -Filter "*.lnk" -ErrorAction SilentlyContinue
                foreach ($lnk in $shortcuts) {
                    $base = $lnk.BaseName.ToLower()
                    if ($base -eq $termLower -or $base.StartsWith($termLower) -or $termLower.StartsWith($base)) {
                        $procList = [System.Collections.Generic.List[string]]::new()
                        $procList.Add("$($lnk.BaseName).exe")
                        $procList.Add("$termLower.exe")

                        # Try to resolve target .exe from .lnk file
                        try {
                            $wsh = New-Object -ComObject WScript.Shell
                            $sc = $wsh.CreateShortcut($lnk.FullName)
                            if ($sc.TargetPath -and $sc.TargetPath.EndsWith(".exe", [System.StringComparison]::OrdinalIgnoreCase)) {
                                $targetExe = [System.IO.Path]::GetFileName($sc.TargetPath)
                                if ($targetExe -and -not $procList.Contains($targetExe)) {
                                    $procList.Add($targetExe)
                                }
                            }
                        } catch {}

                        # Canonical process mappings for common Windows apps
                        if ($termLower -match "chrome") { $procList.Add("chrome.exe") }
                        if ($termLower -match "edge") { $procList.Add("msedge.exe") }
                        if ($termLower -match "code|vscode") { $procList.Add("Code.exe") }
                        if ($termLower -match "notepad") { $procList.Add("notepad.exe") }
                        if ($termLower -match "calc") { $procList.Add("CalculatorApp.exe"); $procList.Add("Calculator.exe") }
                        if ($termLower -match "explorer") { $procList.Add("explorer.exe") }

                        return @{
                            Found = $true
                            Source = "start_menu"
                            SourceDescription = "Start Menu ($($lnk.BaseName))"
                            DisplayName = $lnk.BaseName
                            Path = $lnk.FullName
                            LaunchTarget = $lnk.FullName
                            LaunchType = "shortcut"
                            ProcessNames = $procList.ToArray()
                        }
                    }
                }
            }
        }
    }

    # ─────────────────────────────────────────────────────────────────────────
    # 2. WINDOWS APP PATHS REGISTRY
    # ─────────────────────────────────────────────────────────────────────────
    $appPathsRoots = @(
        "HKLM:\Software\Microsoft\Windows\CurrentVersion\App Paths",
        "HKCU:\Software\Microsoft\Windows\CurrentVersion\App Paths"
    )
    foreach ($term in $searchTerms) {
        $termLower = $term.ToLower()
        foreach ($root in $appPathsRoots) {
            if (Test-Path $root) {
                $subKeys = Get-ChildItem -Path $root -ErrorAction SilentlyContinue
                foreach ($sk in $subKeys) {
                    $keyName = $sk.PSChildName.ToLower()
                    $baseName = $keyName -replace '\.exe$', ''
                    if ($baseName -eq $termLower -or $keyName -eq $termLower -or $keyName -eq "$termLower.exe") {
                        $exePath = (Get-ItemProperty -Path $sk.PSPath -ErrorAction SilentlyContinue).'(default)'
                        if ($exePath) {
                            $exePath = $exePath.Trim('"')
                            if (Test-Path $exePath) {
                                return @{
                                    Found = $true
                                    Source = "app_paths"
                                    SourceDescription = "Windows App Paths Registry ($keyName)"
                                    DisplayName = $term
                                    Path = $exePath
                                    LaunchTarget = $exePath
                                    LaunchType = "executable"
                                    ProcessNames = @([System.IO.Path]::GetFileName($exePath), "$termLower.exe")
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    # ─────────────────────────────────────────────────────────────────────────
    # 3. EXECUTABLES AVAILABLE THROUGH PATH
    # ─────────────────────────────────────────────────────────────────────────
    foreach ($term in $searchTerms) {
        $termLower = $term.ToLower()
        $candidates = @("$termLower.exe", "$termLower.cmd", "$termLower.bat")
        foreach ($cand in $candidates) {
            $cmd = Get-Command $cand -ErrorAction SilentlyContinue
            if ($cmd -and $cmd.Source -and (Test-Path $cmd.Source)) {
                return @{
                    Found = $true
                    Source = "path_executable"
                    SourceDescription = "System PATH ($($cmd.Name))"
                    DisplayName = $term
                    Path = $cmd.Source
                    LaunchTarget = $cmd.Source
                    LaunchType = "executable"
                    ProcessNames = @($cmd.Name, "$termLower.exe")
                }
            }
        }
    }

    # ─────────────────────────────────────────────────────────────────────────
    # 4. WINDOWS PACKAGED APPLICATIONS (AppUserModelIDs via Get-StartApps)
    # ─────────────────────────────────────────────────────────────────────────
    try {
        $startApps = Get-StartApps -ErrorAction SilentlyContinue
        foreach ($term in $searchTerms) {
            $termLower = $term.ToLower()
            foreach ($app in $startApps) {
                $appNameLower = $app.Name.ToLower()
                if ($appNameLower -eq $termLower -or $appNameLower.StartsWith($termLower) -or $termLower.StartsWith($appNameLower)) {
                    $procNames = @("$($app.Name).exe", "$($app.Name)App.exe", "$termLower.exe")
                    if ($app.Name -match "Calculator") {
                        $procNames += @("CalculatorApp.exe", "Calculator.exe", "calc.exe")
                    }
                    if ($app.Name -match "Notepad") {
                        $procNames += @("Notepad.exe", "notepad.exe")
                    }
                    if ($app.Name -match "Explorer") {
                        $procNames += @("explorer.exe", "explorer")
                    }
                    return @{
                        Found = $true
                        Source = "packaged_app"
                        SourceDescription = "Windows Packaged Application ($($app.Name))"
                        DisplayName = $app.Name
                        AppUserModelId = $app.AppID
                        LaunchTarget = "shell:AppsFolder\$($app.AppID)"
                        LaunchType = "packaged_app"
                        ProcessNames = $procNames
                    }
                }
            }
        }
    } catch {}

    # ─────────────────────────────────────────────────────────────────────────
    # 5. WINDOWS REGISTERED APPLICATION ENTRIES (Uninstall Keys)
    # ─────────────────────────────────────────────────────────────────────────
    $uninstallRoots = @(
        "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKLM:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*"
    )
    foreach ($term in $searchTerms) {
        $termLower = $term.ToLower()
        foreach ($root in $uninstallRoots) {
            $items = Get-ItemProperty -Path $root -ErrorAction SilentlyContinue
            foreach ($item in $items) {
                if ($item.DisplayName) {
                    $disp = $item.DisplayName.ToLower()
                    if ($disp -eq $termLower -or $disp.StartsWith($termLower)) {
                        $iconTarget = $item.DisplayIcon
                        if ($iconTarget -and $iconTarget.Contains(",")) {
                            $iconTarget = $iconTarget.Split(",")[0].Trim('"')
                        }
                        if ($iconTarget -and (Test-Path $iconTarget)) {
                            return @{
                                Found = $true
                                Source = "windows_registry"
                                SourceDescription = "Windows Registered Application ($($item.DisplayName))"
                                DisplayName = $item.DisplayName
                                Path = $iconTarget
                                LaunchTarget = $iconTarget
                                LaunchType = "executable"
                                ProcessNames = @([System.IO.Path]::GetFileName($iconTarget), "$termLower.exe")
                            }
                        }
                        if ($item.InstallLocation -and (Test-Path $item.InstallLocation)) {
                            $exes = Get-ChildItem -Path $item.InstallLocation -Filter "*.exe" -ErrorAction SilentlyContinue
                            if ($exes.Count -gt 0) {
                                $mainExe = $exes[0].FullName
                                return @{
                                    Found = $true
                                    Source = "windows_registry"
                                    SourceDescription = "Windows Registered Application ($($item.DisplayName))"
                                    DisplayName = $item.DisplayName
                                    Path = $mainExe
                                    LaunchTarget = $mainExe
                                    LaunchType = "executable"
                                    ProcessNames = @($exes[0].Name, "$termLower.exe")
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    return @{
        Found = $false
        Query = $raw
    }
}

$result = Search-InstalledApplications -target $query
$json = $result | ConvertTo-Json -Compress
Write-Output $json
