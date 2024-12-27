#!/usr/bin/env python3

import os
import sys
import time
import logging
import subprocess
import requests
from datetime import datetime
from pathlib import Path

class VPNTester:
    def __init__(self):
        self.auth_file = "auth.txt"
        self.config_file = "nl-free-2.protonvpn.udp.ovpn"
        self.test_duration = 30
        self.log_file = "vpn_test.log"
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
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
        
        headers = {'User-Agent': 'curl/7.74.0'}  # Some services require a user agent
        
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

    def test_auth_file(self):
        """Test auth.txt file existence and format."""
        self.logger.info("Testing auth file...")
        
        # Check file existence
        if not os.path.exists(self.auth_file):
            self.logger.error(f"Auth file {self.auth_file} does not exist")
            return False
            
        # Check permissions (should be 600)
        perms = oct(os.stat(self.auth_file).st_mode)[-3:]
        if perms != '600':
            self.logger.error(f"Incorrect file permissions: {perms}, should be 600")
            return False
            
        # Check line count
        with open(self.auth_file, 'r') as f:
            lines = f.readlines()
            if len(lines) != 2:
                self.logger.error(f"Auth file should contain exactly 2 lines (found {len(lines)})")
                return False
            
            # Check for empty lines
            if any(not line.strip() for line in lines):
                self.logger.error("Auth file contains empty lines")
                return False
        
        self.logger.info("Auth file validation successful")
        return True

    def test_config_file(self):
        """Test OpenVPN config file existence."""
        self.logger.info("Testing OpenVPN config file...")
        
        if not os.path.exists(self.config_file):
            self.logger.error(f"Config file {self.config_file} does not exist")
            return False
            
        self.logger.info("OpenVPN config file exists")
        return True

    def test_openvpn_installed(self):
        """Test if OpenVPN is installed."""
        self.logger.info("Testing OpenVPN installation...")
        
        try:
            result = subprocess.run(['openvpn', '--version'], 
                                  capture_output=True, 
                                  text=True)
            version = result.stdout.split('\n')[0]
            self.logger.info(f"OpenVPN is installed: {version}")
            return True
        except FileNotFoundError:
            self.logger.error("OpenVPN is not installed")
            return False

    def test_vpn_connection(self):
        """Test VPN connection."""
        self.logger.info("Testing VPN connection...")
        
        # Get initial IP
        initial_ip = self.get_current_ip()
        if not initial_ip:
            return False
        self.logger.info(f"Initial IPv4: {initial_ip}")
        
        # Start OpenVPN with explicit IPv4
        try:
            self.logger.info("Starting OpenVPN connection...")
            process = subprocess.Popen([
                'sudo', 'openvpn',
                '--config', self.config_file,
                '--auth-user-pass', self.auth_file,
                '--daemon',
                '--log', 'openvpn_test.log',
                '--proto', 'udp4'  # Force IPv4
            ])
            
            # Wait for connection
            self.logger.info(f"Waiting {self.test_duration} seconds for connection...")
            time.sleep(self.test_duration)
            
            # Check if OpenVPN is running
            result = subprocess.run(['pgrep', 'openvpn'], capture_output=True)
            if result.returncode != 0:
                self.logger.error("OpenVPN process not running")
                return False
            
            # Multiple attempts to get new IP
            max_attempts = 3
            new_ip = None
            for attempt in range(max_attempts):
                new_ip = self.get_current_ip()
                if new_ip and new_ip != initial_ip:
                    break
                self.logger.info(f"IP hasn't changed yet, attempt {attempt + 1}/{max_attempts}")
                time.sleep(5)
            
            if not new_ip:
                self.logger.error("Failed to get new IP address")
                return False
                
            self.logger.info(f"New IPv4: {new_ip}")
            
            if initial_ip == new_ip:
                self.logger.error("IPv4 address did not change after VPN connection")
                return False
            
            # Check OpenVPN log for successful connection
            with open('openvpn_test.log', 'r') as f:
                log_content = f.read()
                if "Initialization Sequence Completed" not in log_content:
                    self.logger.error("OpenVPN initialization not completed")
                    return False
            
            self.logger.info("VPN connection successful")
            return True
            
        except subprocess.SubprocessError as e:
            self.logger.error(f"Failed to start OpenVPN: {e}")
            return False
        finally:
            # Cleanup
            self.logger.info("Terminating VPN connection...")
            subprocess.run(['sudo', 'killall', 'openvpn'])
            time.sleep(5)
            if os.path.exists('openvpn_test.log'):
                os.remove('openvpn_test.log')

    def run_tests(self):
        """Run all tests."""
        self.logger.info("Starting VPN connection tests")
        failures = 0
        
        # Run sequential tests
        tests = [
            self.test_auth_file,
            self.test_config_file,
            self.test_openvpn_installed
        ]
        
        for test in tests:
            self.logger.info("-" * 40)
            if not test():
                failures += 1
        
        # Only run connection test if previous tests passed
        if failures == 0:
            self.logger.info("-" * 40)
            if not self.test_vpn_connection():
                failures += 1
        else:
            self.logger.warning("Skipping connection test due to previous failures")
        
        self.logger.info("-" * 40)
        if failures == 0:
            self.logger.info("All tests PASSED")
        else:
            self.logger.error(f"FAILED: {failures} test(s) failed")
        
        return failures == 0

if __name__ == "__main__":
    # Check if running as root
    if os.geteuid() != 0:
        print("This script must be run as root (sudo)")
        sys.exit(1)
        
    tester = VPNTester()
    success = tester.run_tests()
    sys.exit(0 if success else 1)