# Claude Code Notification System (PowerShell)
# Zero-dependency notification script for Claude Code events
# Supports MP3 playback
# Compatible with PowerShell 5.1+

param(
    [Parameter(Mandatory=$true)]
    [ValidateSet('stop', 'tool_complete', 'permission', 'error')]
    [string]$Event,

    [string]$ToolName = '',

    [ValidateSet('flash', 'topmost', 'focus', 'all')]
    [string]$HighlightMode = 'flash',

    [int]$FlashCount = 5,

    [string]$Sound,

    [switch]$NoSound,
    [switch]$NoHighlight
)

# Load required assemblies for MP3 playback
try {
    Add-Type -AssemblyName PresentationCore
    Add-Type -AssemblyName WindowsBase
} catch {
    Write-Error "Failed to load required assemblies"
    exit 1
}

#region P/Invoke Win32 API Declarations
$signature = @"
using System;
using System.Runtime.InteropServices;
using System.Text;

public class Win32 {
    [DllImport("user32.dll")]
    public static extern bool FlashWindowEx(ref FLASHWINFO pwfi);

    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool IsWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool IsWindowVisible(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);

    [DllImport("user32.dll")]
    public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);

    [DllImport("user32.dll")]
    public static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint lpdwProcessId);

    [DllImport("user32.dll")]
    public static extern bool SetWindowPos(IntPtr hWnd, IntPtr hWndInsertAfter, int X, int Y, int cx, int cy, uint uFlags);

    [DllImport("kernel32.dll")]
    public static extern IntPtr GetConsoleWindow();

    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    public struct FLASHWINFO {
        public uint cbSize;
        public IntPtr hWnd;
        public uint dwFlags;
        public uint uCount;
        public uint dwTimeout;
    }

    public const uint FLASHW_ALL = 0x00000003;
    public const uint FLASHW_TIMERNOFG = 0x0000000C;
    public const uint FLASHW_TIMER = 0x00000004;
    public const uint SWP_NOMOVE = 0x0002;
    public const uint SWP_NOSIZE = 0x0001;
    public const uint SWP_NOACTIVATE = 0x0010;
    public static readonly IntPtr HWND_TOPMOST = new IntPtr(-1);
    public static readonly IntPtr HWND_NOTOPMOST = new IntPtr(-2);
}
"@

Add-Type -TypeDefinition $signature
#endregion

#region Configuration
function Get-NotificationConfig {
    $configPath = Join-Path $PSScriptRoot "..\notification_config.json"
    $defaultConfig = @{
        enabled = $true
        sound_enabled = $true
        highlight_enabled = $true
        events = @{
            stop = @{ enabled = $true; sound = $true; highlight = $true; flash_count = 5; highlight_mode = "flash" }
            tool_complete = @{ enabled = $true; sound = $true; highlight = $true; flash_count = 3; highlight_mode = "flash" }
            permission = @{ enabled = $true; sound = $false; highlight = $true; flash_count = 0; highlight_mode = "focus" }
            error = @{ enabled = $true; sound = $true; highlight = $true; flash_count = 5; highlight_mode = "flash" }
        }
    }

    if (Test-Path $configPath) {
        try {
            $json = Get-Content $configPath -Raw | ConvertFrom-Json
            $config = @{}
            $json.PSObject.Properties | ForEach-Object { $config[$_.Name] = $_.Value }
            return $config
        } catch {
            return $defaultConfig
        }
    }
    return $defaultConfig
}

function Get-EventConfig {
    param([string]$EventType)

    $config = Get-NotificationConfig

    if (-not $config.enabled) {
        return @{ enabled = $false }
    }

    $eventConfig = $config.events.$EventType
    if (-not $eventConfig -or -not $eventConfig.enabled) {
        return @{ enabled = $false }
    }

    $flashCount = if ($null -ne $eventConfig.flash_count) { $eventConfig.flash_count } else { 5 }
    $highlightMode = if ($eventConfig.highlight_mode) { $eventConfig.highlight_mode } else { "flash" }

    return @{
        enabled = $true
        sound_enabled = $config.sound_enabled -and $eventConfig.sound
        highlight_enabled = $config.highlight_enabled -and $eventConfig.highlight
        flash_count = $flashCount
        highlight_mode = $highlightMode
    }
}
#endregion

#region Window Detection
function Find-ClaudeWindow {
    # Use Get-Process to find terminal windows
    $terminalProcesses = @('WindowsTerminal', 'OpenConsole', 'conhost')

    try {
        foreach ($procName in $terminalProcesses) {
            $processes = Get-Process -Name $procName -ErrorAction SilentlyContinue
            if ($processes) {
                foreach ($proc in $processes) {
                    if ($proc.MainWindowHandle -ne [IntPtr]::Zero) {
                        $title = $proc.MainWindowTitle
                        if ($title -and $title.Trim() -ne "") {
                            return $proc.MainWindowHandle
                        }
                    }
                }
            }
        }
    } catch {
        # Silently ignore errors
    }

    return [IntPtr]::Zero
}
#endregion

#region Window Highlight
function Set-WindowFlash {
    param([IntPtr]$hWnd, [int]$Count = 5, [int]$Timeout = 500)

    if ($hWnd -eq [IntPtr]::Zero) { return $false }

    try {
        if (-not [Win32]::IsWindow($hWnd)) { return $false }

        $flashInfo = New-Object Win32+FLASHWINFO
        $flashInfo.cbSize = [System.Runtime.InteropServices.Marshal]::SizeOf($flashInfo)
        $flashInfo.hWnd = $hWnd
        $flashInfo.dwFlags = 0x00000007  # FLASHW_ALL | FLASHW_TIMER
        $flashInfo.uCount = $Count
        $flashInfo.dwTimeout = $Timeout

        [Win32]::FlashWindowEx([ref]$flashInfo) | Out-Null

        # FlashWindowEx is async - it runs in background and returns immediately
        # No need to wait, allowing parallel execution with audio

        return $true
    } catch {
        return $false
    }
}

function Set-WindowFocus {
    param([IntPtr]$hWnd)

    if ($hWnd -eq [IntPtr]::Zero) { return $false }

    try {
        return [Win32]::SetForegroundWindow($hWnd)
    } catch {
        return $false
    }
}

function Set-WindowTopmost {
    param([IntPtr]$hWnd, [bool]$Topmost = $true)

    if ($hWnd -eq [IntPtr]::Zero) { return $false }

    try {
        $insertAfter = if ($Topmost) { [Win32]::HWND_TOPMOST } else { [Win32]::HWND_NOTOPMOST }
        $flags = 0x0003 -bor 0x0010  # SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
        return [Win32]::SetWindowPos($hWnd, $insertAfter, 0, 0, 0, 0, $flags)
    } catch {
        return $false
    }
}

function Invoke-WindowHighlight {
    param([IntPtr]$hWnd, [string]$Mode, [int]$FlashCount)

    if ($hWnd -eq [IntPtr]::Zero) { return $false }

    $result = $false
    switch ($Mode) {
        'focus' {
            $result = Set-WindowFocus -hWnd $hWnd
        }
        'flash' {
            $result = Set-WindowFlash -hWnd $hWnd -Count $FlashCount
        }
        'topmost' {
            Set-WindowTopmost -hWnd $hWnd -Topmost $true
            $result = $true
            # Schedule reset after delay (don't block - let main thread handle audio)
            # The window will stay topmost briefly, then script exits and resets
        }
        'all' {
            Set-WindowFocus -hWnd $hWnd
            $result = Set-WindowFlash -hWnd $hWnd -Count $FlashCount
        }
        default {
            $result = Set-WindowFlash -hWnd $hWnd -Count $FlashCount
        }
    }

    return $result
}
#endregion

#region Sound Playback
function Play-NotificationSound {
    param([string]$EventType, [string]$CustomSound = '')

    $soundPath = $null

    if ($CustomSound -and (Test-Path $CustomSound)) {
        $soundPath = $CustomSound
    } else {
        # Map event types to sound files
        $soundFiles = @{
            stop = "complete.mp3"
            tool_complete = "tool_complete.mp3"
            permission = "permission.mp3"
            error = "error.mp3"
        }

        $filename = $soundFiles[$EventType]
        if (-not $filename) { $filename = "notice.mp3" }

        $mp3Dir = Join-Path $PSScriptRoot "..\mp3"
        $soundPath = Join-Path $mp3Dir $filename

        if (-not (Test-Path $soundPath)) {
            $soundPath = Join-Path $mp3Dir "notice.mp3"
        }

        if (-not (Test-Path $soundPath)) {
            # Fallback to system sound
            try {
                [System.Media.SystemSounds]::Beep.Play()
            } catch {
                [Console]::Beep(800, 200)
            }
            return
        }
    }

    # Resolve to absolute path
    $soundPath = (Resolve-Path $soundPath).Path
    $extension = [System.IO.Path]::GetExtension($soundPath).ToLower()
    $soundPlayed = $false

    if ($extension -eq '.mp3') {
        # Use MediaPlayer for MP3 files
        try {
            $mediaPlayer = New-Object System.Windows.Media.MediaPlayer
            $mediaPlayer.Open([uri]"file:///$soundPath")

            # Wait for media to open and get duration
            $timeout = 50
            $counter = 0
            while ($mediaPlayer.NaturalDuration.HasTimeSpan -eq $false -and $counter -lt $timeout) {
                Start-Sleep -Milliseconds 100
                $counter++
            }

            if ($mediaPlayer.NaturalDuration.HasTimeSpan) {
                $duration = $mediaPlayer.NaturalDuration.TimeSpan.TotalMilliseconds
            } else {
                $duration = 2000  # Default 2 seconds if can't get duration
            }

            $mediaPlayer.Play()

            # Wait for playback to complete
            Start-Sleep -Milliseconds $duration

            $mediaPlayer.Close()
            $soundPlayed = $true
        } catch {
            $soundPlayed = $false
        }
    } elseif ($extension -eq '.wav') {
        # Use SoundPlayer for WAV files
        try {
            $player = New-Object System.Media.SoundPlayer($soundPath)
            $player.PlaySync()
            $soundPlayed = $true
        } catch {
            $soundPlayed = $false
        }
    }

    # Fallback to system beep if sound playback failed
    if (-not $soundPlayed) {
        try {
            [System.Media.SystemSounds]::Beep.Play()
        } catch {
            [Console]::Beep(800, 200)
        }
    }
}
#endregion

#region Main Execution
function Invoke-Notification {
    # Get event configuration
    $eventConfig = Get-EventConfig -EventType $Event

    if (-not $eventConfig.enabled) {
        return 0
    }

    # Apply command line overrides
    $soundEnabled = $eventConfig.sound_enabled -and -not $NoSound
    $highlightEnabled = $eventConfig.highlight_enabled -and -not $NoHighlight

    if (-not $soundEnabled -and -not $highlightEnabled) {
        return 0
    }

    # Use highlight mode from config if not specified
    $effectiveMode = if ($HighlightMode -eq 'flash') { $eventConfig.highlight_mode } else { $HighlightMode }
    $effectiveFlashCount = if ($FlashCount -gt 0) { $FlashCount } else { $eventConfig.flash_count }

    # Find Claude Code window
    $hWnd = Find-ClaudeWindow

    # Start window highlight FIRST (async, returns immediately)
    # This allows highlighting to run in parallel with audio playback
    if ($highlightEnabled -and $hWnd -ne [IntPtr]::Zero) {
        Invoke-WindowHighlight -hWnd $hWnd -Mode $effectiveMode -FlashCount $effectiveFlashCount
    }

    # Play sound SECOND (blocking, ensures full playback)
    # Keeping this on main thread prevents audio from being cut off
    if ($soundEnabled) {
        if ($Sound) {
            Play-NotificationSound -EventType $Event -CustomSound $Sound
        } else {
            Play-NotificationSound -EventType $Event
        }
    }

    return 0
}

# Execute notification
exit (Invoke-Notification)
#endregion
