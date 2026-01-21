# Notify Control

Control Claude Code window highlight notification system.

Supports global and project-level configuration with automatic merging.

## Commands

- `enable [--global]`: Enable all notifications (default: project level)
- `disable [--global]`: Disable all notifications (default: project level)
- `status`: Show current notification status (shows merged config)
- `sound-off [--global]`: Disable sound only (keep window highlight)
- `highlight-off [--global]`: Disable window highlight only (keep sound)

## Configuration Levels

The system supports two configuration levels that are automatically merged:

- **Global config** (`--global`): `~/.claude/notification_config.json`
  - Applies to all projects as default settings
  - Use for baseline notification preferences

- **Project config** (default): `.claude/notification_config.json`
  - Overrides global settings for the current project
  - Create project-specific adjustments

## Configuration Merge Logic

```
Global config (defaults)
    ↓
Project config (overrides) - if exists
    ↓
Final effective config
```

Example scenarios:
- No project config → Uses global config (or defaults)
- Project has `{enabled: false}` → Disables notifications for this project only
- Project has `{sound_enabled: false}` → Keeps notifications, but disables sound

## Usage Examples

```bash
# Set global defaults
/notify enable --global

# Check current status (shows merged config and sources)
/notify status

# Disable notifications for a noisy project
/notify disable

# Disable sound globally (keep visual highlights)
/notify sound-off --global

# Re-enable notifications for current project
/notify enable
```

## Implementation

Use the Bash tool to call the Python toggle script:

- `enable`: Run `python .claude/scripts/notification_toggle.py --enable`
- `enable --global`: Run `python .claude/scripts/notification_toggle.py --enable --global`
- `disable`: Run `python .claude/scripts/notification_toggle.py --disable`
- `disable --global`: Run `python .claude/scripts/notification_toggle.py --disable --global`
- `status`: Run `python .claude/scripts/notification_toggle.py --status`
- `sound-off`: Run `python .claude/scripts/notification_toggle.py --no-sound`
- `highlight-off`: Run `python .claude/scripts/notification_toggle.py --no-highlight`

Display the script output to the user.

## Notes

- Global config is created in `~/.claude/` directory automatically on first use
- Project config is created in `.claude/` when you first modify project-level settings
- Status display shows which configuration source each setting comes from (global/project/default)
- To remove project overrides, delete the project config file

## Typical Workflow

1. Set up global defaults for your preferred notification behavior
2. For projects that need adjustments, use project-level commands
3. Use `status` to verify which configuration is active and where it comes from
