#!/usr/bin/env python3
"""
Claude Code Notification Toggle Script

Control Claude Code window highlight notification switches.
Supports global and project-level configuration with automatic merging.

Usage:
    python notification_toggle.py --enable [--global]
    python notification_toggle.py --disable [--global]
    python notification_toggle.py --status
    python notification_toggle.py --no-sound [--global]
    python notification_toggle.py --no-highlight [--global]
"""

import json
import argparse
import sys
from pathlib import Path


class ConfigManager:
    """Manage notification configuration with global and project-level support"""

    DEFAULT_CONFIG = {
        "enabled": True,
        "sound_enabled": True,
        "highlight_enabled": True,
        "events": {
            "stop": {"enabled": True, "sound": True, "highlight": True,
                    "flash_count": 5, "highlight_mode": "flash"},
            "tool_complete": {"enabled": True, "sound": True, "highlight": True,
                            "flash_count": 3, "highlight_mode": "flash"},
            "permission": {"enabled": True, "sound": False, "highlight": True,
                         "flash_count": 0, "highlight_mode": "focus"},
            "error": {"enabled": True, "sound": True, "highlight": True,
                     "flash_count": 5, "highlight_mode": "flash"}
        }
    }

    def __init__(self, use_global: bool = False):
        """
        Initialize ConfigManager.

        Args:
            use_global: If True, use global config path; otherwise use project config path
        """
        script_dir = Path(__file__).parent

        if use_global:
            # Global config: ~/.claude/notification_config.json
            home = Path.home()
            self.config_path = home / ".claude" / "notification_config.json"
        else:
            # Project config: .claude/notification_config.json (relative to script)
            self.config_path = script_dir.parent / "notification_config.json"

    @staticmethod
    def get_config_paths():
        """Return tuple of (global_config_path, project_config_path) for status display"""
        script_dir = Path(__file__).parent
        global_path = Path.home() / ".claude" / "notification_config.json"
        project_path = script_dir.parent / "notification_config.json"
        return global_path, project_path

    def load_config(self) -> dict:
        """Load configuration from file, return None if not exists"""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                print(f"Warning: Failed to load config: {e}", file=sys.stderr)
                return None
        return None

    def save_config(self, config: dict) -> bool:
        """Save configuration to file"""
        try:
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            return True
        except IOError as e:
            print(f"Error: Failed to save config to {self.config_path}: {e}", file=sys.stderr)
            return False

    @staticmethod
    def merge_configs(base: dict, override: dict) -> dict:
        """Deep merge override config into base config"""
        result = base.copy()

        if override:
            for key, override_value in override.items():
                base_value = result.get(key)

                if isinstance(base_value, dict) and isinstance(override_value, dict):
                    result[key] = ConfigManager.merge_configs(base_value, override_value)
                else:
                    result[key] = override_value

        return result

    @staticmethod
    def get_merged_config() -> tuple:
        """
        Load and merge global and project configs.

        Returns:
            tuple: (merged_config, global_config, project_config)
        """
        global_path, project_path = ConfigManager.get_config_paths()

        # Load global config
        global_manager = ConfigManager(use_global=True)
        global_config = global_manager.load_config()

        # Load project config
        project_manager = ConfigManager(use_global=False)
        project_config = project_manager.load_config()

        # Start with default or global config
        if global_config:
            merged = global_config
        else:
            merged = ConfigManager.DEFAULT_CONFIG.copy()

        # Merge project config on top
        if project_config:
            merged = ConfigManager.merge_configs(merged, project_config)

        return merged, global_config, project_config

    @staticmethod
    def get_config_source(key: str, global_config: dict, project_config: dict) -> str:
        """Determine which config file provides a given setting"""
        if project_config and key in project_config:
            return "project"
        elif global_config and key in global_config:
            return "global"
        else:
            return "default"

    @staticmethod
    def get_status_display() -> str:
        """Get formatted status display with config sources"""
        lines = []
        lines.append("")
        lines.append("Claude Code Notification Status")
        lines.append("=" * 35)
        lines.append("")

        global_path, project_path = ConfigManager.get_config_paths()
        merged, global_config, project_config = ConfigManager.get_merged_config()

        # Show configuration file status
        lines.append("Configuration Files:")
        if global_path.exists():
            lines.append(f"  [+] Global: {global_path}")
        else:
            lines.append(f"  [ ] Global: {global_path} (not found, using defaults)")

        if project_path.exists():
            lines.append(f"  [+] Project: {project_path}")
        else:
            lines.append(f"  [ ] Project: {project_path} (not found)")

        lines.append("")

        # Get settings
        enabled = merged.get('enabled', True)
        sound_enabled = merged.get('sound_enabled', True)
        highlight_enabled = merged.get('highlight_enabled', True)

        # Main status
        status_icon = "[+]" if enabled else "[ ]"
        source = ConfigManager.get_config_source('enabled', global_config, project_config)
        status_text = "Enabled" if enabled else "Disabled"

        lines.append(f"  {status_icon} Notifications: {status_text}")
        lines.append(f"     (from: {source})")

        if enabled:
            # Sound status
            sound_icon = "[+]" if sound_enabled else "[ ]"
            sound_source = ConfigManager.get_config_source('sound_enabled', global_config, project_config)
            sound_text = "Enabled" if sound_enabled else "Disabled"

            lines.append(f"  {sound_icon} Sound: {sound_text}")
            lines.append(f"     (from: {sound_source})")

            # Highlight status
            highlight_icon = "[+]" if highlight_enabled else "[ ]"
            highlight_source = ConfigManager.get_config_source('highlight_enabled', global_config, project_config)
            highlight_text = "Enabled" if highlight_enabled else "Disabled"

            lines.append(f"  {highlight_icon} Window Highlight: {highlight_text}")
            lines.append(f"     (from: {highlight_source})")

            # Event-specific settings
            events = merged.get('events', {})
            if events:
                lines.append("")
                lines.append("Event Settings:")
                for event_name in ["stop", "tool_complete", "permission", "error"]:
                    if event_name in events:
                        event_config = events[event_name]
                        event_enabled = event_config.get('enabled', True)
                        event_icon = "[+]" if event_enabled else "[ ]"
                        event_sound = event_config.get('sound', True)
                        event_highlight = event_config.get('highlight', True)

                        details = []
                        if event_sound:
                            details.append("sound")
                        if event_highlight:
                            details.append("highlight")
                        details_str = ", ".join(details) if details else "none"

                        lines.append(f"  {event_icon} {event_name}: {details_str}")

        if project_config:
            lines.append("")
            lines.append("Note: Project config is overriding global settings.")
            lines.append("      Use 'disable --project' or delete the project config file to remove overrides.")

        lines.append("")

        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Control Claude Code notification settings',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --status              Show current notification status (merged config)
  %(prog)s --enable              Enable project notifications
  %(prog)s --enable --global     Enable global notifications (default for all projects)
  %(prog)s --disable             Disable project notifications
  %(prog)s --disable --global    Disable global notifications
  %(prog)s --no-sound            Disable sound for current project
  %(prog)s --no-sound --global   Disable sound globally

Configuration levels:
  --global:    ~/.claude/notification_config.json (applies to all projects)
  (no flag):   .claude/notification_config.json (project-specific override)
        """
    )

    parser.add_argument('--enable', action='store_true',
                        help='Enable notifications')
    parser.add_argument('--disable', action='store_true',
                        help='Disable notifications')
    parser.add_argument('--no-sound', action='store_true',
                        help='Disable sound (keep highlight)')
    parser.add_argument('--no-highlight', action='store_true',
                        help='Disable window highlight (keep sound)')
    parser.add_argument('--status', action='store_true',
                        help='Show current status')
    parser.add_argument('--global', action='store_true', dest='use_global',
                        help='Operate on global config instead of project config')
    parser.add_argument('--project', action='store_true', dest='use_project',
                        help='Explicitly operate on project config')

    args = parser.parse_args()

    # Determine which config to operate on
    # --global flag takes priority, --project is explicit (same as default)
    use_global = args.use_global and not args.use_project
    target_type = "Global" if use_global else "Project"

    manager = ConfigManager(use_global=use_global)

    # Handle status (default if no other flags)
    if args.status or not (args.enable or args.disable or args.no_sound or args.no_highlight):
        print(ConfigManager.get_status_display())
        return 0

    # Load existing config or start with default
    config = manager.load_config()
    if config is None:
        config = ConfigManager.DEFAULT_CONFIG.copy()

    # Handle enable
    if args.enable:
        config["enabled"] = True
        config["sound_enabled"] = True
        config["highlight_enabled"] = True
        if manager.save_config(config):
            print(f"[+] {target_type} notifications enabled")
            print(f"    Config: {manager.config_path}")
            return 0
        else:
            print(f"[x] Failed to enable {target_type.lower()} notifications", file=sys.stderr)
            return 1

    # Handle disable
    elif args.disable:
        config["enabled"] = False
        if manager.save_config(config):
            print(f"[ ] {target_type} notifications disabled")
            print(f"    Config: {manager.config_path}")
            return 0
        else:
            print(f"[x] Failed to disable {target_type.lower()} notifications", file=sys.stderr)
            return 1

    # Handle no-sound
    elif args.no_sound:
        config["sound_enabled"] = False
        if manager.save_config(config):
            print(f"[ ] {target_type} sound disabled (window highlight still active)")
            print(f"    Config: {manager.config_path}")
            return 0
        else:
            print(f"[x] Failed to disable {target_type.lower()} sound", file=sys.stderr)
            return 1

    # Handle no-highlight
    elif args.no_highlight:
        config["highlight_enabled"] = False
        if manager.save_config(config):
            print(f"[ ] {target_type} window highlight disabled (sound still active)")
            print(f"    Config: {manager.config_path}")
            return 0
        else:
            print(f"[x] Failed to disable {target_type.lower()} highlight", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
