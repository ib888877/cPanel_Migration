import logging
import os
import time
import json
import csv
import datetime
import paramiko
import socket
import re
from typing import Tuple, Optional

# Logging setup
log_file = 'general.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class TransferReport:
    """Class to track and report on transfer operations."""
    
    def __init__(self):
        self.start_time = time.time()
        self.end_time = None
        self.success = False
        self.source_path = ""
        self.target_path = ""
        self.total_size_bytes = 0
        self.transferred_size_bytes = 0
        self.file_count = 0
        self.directory_count = 0
        self.errors = []
        self.protocol = "SSH"
    
    def add_error(self, error_msg):
        """Add an error message to the report."""
        self.errors.append(error_msg)
        logging.error(error_msg)
    
    def complete(self, success=True):
        """Mark the transfer as complete."""
        self.end_time = time.time()
        self.success = success
    
    def get_duration(self):
        """Get transfer duration in seconds."""
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time
    
    def generate_report(self):
        """Generate a detailed transfer report."""
        duration = self.get_duration()
        
        return {
            "success": self.success,
            "protocol": self.protocol,
            "source_path": self.source_path,
            "target_path": self.target_path,
            "start_time": datetime.datetime.fromtimestamp(self.start_time).strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": datetime.datetime.fromtimestamp(self.end_time).strftime("%Y-%m-%d %H:%M:%S") if self.end_time else None,
            "duration_seconds": duration,
            "total_size_bytes": self.total_size_bytes,
            "transferred_size_bytes": self.transferred_size_bytes,
            "file_count": self.file_count,
            "directory_count": self.directory_count,
            "errors": "; ".join(self.errors) if self.errors else ""
        }
    
    def save_csv_report(self, filename="transfers_results.csv"):
        """Save transfer report as CSV, appending to existing file."""
        report_data = self.generate_report()
        
        # Check if file exists to determine if we need headers
        file_exists = os.path.exists(filename)
        
        # CSV column headers
        headers = [
            "timestamp", "success", "protocol", "source_path", "target_path",
            "start_time", "end_time", "duration_seconds", "total_size_mb", 
            "transferred_size_mb", "transfer_speed_mbps", "file_count", 
            "directory_count", "errors"
        ]
        
        try:
            with open(filename, 'a', newline='', encoding='utf-8') as csvfile:
                writer = csv.writer(csvfile)
                
                # Write headers if file is new
                if not file_exists:
                    writer.writerow(headers)
                
                # Convert bytes to MB for better readability
                total_size_mb = round(report_data["total_size_bytes"] / (1024*1024), 2)
                transferred_size_mb = round(report_data["transferred_size_bytes"] / (1024*1024), 2)
                
                # Calculate transfer speed for SSH transfers
                duration = report_data["duration_seconds"]
                if duration > 0:
                    transfer_speed_mbps = round((report_data["transferred_size_bytes"] / (1024*1024)) / duration, 2)
                else:
                    transfer_speed_mbps = 0
                
                # Write data row
                row = [
                    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # timestamp
                    "SUCCESS" if report_data["success"] else "FAILED",
                    report_data["protocol"],
                    report_data["source_path"],
                    report_data["target_path"],
                    report_data["start_time"],
                    report_data["end_time"] or "",
                    round(report_data["duration_seconds"], 2),
                    total_size_mb,
                    transferred_size_mb,
                    transfer_speed_mbps,
                    report_data["file_count"],
                    report_data["directory_count"],
                    report_data["errors"]
                ]
                
                writer.writerow(row)
                
            logging.info(f"Transfer report saved to {filename}")
            
        except Exception as e:
            logging.error(f"Failed to save CSV report: {str(e)}")

def create_ssh_connection(host, port, username, password, timeout=30):
    """
    Create an SSH connection to the specified server.
    
    Args:
        host: Server hostname or IP
        port: SSH port
        username: SSH username
        password: SSH password
        timeout: Connection timeout in seconds
        
    Returns:
        SSH client object or None if connection failed
    """
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        logging.debug(f"Connecting to {host}:{port} as {username}")
        ssh.connect(
            hostname=host,
            port=port,
            username=username,
            password=password,
            timeout=timeout,
            banner_timeout=30,
            auth_timeout=30
        )
        
        logging.debug(f"SSH connection established to {host}")
        return ssh
        
    except Exception as e:
        logging.error(f"SSH connection failed: {str(e)}")
        return None

def execute_ssh_command(ssh, command, timeout=300):
    """
    Execute command via SSH and return output.
    
    Args:
        ssh: SSH connection
        command: Command to execute
        timeout: Command timeout in seconds
        
    Returns:
        tuple: (exit_code, stdout, stderr)
    """
    try:
        logging.debug(f"Executing SSH command: {command}")
        
        stdin, stdout, stderr = ssh.exec_command(command, timeout=timeout)
        
        # Wait for command completion
        exit_code = stdout.channel.recv_exit_status()
        
        # Read output
        stdout_data = stdout.read().decode('utf-8', errors='ignore')
        stderr_data = stderr.read().decode('utf-8', errors='ignore')
        
        if exit_code == 0:
            logging.debug(f"Command completed successfully")
            if stdout_data.strip():
                logging.debug(f"Output: {stdout_data.strip()}")
        else:
            logging.warning(f"Command failed with exit code {exit_code}")
            if stderr_data.strip():
                logging.warning(f"Error: {stderr_data.strip()}")
        
        return exit_code, stdout_data, stderr_data
        
    except Exception as e:
        logging.error(f"Failed to execute SSH command: {str(e)}")
        return -1, "", str(e)

def execute_ssh_command_with_progress(ssh, command, timeout=300):
    """
    Execute command via SSH with real-time progress monitoring for wget downloads.
    
    Args:
        ssh: SSH connection
        command: Command to execute (typically wget with progress=bar)
        timeout: Command timeout in seconds
        
    Returns:
        tuple: (exit_code, stdout, stderr)
    """
    try:
        logging.debug(f"Executing SSH command with progress: {command}")
        
        # Start the command
        stdin, stdout, stderr = ssh.exec_command(command, timeout=timeout)
        
        # Make stdout and stderr non-blocking
        stdout.channel.settimeout(0.1)
        stderr.channel.settimeout(0.1)
        
        stdout_data = ""
        stderr_data = ""
        last_progress_time = time.time()
        
        # Monitor progress in real-time
        while not stdout.channel.exit_status_ready():
            # Try to read from stderr (wget outputs progress to stderr)
            try:
                chunk = stderr.read(1024).decode('utf-8', errors='ignore')
                if chunk:
                    stderr_data += chunk
                    # Parse wget progress bars
                    lines = chunk.split('\n')
                    for line in lines:
                        if '%' in line and ('=' in line or 'ETA' in line):
                            # Extract progress information from wget output
                            # Format: filename    100%[===================>]  size  speed   ETA
                            progress_match = re.search(r'(\d+)%\[([=>\s]*)\]\s+([0-9.,]+[KMGT]?)\s+([0-9.,]+[KMGT]?B/s)\s*(eta\s+[0-9hms\s]*)?', line, re.IGNORECASE)
                            if progress_match:
                                percent = progress_match.group(1)
                                size = progress_match.group(3)
                                speed = progress_match.group(4)
                                eta = progress_match.group(5) or "calculating..."
                                
                                # Create a formatted progress line
                                progress_line = f"FTP Download Progress: {percent}% ({size}) @ {speed} - {eta.strip()}"
                                print(f"\r{progress_line}", end='', flush=True)
                                
                                # Log progress every 5 seconds to avoid spam
                                current_time = time.time()
                                if current_time - last_progress_time >= 5:
                                    logging.info(progress_line)
                                    last_progress_time = current_time
            except:
                pass
            
            # Try to read from stdout
            try:
                chunk = stdout.read(1024).decode('utf-8', errors='ignore')
                if chunk:
                    stdout_data += chunk
            except:
                pass
            
            time.sleep(0.1)
        
        # Read any remaining output
        try:
            remaining_stdout = stdout.read().decode('utf-8', errors='ignore')
            stdout_data += remaining_stdout
        except:
            pass
            
        try:
            remaining_stderr = stderr.read().decode('utf-8', errors='ignore')
            stderr_data += remaining_stderr
        except:
            pass
        
        # Get exit code
        exit_code = stdout.channel.recv_exit_status()
        
        # Clear the progress line
        print()
        
        if exit_code == 0:
            logging.debug(f"Command completed successfully")
        else:
            logging.warning(f"Command failed with exit code {exit_code}")
            if stderr_data.strip():
                # Filter out progress lines from error output
                error_lines = [line for line in stderr_data.split('\n') 
                              if line.strip() and '%' not in line and '=' not in line]
                if error_lines:
                    logging.warning(f"Error: {chr(10).join(error_lines)}")
        
        return exit_code, stdout_data, stderr_data
        
    except Exception as e:
        print()  # Clear progress line
        logging.error(f"Failed to execute SSH command with progress: {str(e)}")
        return -1, "", str(e)

def get_directory_size_ssh(ssh, path):
    """
    Get directory size and file count via SSH.
    
    Args:
        ssh: SSH connection
        path: Directory path to analyze
        
    Returns:
        tuple: (total_size_bytes, file_count, dir_count)
    """
    try:
        logging.info(f"Analyzing directory size: {path}")
        
        # Get total size in bytes
        size_cmd = f"du -sb '{path}' 2>/dev/null | cut -f1"
        exit_code, stdout, stderr = execute_ssh_command(ssh, size_cmd)
        
        total_size = 0
        if exit_code == 0 and stdout.strip().isdigit():
            total_size = int(stdout.strip())
        
        # Get file count
        file_cmd = f"find '{path}' -type f 2>/dev/null | wc -l"
        exit_code, stdout, stderr = execute_ssh_command(ssh, file_cmd)
        
        file_count = 0
        if exit_code == 0 and stdout.strip().isdigit():
            file_count = int(stdout.strip())
        
        # Get directory count
        dir_cmd = f"find '{path}' -type d 2>/dev/null | wc -l"
        exit_code, stdout, stderr = execute_ssh_command(ssh, dir_cmd)
        
        dir_count = 0
        if exit_code == 0 and stdout.strip().isdigit():
            dir_count = int(stdout.strip())
        
        logging.info(f"Directory analysis: {total_size/1024/1024:.2f}MB, {file_count} files, {dir_count} directories")
        return total_size, file_count, dir_count
        
    except Exception as e:
        logging.error(f"Failed to analyze directory: {str(e)}")
        return 0, 0, 0

def verify_directory_counts(ssh, path):
    """
    Get accurate file and directory counts for verification.
    
    Args:
        ssh: SSH connection
        path: Directory path to verify
        
    Returns:
        tuple: (file_count, directory_count)
    """
    try:
        # Count files (excluding directories)
        file_count_cmd = f"find '{path}' -type f | wc -l"
        exit_code, stdout, stderr = execute_ssh_command(ssh, file_count_cmd)
        file_count = int(stdout.strip()) if exit_code == 0 and stdout.strip().isdigit() else 0
        
        # Count directories (excluding the root directory itself)
        dir_count_cmd = f"find '{path}' -type d | wc -l"
        exit_code, stdout, stderr = execute_ssh_command(ssh, dir_count_cmd)
        dir_count = int(stdout.strip()) - 1 if exit_code == 0 and stdout.strip().isdigit() else 0
        dir_count = max(0, dir_count)  # Ensure non-negative
        
        return file_count, dir_count
        
    except Exception as e:
        logging.error(f"Failed to verify directory counts: {str(e)}")
        return 0, 0

def handle_missing_files(source_ssh, target_ssh, path, source_home, target_home, source_user, source_host):
    """
    Attempt to identify and transfer missing files.
    
    Args:
        source_ssh: Source SSH connection
        target_ssh: Target SSH connection
        path: Directory path
        source_home: Source home directory
        target_home: Target home directory
        source_user: Source username for FTP
        source_host: Source hostname for FTP
        
    Returns:
        bool: True if recovery was attempted successfully
    """
    try:
        logging.info("Attempting to identify and recover missing files...")
        
        # Get list of files from source and target
        source_files_cmd = f"find '{path}' -type f -printf '%P\\n' | sort"
        target_files_cmd = f"find '{path}' -type f -printf '%P\\n' | sort"
        
        # Get source file list
        exit_code, source_files, stderr = execute_ssh_command(source_ssh, source_files_cmd)
        if exit_code != 0:
            logging.error(f"Failed to get source file list: {stderr}")
            return False
            
        # Get target file list  
        exit_code, target_files, stderr = execute_ssh_command(target_ssh, target_files_cmd)
        if exit_code != 0:
            logging.error(f"Failed to get target file list: {stderr}")
            return False
        
        # Find missing files
        source_file_set = set(source_files.strip().split('\n')) if source_files.strip() else set()
        target_file_set = set(target_files.strip().split('\n')) if target_files.strip() else set()
        missing_files = source_file_set - target_file_set
        
        if missing_files:
            logging.info(f"Found {len(missing_files)} missing files:")
            for missing_file in list(missing_files)[:10]:  # Show first 10
                logging.info(f"  Missing: {missing_file}")
            
            if len(missing_files) > 10:
                logging.info(f"  ... and {len(missing_files) - 10} more")
            
            # Try to transfer missing files individually using tar
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            recovery_archive = f"recovery_{timestamp}.tar.gz"
            
            # Create file list for tar
            file_list_path = f"/tmp/missing_files_{timestamp}.txt"
            file_list_content = '\n'.join(missing_files)
            
            # Create file list on source server
            create_list_cmd = f"cat > {file_list_path} << 'EOF'\n{file_list_content}\nEOF"
            execute_ssh_command(source_ssh, create_list_cmd)
            
            # Create recovery archive with only missing files
            recovery_tar_cmd = f"cd '{path}' && tar czf ~/tmp_trans/{recovery_archive} -T {file_list_path}"
            exit_code, stdout, stderr = execute_ssh_command(source_ssh, recovery_tar_cmd, timeout=300)
            
            if exit_code == 0:
                # Transfer and extract recovery archive
                source_ftp_url = f"ftp://{source_user}@{source_host}:21/tmp_trans/{recovery_archive}"
                wget_cmd = f"cd ~/tmp_trans && wget --timeout=180 --tries=2 '{source_ftp_url}'"
                exit_code, stdout, stderr = execute_ssh_command(target_ssh, wget_cmd, timeout=600)
                
                if exit_code == 0:
                    # Extract recovery archive
                    extract_cmd = f"tar -xzf ~/tmp_trans/{recovery_archive} -C '{target_home}'"
                    exit_code, stdout, stderr = execute_ssh_command(target_ssh, extract_cmd, timeout=300)
                    
                    if exit_code == 0:
                        logging.info("Recovery archive extracted successfully")
                        
                        # Cleanup recovery files
                        execute_ssh_command(source_ssh, f"rm ~/tmp_trans/{recovery_archive} {file_list_path}")
                        execute_ssh_command(target_ssh, f"rm ~/tmp_trans/{recovery_archive}")
                        
                        return True
                    else:
                        logging.error(f"Failed to extract recovery archive: {stderr}")
                else:
                    logging.error(f"Failed to download recovery archive: {stderr}")
            else:
                logging.error(f"Failed to create recovery archive: {stderr}")
            
            # Cleanup even if failed
            execute_ssh_command(source_ssh, f"rm -f ~/tmp_trans/{recovery_archive} {file_list_path}")
            execute_ssh_command(target_ssh, f"rm -f ~/tmp_trans/{recovery_archive}")
        
        return False
        
    except Exception as e:
        logging.error(f"Error during missing file recovery: {str(e)}")
        return False

def transfer_directory_ssh(
        SOURCE_HOST, SOURCE_PORT, SOURCE_USER, SOURCE_PASS,
        TARGET_HOST, TARGET_PORT, TARGET_USER, TARGET_PASS,
        path, cleanup_temp_files=True):
    """
    Transfer a directory using SSH-based workflow:
    1. SSH to source: compress directory to ~/tmp_trans/
    2. SSH to target: wget archive from source FTP, extract, cleanup
    3. SSH to source: cleanup archive
    
    Args:
        SOURCE_HOST, SOURCE_PORT, SOURCE_USER, SOURCE_PASS: Source server SSH details
        TARGET_HOST, TARGET_PORT, TARGET_USER, TARGET_PASS: Target server SSH details  
        path: Path to transfer (relative to home directory)
        cleanup_temp_files: Whether to remove temporary files after transfer
        
    Returns:
        TransferReport object with transfer details
    """
    report = TransferReport()
    report.source_path = path
    report.target_path = path
    
    source_ssh = None
    target_ssh = None
    
    try:
        logging.info(f"--- SSH Transfer Start: {path} ---")
        
        # Create SSH connections
        source_ssh = create_ssh_connection(SOURCE_HOST, SOURCE_PORT, SOURCE_USER, SOURCE_PASS)
        target_ssh = create_ssh_connection(TARGET_HOST, TARGET_PORT, TARGET_USER, TARGET_PASS)
        
        if not source_ssh or not target_ssh:
            raise Exception("Failed to establish SSH connections")
        
        # Get source directory info
        total_size, file_count, dir_count = get_directory_size_ssh(source_ssh, path)
        report.total_size_bytes = total_size
        report.file_count = file_count
        report.directory_count = dir_count
        
        if file_count == 0:
            logging.warning("Source directory appears to be empty")
        
        # Step 1: Create compressed archive on source server
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        archive_name = f"{os.path.basename(path)}_{timestamp}.tar.gz"
        source_archive_path = f"tmp_trans/{archive_name}"
        
        logging.info("Step 1: Creating compressed archive on source server...")
        
        # Ensure tmp_trans directory exists on source
        mkdir_cmd = "mkdir -p ~/tmp_trans"
        execute_ssh_command(source_ssh, mkdir_cmd)
        
        # Get source home directory for absolute paths
        pwd_cmd = "pwd"
        exit_code, source_home, stderr = execute_ssh_command(source_ssh, pwd_cmd)
        source_home = source_home.strip()
        
        # Create archive using relative paths to avoid nested directory structure
        path_parts = path.split('/')
        if len(path_parts) > 1:
            # If path has multiple parts, cd to parent and tar the final directory
            parent_dir = '/'.join(path_parts[:-1])
            target_dir_name = path_parts[-1]
            
            # Properly quote directory names to handle spaces and special characters
            parent_path = f"{source_home}/{parent_dir}"
            # Create archive name without spaces to avoid shell issues
            safe_archive_name = archive_name.replace(' ', '_').replace('\\', '_')
            archive_path = f"{source_home}/tmp_trans/{safe_archive_name}"
            
            # Use the actual directory name from path instead of hardcoded patterns
            # This properly handles any special characters in the directory name
            tar_cmd = f"cd '{parent_path}' && tar czf '{archive_path}' --exclude-backups --warning=no-file-changed '{target_dir_name}'"
        else:
            # If path is single directory, cd to home and tar it
            safe_archive_name = archive_name.replace(' ', '_').replace('\\', '_')
            tar_cmd = f"cd '{source_home}' && tar czf '{source_home}/tmp_trans/{safe_archive_name}' --exclude-backups --warning=no-file-changed '{path}'"
        
        logging.info(f"Creating archive: {tar_cmd}")
        
        exit_code, stdout, stderr = execute_ssh_command(source_ssh, tar_cmd, timeout=600)
        if exit_code != 0:
            # Log more details about the failure
            logging.error(f"Tar command failed with exit code {exit_code}")
            logging.error(f"Stdout: {stdout}")
            logging.error(f"Stderr: {stderr}")
            
            # Try to list the directory to see what's actually there
            if len(path_parts) > 1:
                list_cmd = f"ls -la '{source_home}/{parent_dir}/'"
                logging.info(f"Attempting to list parent directory: {list_cmd}")
                list_exit, list_out, list_err = execute_ssh_command(source_ssh, list_cmd)
                if list_exit == 0:
                    logging.info(f"Directory contents:\n{list_out}")
                else:
                    logging.error(f"Could not list directory: {list_err}")
            
            raise Exception(f"Failed to create archive on source: {stderr}")
        
        # Verify archive was created
        safe_archive_name = archive_name.replace(' ', '_').replace('\\', '_')
        ls_cmd = f"ls -la ~/tmp_trans/{safe_archive_name}"
        exit_code, stdout, stderr = execute_ssh_command(source_ssh, ls_cmd)
        if exit_code != 0:
            raise Exception("Archive was not created successfully")
        
        logging.info(f"Archive created successfully: {safe_archive_name}")
        
        # Step 2: Transfer and extract on target server
        logging.info("Step 2: Transferring archive to target server...")
        
        # Get target home directory
        exit_code, target_home, stderr = execute_ssh_command(target_ssh, pwd_cmd)
        target_home = target_home.strip()
        
        # Ensure tmp_trans directory exists on target
        execute_ssh_command(target_ssh, "mkdir -p ~/tmp_trans")
        
        # Download archive using wget from source FTP with progress display
        # Note: Use port 21 for FTP, not the SSH port that was passed to this function
        source_ftp_url = f"ftp://{SOURCE_USER}:{SOURCE_PASS}@{SOURCE_HOST}:21/tmp_trans/{safe_archive_name}"
        wget_cmd = f"cd ~/tmp_trans && wget --progress=bar:force --timeout=300 --tries=3 '{source_ftp_url}'"
        
        logging.info("Downloading archive via FTP...")
        logging.info(f"Source: {SOURCE_HOST}/tmp_trans/{safe_archive_name}")
        
        # Execute wget command with real-time progress monitoring
        exit_code, stdout, stderr = execute_ssh_command_with_progress(target_ssh, wget_cmd, timeout=1800)
        if exit_code != 0:
            raise Exception(f"Failed to download archive: {stderr}")
        
        logging.info("Archive download completed successfully")
        
        # Create target directory structure (parent directory)
        if len(path_parts) > 1:
            parent_target_dir = f"{target_home}/{'/'.join(path_parts[:-1])}"
            mkdir_target_cmd = f"mkdir -p '{parent_target_dir}'"
            execute_ssh_command(target_ssh, mkdir_target_cmd)
            extract_dir = parent_target_dir
        else:
            extract_dir = target_home
        
        # Extract archive directly (no strip-components needed since we used relative paths)
        extract_cmd = f"tar -xvzf ~/tmp_trans/{safe_archive_name} -C '{extract_dir}'"
        logging.info(f"Extracting archive: {extract_cmd}")
        
        exit_code, stdout, stderr = execute_ssh_command(target_ssh, extract_cmd, timeout=600)
        if exit_code != 0:
            logging.error(f"Extract command failed with exit code {exit_code}")
            logging.error(f"Stdout: {stdout}")
            logging.error(f"Stderr: {stderr}")
            raise Exception(f"Failed to extract archive: {stderr}")
        
        logging.info("Archive extracted successfully")
        
        # Step 3: Verify transfer completeness
        logging.info("Step 3: Verifying transfer completeness...")
        
        # Get file counts before and after transfer
        source_file_count, source_dir_count = verify_directory_counts(source_ssh, path)
        target_file_count, target_dir_count = verify_directory_counts(target_ssh, path)
        
        logging.info(f"Source: {source_file_count} files, {source_dir_count} directories")
        logging.info(f"Target: {target_file_count} files, {target_dir_count} directories")
        
        # Check for missing files
        if target_file_count < source_file_count:
            missing_files = source_file_count - target_file_count
            logging.warning(f"Transfer incomplete: {missing_files} files missing")
            
            # Try to identify and transfer missing files
            success = handle_missing_files(source_ssh, target_ssh, path, source_home, target_home, SOURCE_USER, SOURCE_HOST)
            if success:
                # Re-verify after fixing
                new_target_count, _ = verify_directory_counts(target_ssh, path)
                logging.info(f"After recovery: Target has {new_target_count} files")
                if new_target_count < source_file_count:
                    logging.error(f"Still missing {source_file_count - new_target_count} files after recovery attempt")
                else:
                    logging.info("✓ All missing files recovered successfully")
                    target_file_count = new_target_count
            else:
                logging.error("Failed to recover missing files")
        elif target_file_count > source_file_count:
            logging.warning(f"Target has {target_file_count - source_file_count} extra files")
        else:
            logging.info("✓ File count verification successful - all files transferred")
        
        # Update report with actual transferred files
        report.file_count = target_file_count
        report.directory_count = target_dir_count
        
        # Step 4: Cleanup temporary files
        if cleanup_temp_files:
            logging.info("Step 4: Cleaning up temporary files...")
            
            # Remove archive from target  
            safe_archive_name = archive_name.replace(' ', '_').replace('\\', '_')
            target_cleanup_cmd = f"rm ~/tmp_trans/{safe_archive_name}"
            execute_ssh_command(target_ssh, target_cleanup_cmd)
            
            # Remove archive from source
            source_cleanup_cmd = f"rm ~/tmp_trans/{safe_archive_name}"
            execute_ssh_command(source_ssh, source_cleanup_cmd)
            
            logging.info("Cleanup completed")
        
        # Mark transfer as successful
        report.transferred_size_bytes = total_size
        report.complete(True)
        
        # Calculate performance metrics
        duration = report.get_duration()
        if duration > 0:
            speed_mbps = (total_size / (1024*1024)) / duration
            logging.info(f"Transfer completed in {duration:.2f} seconds")
            logging.info(f"Average speed: {speed_mbps:.2f} MB/s")
        
        logging.info("SSH transfer completed successfully")
        
    except Exception as e:
        error_msg = f"SSH transfer failed: {str(e)}"
        report.add_error(error_msg)
        report.complete(False)
        logging.error(error_msg)
        
        # Log stack trace for debugging
        import traceback
        logging.debug(traceback.format_exc())
        
    finally:
        # Close SSH connections
        if source_ssh:
            try:
                source_ssh.close()
                logging.debug("Source SSH connection closed")
            except:
                pass
                
        if target_ssh:
            try:
                target_ssh.close()
                logging.debug("Target SSH connection closed")
            except:
                pass
    
    logging.info(f"--- SSH Transfer Complete: {path} ---")
    return report