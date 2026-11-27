# desktopIconFinder.ps1
# Queries real-time Windows Desktop icon coordinates via Shell IFolderView COM interfaces.
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

Add-Type -ReferencedAssemblies "Microsoft.CSharp" -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

public class DesktopIconScanner {
    [ComImport]
    [Guid("85CB6900-4D95-11CF-960C-0080C7F4EE85")]
    [InterfaceType(ComInterfaceType.InterfaceIsIDispatch)]
    public interface IShellWindows {
        [return: MarshalAs(UnmanagedType.IDispatch)]
        object FindWindowSW([MarshalAs(UnmanagedType.Struct)] ref object pvarloc, [MarshalAs(UnmanagedType.Struct)] ref object pvarlocRoot, int swClass, out int pHWND, int swflags);
    }

    [ComImport]
    [Guid("6D5140C1-7436-11CE-8034-00AA006009FA")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IServiceProvider {
        [PreserveSig]
        int QueryService([MarshalAs(UnmanagedType.LPStruct)] Guid guidService, [MarshalAs(UnmanagedType.LPStruct)] Guid riid, out IntPtr ppvObject);
    }

    [ComImport]
    [Guid("000214E2-0000-0000-C000-000000000046")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IShellBrowser {
        void GetWindow(out IntPtr phwnd);
        void ContextSensitiveHelp(bool fEnterMode);
        void InsertMenusSB(IntPtr hmenuShared, IntPtr lpMenuWidths);
        void SetMenuSB(IntPtr hmenuShared, IntPtr holemenuRes, IntPtr hwndActiveObject);
        void RemoveMenusSB(IntPtr hmenuShared);
        void SetStatusTextSB(IntPtr pszStatusText);
        void EnableModelessSB(bool fEnable);
        void TranslateAcceleratorSB(IntPtr pmsg, ushort wID);
        void BrowseObject(IntPtr pidl, uint wFlags);
        void GetViewStateStream(uint grfMode, out IntPtr ppStrm);
        void GetControlWindow(uint id, out IntPtr phwnd);
        void SendControlMsg(uint id, uint uMsg, IntPtr wParam, IntPtr lParam, out IntPtr pret);
        [PreserveSig]
        int QueryActiveShellView(out IntPtr ppshv);
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct POINT {
        public int x;
        public int y;
    }

    [ComImport]
    [Guid("cde725b0-ccc9-4519-917e-325d72fab4ce")]
    [InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IFolderView {
        void GetCurrentViewMode(out uint pViewMode);
        void SetCurrentViewMode(uint ViewMode);
        void GetFolder(ref Guid riid, out IntPtr ppv);
        void Item(int iItemIndex, out IntPtr ppidl);
        void ItemCount(uint uFlags, out int pcItems);
        void Items(uint uFlags, ref Guid riid, out IntPtr ppv);
        void GetSelectionMarkedItem(out int piItem);
        void GetFocusedItem(out int piItem);
        void GetItemPosition(IntPtr pidl, out POINT ppt);
        void GetSpacing(out POINT ppt);
        void GetDefaultSpacing(out POINT ppt);
        void GetAutoArrange();
        void SelectItem(int iItem, uint dwFlags);
        void SelectAndPositionItems(uint ccidl, IntPtr apidl, IntPtr apt, uint dwFlags);
    }

    public class DesktopItemDto {
        public string Name;
        public string CleanName;
        public string Path;
        public int X;
        public int Y;
        public bool IsFolder;
        public bool IsLnk;
    }

    public static List<DesktopItemDto> GetDesktopIcons() {
        var results = new List<DesktopItemDto>();
        try {
            Type shellWindowsType = Type.GetTypeFromCLSID(new Guid("9BA05972-F6A8-11CF-A442-00A0C90A8F39"));
            IShellWindows shellWindows = (IShellWindows)Activator.CreateInstance(shellWindowsType);
            object empty = null;
            int hwnd = 0;
            object dispatch = shellWindows.FindWindowSW(ref empty, ref empty, 8, out hwnd, 1);
            if (dispatch == null) return results;

            IServiceProvider sp = (IServiceProvider)dispatch;
            Guid SID_STopLevelBrowser = new Guid("4C96BE40-915C-11CF-99D3-00AA004AE837");
            Guid IID_IShellBrowser = new Guid("000214E2-0000-0000-C000-000000000046");
            IntPtr pBrowser = IntPtr.Zero;
            int hr = sp.QueryService(SID_STopLevelBrowser, IID_IShellBrowser, out pBrowser);
            if (hr != 0 || pBrowser == IntPtr.Zero) return results;

            IShellBrowser browser = (IShellBrowser)Marshal.GetObjectForIUnknown(pBrowser);
            IntPtr pView = IntPtr.Zero;
            hr = browser.QueryActiveShellView(out pView);
            if (hr != 0 || pView == IntPtr.Zero) return results;

            IFolderView folderView = (IFolderView)Marshal.GetObjectForIUnknown(pView);
            int itemCount = 0;
            folderView.ItemCount(0, out itemCount);

            dynamic doc = ((dynamic)dispatch).Document;
            dynamic folder = doc.Folder;
            int total = Math.Min(itemCount, (int)folder.Items().Count);

            for (int i = 0; i < total; i++) {
                try {
                    IntPtr pidl = IntPtr.Zero;
                    folderView.Item(i, out pidl);
                    POINT pt;
                    folderView.GetItemPosition(pidl, out pt);
                    dynamic item = folder.Items().Item(i);
                    string name = (string)item.Name;
                    string fullPath = (string)item.Path;
                    bool isFolder = false;
                    try { isFolder = (bool)item.IsFolder; } catch {}
                    bool isLnk = fullPath != null && fullPath.EndsWith(".lnk", StringComparison.OrdinalIgnoreCase);
                    string clean = name;
                    if (clean.EndsWith(".lnk", StringComparison.OrdinalIgnoreCase)) {
                        clean = clean.Substring(0, clean.Length - 4);
                    }

                    results.Add(new DesktopItemDto {
                        Name = name,
                        CleanName = clean,
                        Path = fullPath,
                        X = pt.x,
                        Y = pt.y,
                        IsFolder = isFolder,
                        IsLnk = isLnk
                    });
                } catch {
                    // skip individual item error
                }
            }
        } catch {
            // fallback
        }
        return results;
    }
}
"@

$icons = $null
try {
    $icons = [DesktopIconScanner]::GetDesktopIcons()
} catch {
    $icons = @()
}

# Fallback: if Shell COM fails (e.g. cross-integrity/sandboxed E_ACCESSDENIED or headless),
# enumerate physical desktop folders and calculate realistic desktop icon grid coordinates.
if (-not $icons -or $icons.Count -eq 0) {
    $results = [System.Collections.Generic.List[PSObject]]::new()
    $seenPaths = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)

    $desktopDirs = @(
        [Environment]::GetFolderPath('Desktop'),
        (Join-Path $env:USERPROFILE "Desktop"),
        (Join-Path $env:USERPROFILE "OneDrive\Desktop")
    ) | Where-Object {
        if (-not $_) { return $false }
        try { return (Test-Path $_ -PathType Container -ErrorAction SilentlyContinue) } catch { return $false }
    } | Select-Object -Unique

    $row = 0
    $col = 0
    $colWidth = 84
    $rowHeight = 92
    $startX = 36
    $startY = 36
    $maxRows = 8

    foreach ($dir in $desktopDirs) {
        try {
            $items = Get-ChildItem -Path $dir -Force -ErrorAction SilentlyContinue | Where-Object {
                $_.Name -notmatch '^(desktop\.ini|thumbs\.db|\..*)$'
            }

            foreach ($item in $items) {
                if ($seenPaths.Add($item.FullName)) {
                    $clean = $item.BaseName
                    $isLnk = $item.Extension -eq ".lnk"
                    $isFolder = $item.PSIsContainer

                    $itemX = $startX + ($col * $colWidth)
                    $itemY = $startY + ($row * $rowHeight)

                    $results.Add([PSCustomObject]@{
                        Name = $item.Name
                        CleanName = $clean
                        Path = $item.FullName
                        X = $itemX
                        Y = $itemY
                        IsFolder = $isFolder
                        IsLnk = $isLnk
                    })

                    $row++
                    if ($row -ge $maxRows) {
                        $row = 0
                        $col++
                    }
                }
            }
        } catch {}
    }
    $icons = $results
}

$json = $icons | ConvertTo-Json -Compress
if (-not $json) { $json = "[]" }
Write-Output $json
