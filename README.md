# OpenVPN Auto Change Server Script

## Description
`change_vpn_server.sh` is a Bash script that automates reconnecting to OpenVPN servers, verifies the IP address change (IPv4 only), and logs all activities.

The script terminates any existing OpenVPN processes, reconnects using a specified configuration file, and checks if the public IP has successfully changed. It's useful for maintaining privacy and periodically switching servers.

---

## Project Structure
```plaintext
project-folder/
├── change_vpn_server.sh      # Main script
├── vpn_configs/              # Directory containing .ovpn configuration files
│   └── it.protonvpn.udp.ovpn # Example configuration file
├── auth.txt                  # Credentials file (excluded from the repository)
└── vpn_reconnect.log         # Log file generated by the script
```

---

## Requirements
- **Operating System**: Linux (tested on Ubuntu/Kubuntu)
- **OpenVPN**: OpenVPN client installed
- **curl**: To retrieve the current IP address
- **killall**: To terminate OpenVPN processes
- **logger**: For system logging
- **auth.txt**: File containing VPN credentials

---

## Configuration
1. **OpenVPN Configuration File**:
   Place the OpenVPN `.ovpn` configuration file in the `vpn_configs/` directory.

2. **Credentials File**:
   Create an `auth.txt` file with the following format:
   ```plaintext
   username
   password
   ```

   Secure the credentials file:
   ```bash
   chmod 600 auth.txt
   ```

3. **Make the Script Executable**:
   Ensure the script has execution permissions:
   ```bash
   chmod +x change_vpn_server.sh
   ```

---

## Usage
Run the script with the following command:

```bash
./change_vpn_server.sh
```

### Script Workflow:
1. Terminates any existing OpenVPN processes.
2. Reconnects using the specified `.ovpn` file and `auth.txt` for credentials.
3. Verifies the public IP change.
4. Logs all activities to `vpn_reconnect.log` and the system logger.
5. Repeats the process every 30 minutes (default, configurable).

---

## Key Parameters
- **`CONFIG_FILE`**: Path to the OpenVPN configuration file.
- **`AUTH_FILE`**: Path to the credentials file.
- **`CHECK_INTERVAL`**: Time interval between reconnect attempts (default: 30 minutes).
- **`RECHECK_DELAY`**: Delay before verifying the new IP (default: 15 seconds).
- **`MAX_RECONNECT_ATTEMPTS`**: Maximum number of reconnection attempts (default: 3).

---

## Example Log Output
Example entries in the `vpn_reconnect.log` file:
```plaintext
2024-06-15 12:00:00 : Terminating existing OpenVPN processes...
2024-06-15 12:00:05 : Attempting OpenVPN reconnection (Attempt 1)...
2024-06-15 12:00:15 : OpenVPN connected successfully to the selected server.
2024-06-15 12:00:30 : New IP: 123.123.123.123
2024-06-15 12:30:00 : Success: IP changed from 111.111.111.111 to 123.123.123.123.
```

---

## Dependencies
- OpenVPN
- curl
- killall
- logger
- pgrep
- grep

### Install Dependencies on Debian-based Systems
```bash
sudo apt update && sudo apt install openvpn curl procps
```

---

## Notes
- **Protect Sensitive Data**: Ensure `auth.txt` is not included in the Git repository. Add it to `.gitignore`:
   ```plaintext
   auth.txt
   ```
- **IP Service**: The script uses `ifconfig.me` to fetch the public IP. Replace it with another IPv4 service if necessary.