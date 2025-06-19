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

# Setup logging will be initialized later after parsing command line arguments
logger = logging.getLogger('kicad-wakatime')

class KiCadWakaTime:
    def __init__(self, dry_run=False):
        self.last_heartbeat_at = 0
        self.last_file = None
        self.heartbeat_frequency = 120  # seconds
        self.dry_run = dry_run
        
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
                    return old_format.group(1)
                
                # Try new format: "{if unsaved: * else ""} {project name} — {editor type}"
                new_format = re.search(r'(\*?)([^\s—]+)\s+—\s+(.+)', window_title)
                if new_format:
                    is_unsaved = new_format.group(1) == '*'
                    project_name = new_format.group(2).strip()
                    editor_type = new_format.group(3).strip()
                    
                    # Map editor type to file extension
                    if 'PCB Editor' in editor_type:
                        return f"{project_name}.kicad_pcb"
                    elif 'Schematic Editor' in editor_type:
                        return f"{project_name}.kicad_sch"
                    elif 'KiCad' in editor_type:
                        return f"{project_name}.kicad_pro"
                    elif 'Symbol Editor' in editor_type:
                        return f"{project_name}.kicad_sym"
                    elif 'Footprint Editor' in editor_type:
                        return f"{project_name}.kicad_mod"
            
            return None
        except Exception as e:
            logger.error(f"Error getting active window: {str(e)}")
            return None

    def send_heartbeat(self, file):
        """Send heartbeat data to WakaTime"""
        if not os.path.exists(self.wakatime_cli) and not self.dry_run:
            logger.error(f"WakaTime CLI not found at {self.wakatime_cli}")
            return
        
        now = time.time()
        if file != self.last_file or now - self.last_heartbeat_at > self.heartbeat_frequency:
            self.last_heartbeat_at = now
            self.last_file = file
            
            cmd = [
                self.wakatime_cli,
                '--entity', file,
                '--plugin', 'kicad-wakatime/0.1.0',
                '--language', 'KiCad',
                '--key', self.api_key
            ]
            
            if self.api_url:
                cmd.extend(['--api-url', self.api_url])
            
            if self.dry_run:
                logger.info(f"DRY RUN: Would send heartbeat for {file}")
                logger.info(f"DRY RUN: Command: {' '.join(cmd)}")
            else:
                logger.info(f"Sending heartbeat for file: {file}")
                try:
                    subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    logger.info(f"Heartbeat sent for {file}")
                except Exception as e:
                    logger.error(f"Error sending heartbeat: {str(e)}")

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
        except Exception as e:
            logger.error(f"Error in main loop: {str(e)}")

if __name__ == "__main__":
    try:
        # Parse command line arguments
        parser = argparse.ArgumentParser(description='KiCad WakaTime integration')
        parser.add_argument('--dry-run', action='store_true', help='Run without sending actual heartbeats')
        
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
        
        kicad_wakatime = KiCadWakaTime(dry_run=args.dry_run)
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