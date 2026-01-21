# Claude Code Notification Toggle Script (PowerShell)
# Control Claude Code window highlight notification switches.
# Supports global and project-level configuration.
# Compatible with PowerShell 5.1+

param(
    [switch]$Enable,
    [switch]$Disable,
    [switch]$Status,
    [switch]$NoSound,
    [switch]$NoHighlight,
    [switch]$Global,
    [switch]$Project
)

$ErrorActionPreference = "Stop"

# Determine which config to operate on
$operatingOnGlobal = $Global -and (-not $Project)
$operatingOnProject = $Project -or (-not $Global)

# Config file paths
$globalConfigPath = Join-Path $env:USERPROFILE ".claude\notification_config.json"
$projectConfigPath = Join-Path $PSScriptRoot "..\notification_config.json"

# Default configuration
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

function Get-Config {
    param([string]$Path)

    if (Test-Path $Path) {
        try {
            $json = Get-Content $Path -Raw -Encoding UTF8 | ConvertFrom-Json
            $config = @{}
            $json.PSObject.Properties | ForEach-Object { $config[$_.Name] = $_.Value }
            return $config
        } catch {
            return $null
        }
    }
    return $null
}

function Save-Config {
    param([hashtable]$Config, [string]$Path)

    try {
        $dir = Split-Path $Path -Parent
        if (-not (Test-Path $dir)) {
            New-Item -ItemType Directory -Path $dir -Force | Out-Null
        }
        $Config | ConvertTo-Json -Depth 10 | Set-Content $Path -Encoding UTF8
        return $true
    } catch {
        Write-Error "Failed to save config to $Path`: $_"
        return $false
    }
}

function Merge-Config {
    param([hashtable]$Base, [hashtable]$Override)

    $result = @{}
    foreach ($key in $Base.Keys) {
        $result[$key] = $Base[$key]
    }

    if ($Override) {
        foreach ($key in $Override.Keys) {
            $baseValue = $Base[$key]
            $overrideValue = $Override[$key]

            if ($baseValue -is [hashtable] -and $overrideValue -is [hashtable]) {
                $result[$key] = Merge-Config -Base $baseValue -Override $overrideValue
            } else {
                $result[$key] = $overrideValue
            }
        }
    }

    return $result
}

function Get-MergedConfig {
    $globalConfig = Get-Config -Path $globalConfigPath
    $projectConfig = Get-Config -Path $projectConfigPath

    $mergedConfig = $null

    if ($globalConfig) {
        $mergedConfig = $globalConfig
    } else {
        $mergedConfig = $defaultConfig.Clone()
    }

    if ($projectConfig) {
        $mergedConfig = Merge-Config -Base $mergedConfig -Override $projectConfig
    }

    return $mergedConfig, $globalConfig, $projectConfig
}

function Get-StatusIcon {
    param([bool]$Enabled)
    if ($Enabled) { return "[+]" } else { return "[ ]" }
}

function Get-ConfigSource {
    param([string]$Key, [hashtable]$GlobalConfig, [hashtable]$ProjectConfig)

    if ($ProjectConfig -and $ProjectConfig.ContainsKey($Key)) {
        return "project"
    } elseif ($GlobalConfig -and $GlobalConfig.ContainsKey($Key)) {
        return "global"
    } else {
        return "default"
    }
}

function Show-Status {
    $mergedConfig, $globalConfig, $projectConfig = Get-MergedConfig

    Write-Host ""
    Write-Host "Claude Code Notification Status" -ForegroundColor Cyan
    Write-Host ("=" * 35) -ForegroundColor Cyan
    Write-Host ""

    $enabled = $mergedConfig.enabled -eq $true
    $soundEnabled = $mergedConfig.sound_enabled -eq $true
    $highlightEnabled = $mergedConfig.highlight_enabled -eq $true

    # Show configuration file status
    Write-Host "Configuration Files:" -ForegroundColor Yellow
    if (Test-Path $globalConfigPath) {
        Write-Host "  [+] Global: $globalConfigPath" -ForegroundColor Green
    } else {
        Write-Host "  [ ] Global: $globalConfigPath (not found, using defaults)" -ForegroundColor DarkGray
    }

    if (Test-Path $projectConfigPath) {
        Write-Host "  [+] Project: $projectConfigPath" -ForegroundColor Green
    } else {
        Write-Host "  [ ] Project: $projectConfigPath (not found)" -ForegroundColor DarkGray
    }
    Write-Host ""

    # Main status
    $icon = Get-StatusIcon -Enabled $enabled
    $source = Get-ConfigSource -Key "enabled" -GlobalConfig $globalConfig -ProjectConfig $projectConfig

    if ($enabled) {
        $statusText = "Enabled"
        $color = "Green"
    } else {
        $statusText = "Disabled"
        $color = "Red"
    }

    Write-Host "  $icon Notifications: " -NoNewline
    Write-Host $statusText -ForegroundColor $color
    Write-Host "     (from: $source)" -ForegroundColor DarkGray -NoNewline
    Write-Host ""

    if ($enabled) {
        # Sound status
        $soundIcon = Get-StatusIcon -Enabled $soundEnabled
        $soundSource = Get-ConfigSource -Key "sound_enabled" -GlobalConfig $globalConfig -ProjectConfig $projectConfig

        if ($soundEnabled) {
            $soundColor = "Green"
            $soundText = "Enabled"
        } else {
            $soundColor = "Red"
            $soundText = "Disabled"
        }

        Write-Host "  $soundIcon Sound: " -NoNewline
        Write-Host $soundText -ForegroundColor $soundColor
        Write-Host "     (from: $soundSource)" -ForegroundColor DarkGray -NoNewline
        Write-Host ""

        # Highlight status
        $highlightIcon = Get-StatusIcon -Enabled $highlightEnabled
        $highlightSource = Get-ConfigSource -Key "highlight_enabled" -GlobalConfig $globalConfig -ProjectConfig $projectConfig

        if ($highlightEnabled) {
            $highlightColor = "Green"
            $highlightText = "Enabled"
        } else {
            $highlightColor = "Red"
            $highlightText = "Disabled"
        }

        Write-Host "  $highlightIcon Window Highlight: " -NoNewline
        Write-Host $highlightText -ForegroundColor $highlightColor
        Write-Host "     (from: $highlightSource)" -ForegroundColor DarkGray -NoNewline
        Write-Host ""

        # Event-specific settings
        $events = $mergedConfig.events
        if ($events) {
            Write-Host ""
            Write-Host "Event Settings:" -ForegroundColor Yellow
            $eventNames = @("stop", "tool_complete", "permission", "error")

            foreach ($eventKey in $eventNames) {
                $eventConfig = $events.$eventKey
                if ($eventConfig) {
                    $eventEnabled = $eventConfig.enabled -eq $true
                    $eventIcon = Get-StatusIcon -Enabled $eventEnabled
                    $eventSound = $eventConfig.sound -eq $true
                    $eventHighlight = $eventConfig.highlight -eq $true

                    $details = @()
                    if ($eventSound) { $details += "sound" }
                    if ($eventHighlight) { $details += "highlight" }
                    if ($details.Count -gt 0) {
                        $detailsStr = $details -join ", "
                    } else {
                        $detailsStr = "none"
                    }

                    if ($eventEnabled) {
                        $eventColor = "Green"
                    } else {
                        $eventColor = "Red"
                    }

                    Write-Host "  $eventIcon $eventKey`: " -NoNewline
                    Write-Host $detailsStr -ForegroundColor $eventColor
                }
            }
        }
    }

    if ($projectConfig) {
        Write-Host ""
        Write-Host "Note: Project config is overriding global settings." -ForegroundColor DarkGray
        Write-Host "      Use 'disable --project' to remove project overrides." -ForegroundColor DarkGray
    }

    Write-Host ""
}

# Main logic
$actionTaken = $false

if ($Enable) {
    $targetPath = if ($operatingOnGlobal) { $globalConfigPath } else { $projectConfigPath }
    $targetType = if ($operatingOnGlobal) { "Global" } else { "Project" }

    # Load existing or create new
    $config = Get-Config -Path $targetPath
    if (-not $config) {
        $config = $defaultConfig.Clone()
    }

    $config.enabled = $true
    $config.sound_enabled = $true
    $config.highlight_enabled = $true
    $actionTaken = $true

    if (Save-Config -Config $config -Path $targetPath) {
        Write-Host "[+] $targetType notifications enabled" -ForegroundColor Green
        Write-Host "    Config: $targetPath" -ForegroundColor DarkGray
    } else {
        Write-Host "[x] Failed to enable $targetType notifications" -ForegroundColor Red
        exit 1
    }
}

if ($Disable) {
    $targetPath = if ($operatingOnGlobal) { $globalConfigPath } else { $projectConfigPath }
    $targetType = if ($operatingOnGlobal) { "Global" } else { "Project" }

    # Load existing or create new
    $config = Get-Config -Path $targetPath
    if (-not $config) {
        $config = $defaultConfig.Clone()
    }

    $config.enabled = $false
    $actionTaken = $true

    if (Save-Config -Config $config -Path $targetPath) {
        Write-Host "[ ] $targetType notifications disabled" -ForegroundColor Yellow
        Write-Host "    Config: $targetPath" -ForegroundColor DarkGray
    } else {
        Write-Host "[x] Failed to disable $targetType notifications" -ForegroundColor Red
        exit 1
    }
}

if ($NoSound) {
    $targetPath = if ($operatingOnGlobal) { $globalConfigPath } else { $projectConfigPath }
    $targetType = if ($operatingOnGlobal) { "Global" } else { "Project" }

    $config = Get-Config -Path $targetPath
    if (-not $config) {
        $config = $defaultConfig.Clone()
    }

    $config.sound_enabled = $false
    $actionTaken = $true

    if (Save-Config -Config $config -Path $targetPath) {
        Write-Host "[ ] $targetType sound disabled (window highlight still active)" -ForegroundColor Yellow
        Write-Host "    Config: $targetPath" -ForegroundColor DarkGray
    } else {
        Write-Host "[x] Failed to disable $targetType sound" -ForegroundColor Red
        exit 1
    }
}

if ($NoHighlight) {
    $targetPath = if ($operatingOnGlobal) { $globalConfigPath } else { $projectConfigPath }
    $targetType = if ($operatingOnGlobal) { "Global" } else { "Project" }

    $config = Get-Config -Path $targetPath
    if (-not $config) {
        $config = $defaultConfig.Clone()
    }

    $config.highlight_enabled = $false
    $actionTaken = $true

    if (Save-Config -Config $config -Path $targetPath) {
        Write-Host "[ ] $targetType window highlight disabled (sound still active)" -ForegroundColor Yellow
        Write-Host "    Config: $targetPath" -ForegroundColor DarkGray
    } else {
        Write-Host "[x] Failed to disable $targetType highlight" -ForegroundColor Red
        exit 1
    }
}

# Show status if no action taken or status explicitly requested
if (-not $actionTaken -or $Status) {
    Show-Status
}

exit 0
