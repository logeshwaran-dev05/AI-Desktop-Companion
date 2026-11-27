param(
    [string]$query
)

[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

if ([string]::IsNullOrWhiteSpace($query)) {
    Write-Output "[]"
    exit 0
}

$cleanQuery = $query.Trim().ToLower()
$results = [System.Collections.Generic.List[PSObject]]::new()
$seenPaths = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)

# Candidate base search directories
$searchRoots = @(
    (Join-Path $env:USERPROFILE "Desktop"),
    (Join-Path $env:USERPROFILE "OneDrive\Desktop"),
    "C:\Users\Public\Desktop",
    (Join-Path $env:USERPROFILE "Downloads"),
    (Join-Path $env:USERPROFILE "Documents"),
    (Join-Path $env:USERPROFILE "Pictures"),
    (Join-Path $env:USERPROFILE "Videos"),
    (Join-Path $env:USERPROFILE "Music"),
    (Join-Path $env:USERPROFILE "OneDrive"),
    $env:USERPROFILE
)

foreach ($dir in $searchRoots) {
    if (-not $dir) { continue }
    $dirExists = $false
    try { $dirExists = Test-Path -Path $dir -PathType Container -ErrorAction SilentlyContinue } catch {}
    if (-not $dirExists) { continue }

    try {
        # Check direct children first for fast response
        $items = Get-ChildItem -Path $dir -Force -ErrorAction SilentlyContinue | Where-Object {
            $_.Name -notmatch '^\.' -and $_.Name -notmatch '^(AppData|node_modules|__pycache__|\$RECYCLE\.BIN)$'
        }

        foreach ($item in $items) {
            $nameLower = $item.Name.ToLower()
            $baseNameLower = $item.BaseName.ToLower()

            # Check exact match or query match
            $isMatch = ($nameLower -eq $cleanQuery) -or
                       ($baseNameLower -eq $cleanQuery) -or
                       ($nameLower -like "*$cleanQuery*")

            if ($isMatch) {
                if ($seenPaths.Add($item.FullName)) {
                    $results.Add([PSCustomObject]@{
                        name = $item.Name
                        baseName = $item.BaseName
                        path = $item.FullName
                        isFolder = $item.PSIsContainer
                        extension = $item.Extension
                    })
                }
            }
        }
    } catch {}

    if ($results.Count -ge 8) { break }
}

$json = $results | ConvertTo-Json -Compress
if (-not $json) { $json = "[]" }
Write-Output $json
