Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class WinInput {
    [DllImport("user32.dll")]
    public static extern void keybd_event(byte bVk, byte bScan, uint dwFlags, int dwExtraInfo);
    public static void TriggerVoiceTyping() {
        keybd_event(0x5B, 0, 0, 0);
        keybd_event(0x48, 0, 0, 0);
        keybd_event(0x48, 0, 2, 0);
        keybd_event(0x5B, 0, 2, 0);
    }
}
"@
[WinInput]::TriggerVoiceTyping()
Write-Output "Win+H triggered successfully"
