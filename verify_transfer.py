#!/usr/bin/env python3
"""
Quick verification script to check what was transferred
"""

import os
from dotenv import load_dotenv
from service_ssh import create_ssh_connection, execute_ssh_command

# Load environment
load_dotenv()

def verify_transfer():
    # Connect to target server
    target_ssh = create_ssh_connection(
        os.getenv('TARGET_HOST'),
        int(os.getenv('TARGET_SSH_PORT', '22')),
        os.getenv('TARGET_USER'),
        os.getenv('TARGET_PASSWORD')
    )
    
    if not target_ssh:
        print("Failed to connect to target server")
        return
    
    # Check if directory exists on target
    target_path = os.getenv('TRANSFER_PATH', '')
    
    print(f"Checking target directory: {target_path}")
    
    # List contents
    list_cmd = f"ls -la '{target_path}'"
    exit_code, stdout, stderr = execute_ssh_command(target_ssh, list_cmd)
    
    if exit_code == 0:
        print("Target directory contents:")
        print(stdout)
    else:
        print(f"Failed to list target directory: {stderr}")
        
        # Try to find any AFAQ directories in the parent
        if target_path:
            parent_path = '/'.join(target_path.split('/')[:-1])
            find_cmd = f"find '{parent_path}' -name '*AFAQ*' -type d 2>/dev/null"
            exit_code, stdout, stderr = execute_ssh_command(target_ssh, find_cmd)
            
            if stdout.strip():
                print("Found AFAQ directories:")
                print(stdout)
            else:
                print("No AFAQ directories found in parent directory")
    
    target_ssh.close()

if __name__ == "__main__":
    verify_transfer()