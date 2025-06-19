#!/usr/bin/env python3
import os
import time
import subprocess
import configparser
import platform
import re
import glob
from pathlib import Path
import logging
import psutil
import argparse
import sys
from threading import Thread, Lock
from datetime import datetime

# Add pynput for mouse and keyboard tracking
try:
    from pynput import mouse, keyboard
    ACTIVITY_TRACKING_AVAILABLE = True
except ImportError:
    ACTIVITY_TRACKING_AVAILABLE = False
    
# Setup logging will be initialized later after parsing command line arguments
logger = logging.getLogger('kicad-wakatime')

class UserActivityTracker:
    def __init__(self, inactivity_threshold=60):
        self.last_activity_time = time.time()
        self.inactivity_threshold = inactivity_threshold
        self.is_active = True
        self.lock = Lock()
        self.tracking_enabled = ACTIVITY_TRACKING_AVAILABLE
        
        if not self.tracking_enabled:
            logger.warning("Activity tracking not available: pynput module not found")
            logger.warning("Install pynput with: pip install pynput")
            logger.warning("Running without activity tracking")
            return
            
        # Start listeners in separate threads
        self.mouse_listener = mouse.Listener(on_move=self.on_activity, 
                                           on_click=self.on_activity, 
                                           on_scroll=self.on_activity)
        self.keyboard_listener = keyboard.Listener(on_press=self.on_activity)
        
        self.mouse_listener.daemon = True
        self.keyboard_listener.daemon = True
        
        self.mouse_listener.start()
        self.keyboard_listener.start()
        
        logger.info("User activity tracking started")
        
    def on_activity(self, *args, **kwargs):
        """Callback for any mouse or keyboard activity"""
        # logger.debug("User activity detected")
        with self.lock:
            self.last_activity_time = time.time()
            self.is_active = True
    
    def check_activity(self):
        """Check if user is currently active based on recent input"""
        if not self.tracking_enabled:
            logger.warning("Activity tracking not enabled, assuming user is active")
            return True  # Assume active if tracking not available
            
        with self.lock:
            current_time = time.time()
            time_since_activity = current_time - self.last_activity_time

            # logger.debug(f"Time since last activity: {time_since_activity:.1f} seconds")

            logger.debug(f"User has been inactive for {time_since_activity:.1f} seconds out of threshold {self.inactivity_threshold} seconds")
            
            # Update active status if we've exceeded the threshold
            if time_since_activity > self.inactivity_threshold:
                if self.is_active:
                    logger.info(f"User inactive for {time_since_activity:.1f} seconds, threshold is {self.inactivity_threshold} seconds")
                self.is_active = False
            
            return self.is_active
    
    def get_time_since_activity(self):
        """Return seconds since last activity"""
        if not self.tracking_enabled:
            return 0  # Assume just active if tracking not available
            
        with self.lock:
            return time.time() - self.last_activity_time
            
    def stop(self):
        """Stop the activity tracking"""
        if self.tracking_enabled:
            self.mouse_listener.stop()
            self.keyboard_listener.stop()
            logger.info("User activity tracking stopped")

class KiCadWakaTime:
    def __init__(self, dry_run=False, inactivity_threshold=60):
        self.last_heartbeat_at = 0
        self.last_file = None
        self.heartbeat_frequency = 60  # seconds
        self.dry_run = dry_run
        
        # Initialize activity tracker
        self.activity_tracker = UserActivityTracker(inactivity_threshold)
        
        if dry_run:
            logger.info("Running in dry run mode - no heartbeats will be sent")
        
        # Find wakatime CLI using glob pattern
        home_dir = str(Path.home())
        wakatime_path = os.path.join(home_dir, '.wakatime')
        
        # Look for wakatime-cli with any extension
        cli_pattern = os.path.join(wakatime_path, 'wakatime-cli*')
        cli_candidates = glob.glob(cli_pattern)
        
        if cli_candidates:
            self.wakatime_cli = cli_candidates[0]  # Use the first match
            logger.info(f"Found WakaTime CLI: {self.wakatime_cli}")
        else:
            logger.error("WakaTime CLI not found in ~/.wakatime/")
            raise Exception("WakaTime CLI not found. Please make sure it's installed in ~/.wakatime/")
        
        # Load WakaTime config
        self.load_wakatime_config()
        
        logger.info("KiCad WakaTime initialized")
        logger.info(f"WakaTime CLI path: {self.wakatime_cli}")

    def get_curr_prj_dir(self, project_name: str):
        """Read from %appdata%/kicad\\9.0\\kicad.json and find the project directory using the project name and json.system.file_history"""
        import json
        
        try:
            # Determine config directory based on OS
            if platform.system() == 'Windows':
                appdata = os.environ.get('APPDATA')
                if appdata is None:
                    raise Exception("APPDATA environment variable not found")
                config_dir = os.path.join(appdata, 'kicad')
            # elif platform.system() == 'Darwin':  # macOS
            #     config_dir = os.path.expanduser('~/Library/Preferences/kicad')
            else:  # Linux and others
                # config_dir = os.path.expanduser('~/.config/kicad')
                logger.warning("Linux/macOS support is not implemented yet. Only Windows is supported for now.")
                return None
            
            # Try to find the KiCad config in different version folders
            kicad_config = None
            version_dirs = ['9.0', '8.0', '7.0', '6.0']
            
            for version in version_dirs:
                version_dir = os.path.join(config_dir, version)
                if os.path.exists(version_dir):
                    for config_file in ['kicad.json']:
                        config_path = os.path.join(version_dir, config_file)
                        if os.path.exists(config_path):
                            logger.debug(f"Found KiCad config at {config_path}")
                            with open(config_path, 'r') as f:
                                kicad_config = json.load(f)
                                break
                    if kicad_config:
                        break
            
            if not kicad_config:
                logger.warning(f"Could not find KiCad config in {config_dir} for versions {version_dirs}")
                return None
            
            prj_file:str = kicad_config["system"]["open_projects"][0]

            # Verify that the project name appears in the project file path
            if project_name.lower() in prj_file.lower():
                # Extract the directory containing the project file
                prj_dir = os.path.dirname(prj_file)
                logger.debug(f"Project directory found: {prj_dir}")
                return prj_dir
            else:
                logger.warning(f"Project name '{project_name}' not found in project file path '{prj_file}'")
                logger.warning("Please close all KiCad instances and try again.")
                return None
        
        except Exception as e:
            logger.error(f"Error matching project directory: {str(e)}")
            return None

    def load_wakatime_config(self):
        """Load API key and URL from ~/.wakatime.cfg"""
        config = configparser.ConfigParser()
        config_file = os.path.expanduser('~/.wakatime.cfg')
        
        try:
            config.read(config_file)
            self.api_key = config.get('settings', 'api_key')
            
            # API URL is optional, use default if not specified
            try:
                self.api_url = config.get('settings', 'api_url')
            except (configparser.NoSectionError, configparser.NoOptionError):
                self.api_url = 'https://api.wakatime.com/api/v1'
                
            logger.info("WakaTime configuration loaded successfully")
        except Exception as e:
            logger.error(f"Error loading WakaTime config: {str(e)}")
            raise Exception(f"Could not load WakaTime configuration: {str(e)}")

    def get_active_kicad_window(self):
        """Get the active KiCad window title and extract file path by checking both window title and executable name"""
        try:
            if platform.system() == 'Windows':
                from win32 import win32gui, win32process
                
                window = win32gui.GetForegroundWindow()
                window_title = win32gui.GetWindowText(window)
                
                # Get process ID and executable name
                _, pid = win32process.GetWindowThreadProcessId(window)
                try:
                    process = psutil.Process(pid)
                    exe_name = process.name().lower()
                    is_kicad_exe = any(k in exe_name for k in ['kicad', 'pcbnew', 'eeschema', 'pcb_editor', 'sch_editor'])
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    is_kicad_exe = False
            
            # Check if it's a KiCad window based on title or executable
            is_kicad_title = any(k in window_title for k in ['KiCad', 'PCB Editor', 'Eeschema', 'Schematic Editor', 'PCBNew', 'Symbol Editor', 'Footprint Editor'])
            
            if is_kicad_title or is_kicad_exe:
                logger.debug(f"KiCad detected - Title match: {is_kicad_title}, Exe match: {is_kicad_exe}")
                
                # First try the old format pattern
                old_format = re.search(r'([^\s/\\]+\.(kicad_pcb|sch|kicad_sch|kicad_pro))(?:\s+-\s+|\s+\[\*\]\s+-\s+)', window_title)
                if old_format:
                    filename = old_format.group(1)
                    # Extract project name from filename (remove extension)
                    project_name = os.path.splitext(filename)[0]
                    return (filename, project_name)
                
                # Try new format: "{if unsaved: * else ""} {project name} — {editor type}"
                new_format = re.search(r'(\*?)([^\s—]+)\s+—\s+(.+)', window_title)
                if new_format:
                    is_unsaved = new_format.group(1) == '*'
                    project_name = new_format.group(2).strip()
                    editor_type = new_format.group(3).strip()

                    file_path = str(self.get_curr_prj_dir(project_name)) + "\\" + project_name
                    
                    # Map editor type to file extension
                    if 'PCB Editor' in editor_type:
                        file_path = f"{file_path}.kicad_pcb"
                    elif 'Schematic Editor' in editor_type:
                        file_path = f"{file_path}.kicad_sch"
                    elif 'KiCad' in editor_type:
                        file_path = f"{file_path}.kicad_pro"
                    elif 'Symbol Editor' in editor_type:
                        logger.warning("Symbol Editor detected file path may not be correct")
                        file_path = f"{file_path}.kicad_sym"
                    elif 'Footprint Editor' in editor_type:
                        logger.warning("Footprint Editor detected file path may not be correct")
                        file_path = f"{file_path}.kicad_mod"

                    return (file_path, project_name)
                
            
            return None
        except Exception as e:
            logger.error(f"Error getting active window: {str(e)}")
            return None

    def send_heartbeat(self, file_info: tuple):
        """Send heartbeat data to WakaTime"""
        if not os.path.exists(self.wakatime_cli) and not self.dry_run:
            logger.error(f"WakaTime CLI not found at {self.wakatime_cli}")
            return
        
        file, project_name = file_info
        
        now = time.time()
        is_user_active = self.activity_tracker.check_activity()
        
        # Only send heartbeat if:
        # 1. The file changed, OR
        # 2. Time since last heartbeat exceeds frequency AND user is active
        if (file != self.last_file) or (now - self.last_heartbeat_at > self.heartbeat_frequency and is_user_active):
            self.last_heartbeat_at = now
            self.last_file = file
            
            cmd = [
                self.wakatime_cli,
                '--entity', file,
                '--plugin', 'kicad-wakatime/0.1.0',
                '--project', project_name,
                '--language', 'KiCad',
                '--key', self.api_key
            ]
            
            if self.api_url:
                cmd.extend(['--api-url', self.api_url])
            
            if self.dry_run:
                logger.info(f"DRY RUN: Would send heartbeat for {file}")
                logger.info(f"DRY RUN: Command: {' '.join(cmd)}")
            else:
                activity_status = "ACTIVE" if is_user_active else "INACTIVE"
                seconds_since_activity = self.activity_tracker.get_time_since_activity()
                logger.info(f"Sending heartbeat for file: {file} (User: {activity_status}, {seconds_since_activity:.1f}s since activity)")
                try:
                    subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    logger.info(f"Heartbeat sent for {file}")
                except Exception as e:
                    logger.error(f"Error sending heartbeat: {str(e)}")
        elif not is_user_active:
            logger.debug(f"Skipping heartbeat: User inactive for {self.activity_tracker.get_time_since_activity():.1f}s")

    def run(self):
        print("Starting KiCad WakaTime integration...")
        """Main loop to monitor KiCad activity"""
        logger.info("Starting KiCad WakaTime monitor")
        try:
            while True:
                active_file = self.get_active_kicad_window()
                if active_file:
                    self.send_heartbeat(active_file)
                time.sleep(5)  # Check every 5 seconds
        except KeyboardInterrupt:
            logger.info("KiCad WakaTime monitor stopped")
            self.activity_tracker.stop()
        except Exception as e:
            logger.error(f"Error in main loop: {str(e)}")
            self.activity_tracker.stop()

if __name__ == "__main__":
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser(description='KiCad WakaTime integration')
        parser.add_argument('--dry-run', action='store_true', help='Run without sending actual heartbeats')
        
        # Add activity tracking options
        parser.add_argument('--inactivity-threshold', type=int, default=60,
                           help='Time in seconds after which user is considered inactive (default: 300)')
        
        # Add logging options
        parser.add_argument('--log-level', choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
                           default='INFO', help='Set the logging level')
        parser.add_argument('--no-file-log', action='store_true', 
                           help='Disable logging to file (log to console only)')
        parser.add_argument('--quiet', action='store_true',
                           help='Suppress console output except for errors')
        
        args = parser.parse_args()
        
        # Configure logging based on command-line arguments
        log_level = getattr(logging, args.log_level)
        
        # Create logger
        logger.setLevel(log_level)
        
        # Create formatters
        file_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        console_formatter = logging.Formatter('%(levelname)s: %(message)s')
        
        # Create handlers
        handlers = []
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(console_formatter)
        if args.quiet:
            console_handler.setLevel(logging.ERROR)  # Only show errors and higher
        else:
            console_handler.setLevel(log_level)
        handlers.append(console_handler)
        
        # File handler (if not disabled)
        if not args.no_file_log:
            log_dir = os.path.expanduser('~/.wakatime')
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, 'kicad-wakatime.log')
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(file_formatter)
            file_handler.setLevel(log_level)
            handlers.append(file_handler)
        
        # Add handlers to logger
        for handler in handlers:
            logger.addHandler(handler)
        
        logger.info(f"Logging initialized at level {args.log_level}")
        if not args.no_file_log:
            logger.info(f"Logging to file: {log_file}")
        
        kicad_wakatime = KiCadWakaTime(dry_run=args.dry_run, 
                                       inactivity_threshold=args.inactivity_threshold)
        kicad_wakatime.run()
    except Exception as e:
        # Ensure there's at least a basic logger for errors
        if not logger.handlers:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
            logger.addHandler(console_handler)
            
        logger.error(f"Failed to start KiCad WakaTime: {str(e)}")
        print(f"Error: {str(e)}")
        sys.exit(1)