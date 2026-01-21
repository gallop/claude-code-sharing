#!/usr/bin/env python3
"""
Claude Code Notification System

Provides window highlighting and sound notifications for Claude Code events.
Supports multi-window detection through process tree traversal and title matching.

Usage:
    python claude_notification.py --event stop
    python claude_notification.py --event tool_complete --tool-name "Bash"
    python claude_notification.py --event permission --highlight-mode focus
"""

import argparse
import json
import logging
import os
import sys
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional, List, Tuple

# Configure logging
script_dir = Path(__file__).parent
log_file = script_dir.parent / "notification_debug.log"

# Add file handler to see what happens during hook calls
file_handler = logging.FileHandler(log_file, encoding='utf-8')
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)
logger.addHandler(file_handler)


class HighlightMode(Enum):
    """Window highlight modes"""
    FLASH = "flash"           # Flash window title bar
    TOPMOST = "topmost"       # Temporarily set window to topmost
    FOCUS = "focus"           # Bring window to foreground
    ALL = "all"               # Combine all methods


@dataclass
class NotificationConfig:
    """Notification configuration"""
    enabled: bool = True
    sound_enabled: bool = True
    highlight_enabled: bool = True
    flash_count: int = 5
    highlight_mode: str = "flash"
    sound_path: Optional[str] = None


class ConfigManager:
    """Manage notification configuration from JSON file"""

    def __init__(self, config_path: Optional[str] = None):
        if config_path:
            self.config_path = Path(config_path)
        else:
            script_dir = Path(__file__).parent
            self.config_path = script_dir.parent / "notification_config.json"

    def load_config(self) -> dict:
        """Load configuration from file"""
        default_config = {
            "enabled": True,
            "sound_enabled": True,
            "highlight_enabled": True,
            "events": {
                "stop": {"enabled": True, "sound": True, "highlight": True, "flash_count": 5, "highlight_mode": "flash"},
                "tool_complete": {"enabled": True, "sound": True, "highlight": True, "flash_count": 3, "highlight_mode": "flash"},
                "permission": {"enabled": True, "sound": False, "highlight": True, "flash_count": 0, "highlight_mode": "focus"},
                "error": {"enabled": True, "sound": True, "highlight": True, "flash_count": 5, "highlight_mode": "flash"}
            }
        }

        if self.config_path.exists():
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load config: {e}, using defaults")
                return default_config
        return default_config

    def get_event_config(self, event_type: str) -> NotificationConfig:
        """Get configuration for specific event type"""
        config = self.load_config()

        if not config.get("enabled", True):
            return NotificationConfig(enabled=False)

        events = config.get("events", {})
        event_config = events.get(event_type, {})

        if not event_config.get("enabled", True):
            return NotificationConfig(enabled=False)

        return NotificationConfig(
            enabled=True,
            sound_enabled=config.get("sound_enabled", True) and event_config.get("sound", True),
            highlight_enabled=config.get("highlight_enabled", True) and event_config.get("highlight", True),
            flash_count=event_config.get("flash_count", 5),
            highlight_mode=event_config.get("highlight_mode", "flash"),
            sound_path=None  # Will be determined by sound file name
        )


try:
    import win32gui
    import win32con
    import win32process
    import psutil
    # Use pygame for more reliable audio playback
    try:
        import pygame
        pygame.mixer.init()
        USE_PYGAME = True
    except ImportError:
        USE_PYGAME = False
        # Fallback to playsound
        try:
            from playsound3 import playsound
        except ImportError:
            try:
                from playsound import playsound
            except ImportError:
                playsound = None
    WINDOWS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Windows dependencies not available: {e}")
    logger.warning("Run: pip install pywin32 pygame psutil")
    WINDOWS_AVAILABLE = False
    USE_PYGAME = False
    playsound = None


class WindowFinder:
    """Find Claude Code window using multiple strategies"""

    # Window titles that indicate Claude Code
    CLAUDE_TITLE_PATTERNS = [
        "Claude",
        "claude",
        "Claude Code",
        "Terminal",
        "Windows Terminal",
        "PowerShell",
        "cmd",
        "Command Prompt"
    ]

    # Patterns that indicate this is NOT a terminal window
    NON_TERMINAL_PATTERNS = [
        "Chrome",
        "Firefox",
        "Edge",
        "Explorer",
        "File Explorer",
        "文件资源管理器",
        "Program Manager",
        "Desktop",
        "Taskbar",
        "Notification",
        "System Tray",
        "Search",
        "Setting",
        "设置"
    ]

    @staticmethod
    def is_claude_window(hwnd: int, title: str, workdir: Optional[str] = None) -> bool:
        """Check if window matches Claude Code criteria"""
        if not title or not title.strip():
            return False

        title_lower = title.lower()

        # Exclude non-terminal windows
        for pattern in WindowFinder.NON_TERMINAL_PATTERNS:
            if pattern.lower() in title_lower:
                return False

        # Must contain a Claude-related pattern
        has_claude_pattern = any(pattern.lower() in title_lower for pattern in WindowFinder.CLAUDE_TITLE_PATTERNS)

        if not has_claude_pattern:
            return False

        # If workdir provided, check if it contains relevant parts
        if workdir:
            # Extract project name from workdir
            workdir_parts = Path(workdir).parts
            # Check if window title contains project folder name
            for part in reversed(workdir_parts):
                if len(part) > 3 and part.lower() in title_lower:
                    return True

        return True

    @staticmethod
    def find_by_title(workdir: Optional[str] = None) -> Optional[int]:
        """Find Claude Code window by title matching"""
        if not WINDOWS_AVAILABLE:
            return None

        # Strategy 1: Find windows by terminal process names (WindowsTerminal.exe, etc.)
        def find_terminal_by_process():
            terminal_process_names = [
                "WindowsTerminal.exe",
                "OpenConsole.exe",  # Windows Console Host
                "conhost.exe",
            ]

            def callback(hwnd, windows):
                try:
                    if win32gui.IsWindowVisible(hwnd):
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                        try:
                            process = psutil.Process(pid)
                            if process.name() in terminal_process_names:
                                title = win32gui.GetWindowText(hwnd)
                                windows.append((hwnd, title, pid))
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            pass
                except:
                    pass
                return True

            windows = []
            win32gui.EnumWindows(callback, windows)
            return windows

        # Try process-based detection first
        terminal_windows = find_terminal_by_process()
        if terminal_windows:
            logger.info(f"Found {len(terminal_windows)} terminal window(s) by process")
            for hwnd, title, pid in terminal_windows:
                logger.info(f"  - HWND: {hwnd}, PID: {pid}, Title: {title}")

            # Return first match (Windows Terminal)
            first_hwnd = terminal_windows[0][0]
            logger.info(f"Returning window HWND: {first_hwnd}")
            return first_hwnd

        # Strategy 2: Fallback to title-based detection
        def find_terminal_by_title():
            def callback(hwnd, windows):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if title:
                        title_lower = title.lower()
                        # Check if it's a Windows Terminal or other terminal
                        is_terminal = any(pattern.lower() in title_lower for pattern in WindowFinder.CLAUDE_TITLE_PATTERNS)
                        # Exclude non-terminal windows
                        is_excluded = any(pattern.lower() in title_lower for pattern in WindowFinder.NON_TERMINAL_PATTERNS)
                        if is_terminal and not is_excluded:
                            windows.append((hwnd, title))
                return True

            windows = []
            win32gui.EnumWindows(callback, windows)
            return windows

        terminal_windows = find_terminal_by_title()
        if terminal_windows:
            # If workdir provided, try to match by path components
            if workdir:
                for hwnd, title in terminal_windows:
                    title_lower = title.lower()
                    # Check if title contains any part of the workdir
                    parts = Path(workdir).parts
                    for part in reversed(parts):
                        if len(part) > 3 and part.lower() in title_lower:
                            logger.info(f"Found terminal window by path match: {title}")
                            return hwnd

            # Return first terminal window as fallback (most likely the active one)
            logger.info(f"Using terminal window: {terminal_windows[0][1]}")
            return terminal_windows[0][0]

        logger.warning("No Claude Code window found by title")
        return None

    @staticmethod
    def find_by_process_tree() -> Optional[int]:
        """Find Claude Code window by traversing process tree"""
        if not WINDOWS_AVAILABLE:
            return None

        try:
            # Get current process
            current_process = psutil.Process()
            logger.info(f"Current process: {current_process.name()} (PID: {current_process.pid})")

            # Walk up the process tree to find terminal parent
            parent = current_process
            seen_pids = set()

            for i in range(10):  # Limit traversal depth
                try:
                    parent = parent.parent()
                    if parent is None or parent.pid in seen_pids:
                        break
                    seen_pids.add(parent.pid)

                    logger.info(f"Parent {i}: {parent.name()} (PID: {parent.pid})")

                    # Check if this process has visible windows
                    hwnd = WindowFinder._find_window_for_pid(parent.pid)
                    if hwnd:
                        logger.info(f"Found window via parent PID {parent.pid}")
                        return hwnd

                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    break

            logger.info("No window found via process tree traversal (expected for hook calls)")
            return None

        except Exception as e:
            logger.error(f"Error in process tree traversal: {e}")
            return None

    @staticmethod
    def _find_window_for_pid(pid: int) -> Optional[int]:
        """Find main window for given process ID"""
        def callback(hwnd, result):
            try:
                _, window_pid = win32process.GetWindowThreadProcessId(hwnd)
                if window_pid == pid and win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if title:  # Has a title
                        # Exclude non-terminal windows
                        title_lower = title.lower()
                        is_non_terminal = any(
                            pattern.lower() in title_lower
                            for pattern in WindowFinder.NON_TERMINAL_PATTERNS
                        )
                        if not is_non_terminal:
                            result.append((hwnd, title))
            except:
                pass
            return True

        windows = []
        win32gui.EnumWindows(callback, windows)

        if windows:
            # Return the window with the largest area (main window)
            windows_with_area = []
            for hwnd, title in windows:
                try:
                    rect = win32gui.GetWindowRect(hwnd)
                    area = (rect[2] - rect[0]) * (rect[3] - rect[1])
                    windows_with_area.append((area, hwnd, title))
                except:
                    windows_with_area.append((0, hwnd, title))

            windows_with_area.sort(reverse=True)
            logger.info(f"Found window for PID {pid}: {windows_with_area[0][2]}")
            return windows_with_area[0][1]

        return None

    @staticmethod
    def get_console_window() -> Optional[int]:
        """Get the console window of the current process"""
        if not WINDOWS_AVAILABLE:
            return None

        try:
            import ctypes
            from ctypes import wintypes

            # GetConsoleWindow returns the handle to the console window
            kernel32 = ctypes.windll.kernel32
            get_console_window = kernel32.GetConsoleWindow
            get_console_window.argtypes = []
            get_console_window.restype = wintypes.HWND

            hwnd = get_console_window()
            if hwnd:
                logger.info(f"Found console window: {hwnd}")
                return hwnd

        except Exception as e:
            logger.debug(f"Could not get console window: {e}")

        return None

    @classmethod
    def find_window(cls, workdir: Optional[str] = None) -> Optional[int]:
        """Find Claude Code window using all available strategies"""
        logger.info("=== Starting window search ===")

        # CRITICAL: Skip get_console_window() for hook calls
        # Hook processes have their own hidden console window, not the visible terminal
        # Check if we're being called from a hook by examining the console window title
        hwnd = cls.get_console_window()
        if hwnd:
            title = win32gui.GetWindowText(hwnd)
            logger.info(f"get_console_window found: HWND={hwnd}, Title='{title}'")
            # Only use console window if it has a title (visible window)
            if title and title.strip():
                logger.info(f"Found via get_console_window: {hwnd}")
                return hwnd
            else:
                logger.info("Console window has no title, likely hidden hook window - skipping")

        # Try process tree traversal
        hwnd = cls.find_by_process_tree()
        if hwnd:
            logger.info(f"Found via process tree: {hwnd}")
            return hwnd

        # Fall back to title matching (most reliable for hook calls)
        logger.info("Falling back to title-based search")
        hwnd = cls.find_by_title(workdir)
        if hwnd:
            logger.info(f"Found via title search: {hwnd}")
        else:
            logger.error("Failed to find any window!")

        return hwnd


class WindowHighlighter:
    """Control window highlighting effects"""

    @staticmethod
    def flash(hwnd: int, count: int = 5, timeout: int = 500) -> bool:
        """Flash window title bar"""
        if not WINDOWS_AVAILABLE:
            return False

        try:
            for i in range(count):
                win32gui.FlashWindow(hwnd, True)
                time.sleep(timeout / 1000)
                win32gui.FlashWindow(hwnd, False)
                if i < count - 1:
                    time.sleep(timeout / 1000)
            return True
        except Exception as e:
            logger.error(f"Flash failed: {e}")
            return False

    @staticmethod
    def flash_ex(hwnd: int, count: int = 5, timeout: int = 500) -> bool:
        """Flash window using FlashWindowEx API with enhanced visibility"""
        if not WINDOWS_AVAILABLE:
            return False

        try:
            import ctypes
            from ctypes import wintypes

            # Verify window is still valid
            if not win32gui.IsWindow(hwnd):
                logger.error(f"Window handle {hwnd} is no longer valid!")
                return False

            class FLASHWINFO(ctypes.Structure):
                _fields_ = [
                    ("cbSize", wintypes.UINT),
                    ("hwnd", wintypes.HWND),
                    ("dwFlags", wintypes.DWORD),
                    ("uCount", wintypes.UINT),
                    ("dwTimeout", wintypes.DWORD),
                ]

            info = FLASHWINFO()
            info.cbSize = ctypes.sizeof(FLASHWINFO)
            info.hwnd = hwnd
            # FLASHW_ALL (3) = flash both caption and taskbar
            # FLASHW_TIMERNOFG (0x0C) = flash until window comes to foreground
            # FLASHW_TIMER (4) = flash continuously for uCount times
            # Combined = 7, flash window and taskbar button uCount times
            info.dwFlags = 0x00000007
            info.uCount = count
            info.dwTimeout = timeout

            logger.info(f"Calling FlashWindowEx: hwnd={hwnd}, count={count}, timeout={timeout}")

            user32 = ctypes.windll.user32
            result = user32.FlashWindowEx(ctypes.byref(info))

            logger.info(f"FlashWindowEx returned: {result}")

            # IMPORTANT: Wait for flash to complete
            # FlashWindowEx is async - if we exit immediately, the effect gets cancelled
            # Total time = count * (timeout + timeout) = count * 2 * timeout ms
            total_wait_time = count * 2 * timeout / 1000
            logger.info(f"Waiting {total_wait_time:.1f}s for flash to complete")
            time.sleep(total_wait_time)

            return True

        except Exception as e:
            logger.warning(f"FlashWindowEx failed, falling back to basic flash: {e}")
            return WindowHighlighter.flash(hwnd, count, timeout)

    @staticmethod
    def bring_to_front(hwnd: int) -> bool:
        """Bring window to foreground"""
        if not WINDOWS_AVAILABLE:
            return False

        try:
            # May need to attach input first
            import win32api
            foreground_thread = win32process.GetWindowThreadProcessId(win32gui.GetForegroundWindow())[0]
            current_thread = win32api.GetCurrentThreadId()
            target_thread = win32process.GetWindowThreadProcessId(hwnd)[0]

            if current_thread != target_thread:
                win32process.AttachThreadInput(current_thread, target_thread, True)
                win32gui.SetForegroundWindow(hwnd)
                win32process.AttachThreadInput(current_thread, target_thread, False)
            else:
                win32gui.SetForegroundWindow(hwnd)

            return True
        except Exception as e:
            logger.error(f"Bring to front failed: {e}")
            # Try simple method as fallback
            try:
                win32gui.SetForegroundWindow(hwnd)
                return True
            except:
                return False

    @staticmethod
    def set_topmost(hwnd: int, topmost: bool = True) -> bool:
        """Set window topmost attribute"""
        if not WINDOWS_AVAILABLE:
            return False

        try:
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOPMOST if topmost else win32con.HWND_NOTOPMOST,
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE
            )
            return True
        except Exception as e:
            logger.error(f"Set topmost failed: {e}")
            return False

    @classmethod
    def highlight(cls, hwnd: int, mode: HighlightMode, flash_count: int = 5) -> bool:
        """Apply window highlighting based on mode"""
        success = False

        logger.info(f"Applying highlight mode: {mode.value}, flash_count: {flash_count}, hwnd: {hwnd}")

        if mode == HighlightMode.FOCUS:
            success = cls.bring_to_front(hwnd)
            logger.info(f"Bring to front result: {success}")
        elif mode == HighlightMode.FLASH:
            success = cls.flash_ex(hwnd, flash_count)
            logger.info(f"Flash result: {success}")
        elif mode == HighlightMode.TOPMOST:
            success = cls.set_topmost(hwnd, True)
            # Reset after delay
            def reset_topmost():
                time.sleep(3)
                cls.set_topmost(hwnd, False)
            threading.Thread(target=reset_topmost, daemon=True).start()
            logger.info(f"Set topmost result: {success}")
        elif mode == HighlightMode.ALL:
            cls.bring_to_front(hwnd)
            time.sleep(0.1)
            success = cls.flash_ex(hwnd, flash_count)
            logger.info(f"ALL mode result: {success}")

        return success


class SoundPlayer:
    """Play notification sounds"""

    def __init__(self, mp3_dir: Optional[Path] = None):
        if mp3_dir:
            self.mp3_dir = mp3_dir
        else:
            script_dir = Path(__file__).parent
            self.mp3_dir = script_dir.parent / "mp3"

    def get_sound_path(self, event_type: str, custom_path: Optional[str] = None) -> Optional[Path]:
        """Get sound file path for event type"""
        if custom_path:
            return Path(custom_path)

        # Map event types to sound files
        sound_files = {
            "stop": "complete.mp3",
            "tool_complete": "tool_complete.mp3",
            "permission": "permission.mp3",
            "error": "error.mp3",
        }

        filename = sound_files.get(event_type, "notice.mp3")
        sound_path = self.mp3_dir / filename

        if sound_path.exists():
            return sound_path

        # Fallback to notice.mp3
        fallback = self.mp3_dir / "notice.mp3"
        if fallback.exists():
            return fallback

        logger.warning(f"Sound file not found: {sound_path}")
        return None

    def play_async(self, sound_path: Path) -> threading.Thread:
        """Play sound in background thread"""
        def play():
            try:
                if USE_PYGAME:
                    # Use pygame for more reliable playback
                    sound = pygame.mixer.Sound(str(sound_path))
                    sound.play()
                    # Wait for sound to finish
                    while pygame.mixer.get_busy():
                        time.sleep(0.1)
                elif playsound is not None:
                    playsound(str(sound_path), block=True)
                else:
                    self.play_beep()
            except Exception as e:
                logger.error(f"Failed to play sound: {e}")
                self.play_beep()

        # Use daemon=False to ensure sound plays completely before program exits
        # This allows sound and highlight to run in parallel
        thread = threading.Thread(target=play, daemon=False)
        thread.start()
        return thread

    def play_beep(self) -> None:
        """Play system beep as fallback"""
        try:
            import winsound
            winsound.Beep(800, 200)
        except:
            print("\a")  # Terminal bell

    def play(self, event_type: str, custom_path: Optional[str] = None) -> None:
        """Play notification sound for event"""
        if not WINDOWS_AVAILABLE:
            return

        sound_path = self.get_sound_path(event_type, custom_path)
        if sound_path:
            logger.info(f"Playing sound: {sound_path.name}")
            self.play_async(sound_path)
        else:
            logger.debug("Using system beep as fallback")
            self.play_beep()


class NotificationManager:
    """Coordinate notification execution"""

    def __init__(self, event_type: str, workdir: Optional[str] = None,
                 highlight_mode: str = "flash", flash_count: int = 5,
                 custom_sound: Optional[str] = None,
                 no_sound: bool = False, no_highlight: bool = False):
        self.event_type = event_type
        self.workdir = workdir
        self.highlight_mode_str = highlight_mode
        self.flash_count = flash_count
        self.custom_sound = custom_sound
        self.no_sound = no_sound
        self.no_highlight = no_highlight

        # Initialize components
        self.config_manager = ConfigManager()
        self.window_finder = WindowFinder()
        self.window_highlighter = WindowHighlighter()
        self.sound_player = SoundPlayer()

    def execute(self) -> int:
        """Execute notification based on configuration"""
        # Load configuration
        config = self.config_manager.get_event_config(self.event_type)

        # Check if notification is enabled
        if not config.enabled:
            logger.info("Notification disabled in config")
            return 0

        # Override with command line flags
        sound_enabled = config.sound_enabled and not self.no_sound
        highlight_enabled = config.highlight_enabled and not self.no_highlight

        if not sound_enabled and not highlight_enabled:
            logger.info("Both sound and highlight disabled")
            return 0

        # Parse highlight mode
        try:
            highlight_mode = HighlightMode(self.highlight_mode_str)
        except ValueError:
            highlight_mode = HighlightMode(config.highlight_mode)

        # Find window
        hwnd = self.window_finder.find_window(self.workdir)
        if not hwnd:
            logger.warning("Could not find Claude Code window")
            # Still play sound if enabled
            sound_thread = None
            if sound_enabled:
                sound_thread = self.sound_player.play(self.event_type, self.custom_sound)
            # Wait for sound to finish
            if sound_thread:
                sound_thread.join(timeout=10)
            return 0

        # Verify window is still valid
        if WINDOWS_AVAILABLE:
            title = win32gui.GetWindowText(hwnd)
            logger.info(f"Target window: HWND={hwnd}, Title='{title}'")
            if not win32gui.IsWindow(hwnd):
                logger.error("Window handle became invalid after find!")
                return 0

        logger.info(f"Executing notification for event: {self.event_type}")

        # Play sound and save thread
        sound_thread = None
        if sound_enabled:
            if self.custom_sound:
                sound_thread = self.sound_player.play(self.event_type, self.custom_sound)
            else:
                sound_thread = self.sound_player.play(self.event_type)

        # Highlight window
        if highlight_enabled:
            flash_count = self.flash_count
            logger.info(f"Starting window highlight: mode={highlight_mode.value}, flash_count={flash_count}")
            self.window_highlighter.highlight(hwnd, highlight_mode, flash_count)
            logger.info("Window highlight completed")

        # Wait for sound to finish (with timeout to prevent hanging)
        if sound_thread and sound_enabled:
            logger.info("Waiting for sound to finish...")
            sound_thread.join(timeout=10)
            logger.info("Sound playback completed")

        return 0


def main():
    parser = argparse.ArgumentParser(
        description='Claude Code Notification System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --event stop
  %(prog)s --event tool_complete --tool-name "Bash"
  %(prog)s --event permission --highlight-mode focus
  %(prog)s --event stop --highlight-mode all --flash-count 5
        """
    )

    parser.add_argument('--event', required=True,
                        choices=['stop', 'tool_complete', 'permission', 'error'],
                        help='Event type triggering the notification')
    parser.add_argument('--tool-name', default='',
                        help='Name of the tool (for tool_complete event)')
    parser.add_argument('--workdir',
                        help='Working directory for window matching')
    parser.add_argument('--highlight-mode', default='flash',
                        choices=['flash', 'topmost', 'focus', 'all'],
                        help='Window highlight mode')
    parser.add_argument('--flash-count', type=int, default=5,
                        help='Number of flash iterations (default: 5)')
    parser.add_argument('--sound',
                        help='Custom sound file path')
    parser.add_argument('--no-sound', action='store_true',
                        help='Disable sound for this notification')
    parser.add_argument('--no-highlight', action='store_true',
                        help='Disable window highlight for this notification')

    args = parser.parse_args()

    # Create and execute notification
    manager = NotificationManager(
        event_type=args.event,
        workdir=args.workdir,
        highlight_mode=args.highlight_mode,
        flash_count=args.flash_count,
        custom_sound=args.sound,
        no_sound=args.no_sound,
        no_highlight=args.no_highlight
    )

    return manager.execute()


if __name__ == "__main__":
    sys.exit(main())
