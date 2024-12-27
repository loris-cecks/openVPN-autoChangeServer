#!/usr/bin/env python3

import os
import sys
import time
import signal
import logging
import subprocess
import requests
from pathlib import Path
from datetime import datetime

class VPNServerChanger:
    def __init__(self):
        # Configuration
        self.script_dir = Path(__file__).parent
        self.config_dir = self.script_dir / "vpn_configs"
        self.config_file = self.config_dir / "nl-free-2.protonvpn.udp.ovpn"
        self.auth_file = self.script_dir / "auth.txt"
        self.check_interval = 1800  # 30 minutes in seconds
        self.recheck_delay = 15     # seconds to wait before checking new IP
        self.log_file = self.script_dir / "vpn_reconnect.log"
        self.temp_log = self.script_dir / "openvpn_temp.log"
        self.max_reconnect_attempts = 3
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s : %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)

    def get_current_ip(self):
        """Get current public IPv4 address using multiple services."""
        ip_services = [
            'https://api.ipify.org?format=text',
            'https://v4.ident.me/',
            'https://ipv4.icanhazip.com/',
            'http://ipv4.whatismyip.akamai.com/'
        ]
        
        headers = {'User-Agent': 'curl/7.74.0'}
        
        for service in ip_services:
            try:
                response = requests.get(service, timeout=5, headers=headers)
                if response.status_code == 200:
                    ip = response.text.strip()
                    # Verify it's an IPv4 address (basic check)
                    if ip.count('.') == 3 and all(part.isdigit() and 0 <= int(part) <= 255 
                                                for part in ip.split('.')):
                        return ip
            except requests.RequestException:
                continue
        
        self.logger.error("Failed to get IPv4 address from all services")
        return None

    def terminate_openvpn(self):
        """Terminate existing OpenVPN processes."""
        self.logger.info("Terminating existing OpenVPN processes...")
        try:
            subprocess.run(['killall', 'openvpn'], check=False)
            time.sleep(5)
            
            # Check if OpenVPN is still running
            result = subprocess.run(['pgrep', 'openvpn'], capture_output=True)
            if result.returncode == 0:
                self.logger.error("Failed to terminate all OpenVPN processes")
                return False
                
            self.logger.info("OpenVPN processes terminated successfully")
            return True
        except subprocess.SubprocessError as e:
            self.logger.error(f"Error terminating OpenVPN: {e}")
            return False

    def reconnect_vpn(self):
        """Reconnect to OpenVPN with specified config file."""
        if not self.config_file.exists():
            self.logger.error(f"Config file {self.config_file} not found")
            return False

        for attempt in range(1, self.max_reconnect_attempts + 1):
            self.logger.info(f"Attempting to reconnect to OpenVPN (Attempt {attempt})")
            
            try:
                subprocess.Popen([
                    'openvpn',
                    '--config', str(self.config_file),
                    '--auth-user-pass', str(self.auth_file),
                    '--daemon',
                    '--log', str(self.temp_log),
                    '--proto', 'udp4'  # Force IPv4
                ])

                time.sleep(10)  # Wait for connection

                if self.temp_log.exists():
                    with open(self.temp_log) as f:
                        if "Initialization Sequence Completed" in f.read():
                            self.logger.info("OpenVPN connected successfully")
                            self.temp_log.unlink(missing_ok=True)
                            return True

                self.logger.error("OpenVPN failed to connect properly")
                self.terminate_openvpn()
                self.temp_log.unlink(missing_ok=True)
                time.sleep(5)

            except subprocess.SubprocessError as e:
                self.logger.error(f"Error during OpenVPN connection: {e}")
                self.temp_log.unlink(missing_ok=True)

        self.logger.error(f"OpenVPN reconnection failed after {self.max_reconnect_attempts} attempts")
        return False

    def handle_vpn_reconnect(self):
        """Handle VPN reconnection and IP check."""
        if not self.terminate_openvpn():
            return False
            
        if not self.reconnect_vpn():
            return False

        self.logger.info(f"Waiting {self.recheck_delay} seconds before checking new IP...")
        time.sleep(self.recheck_delay)

        # Multiple attempts to get new IP
        max_ip_check_attempts = 3
        for attempt in range(max_ip_check_attempts):
            new_ip = self.get_current_ip()
            if new_ip:
                self.logger.info(f"New IP: {new_ip}")
                return True
            self.logger.warning(f"Failed to get IP (attempt {attempt + 1}/{max_ip_check_attempts})")
            time.sleep(5)

        self.logger.error("Failed to get new IP after reconnection")
        return False

    def cleanup(self, signum=None, frame=None):
        """Cleanup function for script termination."""
        self.logger.info("Script interruption requested. Terminating OpenVPN...")
        self.terminate_openvpn()
        self.logger.info("Script terminated")
        sys.exit(0)

    def verify_requirements(self):
        """Verify all required files and commands exist."""
        # Check configuration directory
        if not self.config_dir.exists():
            self.logger.error(f"Configuration directory {self.config_dir} not found")
            return False

        # Check auth file
        if not self.auth_file.exists():
            self.logger.error(f"Credentials file {self.auth_file} not found")
            return False

        # Check required commands
        required_commands = ['openvpn', 'killall', 'pgrep']
        for cmd in required_commands:
            try:
                subprocess.run(['which', cmd], check=True, capture_output=True)
            except subprocess.SubprocessError:
                self.logger.error(f"Command '{cmd}' is not installed")
                return False

        return True

    def run(self):
        """Main execution loop."""
        # Set up signal handlers
        signal.signal(signal.SIGINT, self.cleanup)
        signal.signal(signal.SIGTERM, self.cleanup)

        # Verify requirements
        if not self.verify_requirements():
            sys.exit(1)

        # Get initial IP
        old_ip = self.get_current_ip()
        if not old_ip:
            self.logger.error("Unable to get current IP. Exiting.")
            sys.exit(1)
        self.logger.info(f"Current IP: {old_ip}")

        # Main loop
        while True:
            self.logger.info("Starting reconnection and IP verification process")

            if self.handle_vpn_reconnect():
                new_ip = self.get_current_ip()
                if not new_ip:
                    self.logger.error("Unable to get new IP")
                else:
                    self.logger.info(f"New IP obtained: {new_ip}")

                    if old_ip != new_ip:
                        self.logger.info(f"Success: IP changed from {old_ip} to {new_ip}")
                        old_ip = new_ip
                    else:
                        self.logger.warning("Warning: IP did not change after reconnection")
            else:
                self.logger.error("Reconnection process failed")

            self.logger.info(f"Waiting {self.check_interval} seconds before next attempt")
            time.sleep(self.check_interval)

if __name__ == "__main__":
    # Check if running as root
    if os.geteuid() != 0:
        print("This script must be run as root (sudo)")
        sys.exit(1)

    changer = VPNServerChanger()
    changer.run()