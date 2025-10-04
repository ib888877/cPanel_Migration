#!/usr/bin/env python3
"""
Check what's in the extracted AFAQ directory
"""

import os
from dotenv import load_dotenv
from service_ssh import create_ssh_connection, execute_ssh_command

# Load environment
load_dotenv()

def check_afaq_contents():
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
    
    # Check contents of .AFAQ directory
    afaq_path = "mail/abyar-alrumaila.com/account.fin/.AFAQ"
    
    print(f"Checking contents of: {afaq_path}")
    
    # List contents recursively
    list_cmd = f"find '{afaq_path}' -ls 2>/dev/null | head -20"
    exit_code, stdout, stderr = execute_ssh_command(target_ssh, list_cmd)
    
    if exit_code == 0 and stdout.strip():
        print("Contents found:")
        print(stdout)
    else:
        print("No contents found or error accessing directory")
        
    # Also try simple ls
    ls_cmd = f"ls -la '{afaq_path}'"
    exit_code, stdout, stderr = execute_ssh_command(target_ssh, ls_cmd)
    
    if exit_code == 0:
        print("\nDirectory listing:")
        print(stdout)
    
    target_ssh.close()

if __name__ == "__main__":
    check_afaq_contents()