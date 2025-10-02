import logging
import os
import time
import json
import csv
import datetime
import ftplib
import tarfile
import tempfile
import shutil
from ftplib import FTP

# Logging setup
log_file = 'general.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler()
    ]
)

class TransferReport:
    """Class for tracking transfer statistics and generating reports."""
    def __init__(self):
        self.start_time = datetime.datetime.now()
        self.end_time = None  # Will be set when transfer completes
        self.protocol_name = "ftp"  # Always FTP for this version
        self.source_path = ""  # Source path/database
        self.target_path = ""  # Target path/database
        self.total_size_bytes = 0  # Total size of data to transfer
        self.transferred_size_bytes = 0  # Actual transferred size
        self.file_count = 0  # Number of files transferred
        self.directory_count = 0  # Number of directories transferred
        self.errors = []  # List of error messages
        self.success = False  # Whether the transfer was successful
        
    def add_error(self, error_msg):
        """Add error message to report."""
        self.errors.append(error_msg)
        logging.error(error_msg)
        
    def complete(self, success=True):
        """Mark transfer as complete."""
        self.end_time = datetime.datetime.now()
        self.success = success
        
    def get_duration(self):
        """Get transfer duration in seconds."""
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return (datetime.datetime.now() - self.start_time).total_seconds()
        
    def generate_report(self):
        """Generate transfer report."""
        duration = self.get_duration()
        transfer_speed = self.transferred_size_bytes / duration if duration > 0 else 0
        
        report = {
            "success": self.success,
            "protocol": self.protocol_name,
            "source_path": self.source_path,
            "target_path": self.target_path,
            "start_time": self.start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": self.end_time.strftime("%Y-%m-%d %H:%M:%S") if self.end_time else None,
            "duration_seconds": duration,
            "total_size_bytes": self.total_size_bytes,
            "transferred_size_bytes": self.transferred_size_bytes,
            "transfer_speed_bps": transfer_speed,
            "file_count": self.file_count,
            "directory_count": self.directory_count,
            "errors": "; ".join(self.errors) if self.errors else ""
        }
        
        return report
    
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
                transfer_speed_mbps = round(report_data["transfer_speed_bps"] / (1024*1024), 2)
                
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
    
    def save_json_report(self, filename="transfer_report.json"):
        """Save transfer report as JSON (legacy support)."""
        report_data = self.generate_report()
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report_data, f, indent=2, ensure_ascii=False)
            logging.info(f"JSON transfer report saved to {filename}")
        except Exception as e:
            logging.error(f"Failed to save JSON report: {str(e)}")

def create_ftp_connection(host, port, user, password):
    """Create and return an FTP connection."""
    try:
        # Use port 21 if the provided port is SSH port
        ftp_port = port if port != 22 and port != 2222 else 21
        
        logging.info(f"Connecting to FTP server {host}:{ftp_port}")
        ftp = FTP()
        ftp.connect(host, ftp_port)
        ftp.login(user, password)
        logging.info("FTP connection established successfully")
        return ftp
    except Exception as e:
        logging.error(f"Failed to connect to FTP server: {str(e)}")
        raise

def get_ftp_directory_size(ftp, path):
    """Calculate the total size of a directory via FTP."""
    total_size = 0
    file_count = 0
    dir_count = 0
    
    try:
        # Try to change to the directory
        original_dir = ftp.pwd()
        ftp.cwd(path)
        
        # Get directory listing
        files = []
        ftp.retrlines('NLST', files.append)
        
        for item in files:
            try:
                # Try to get file size
                file_size = ftp.size(item)
                if file_size is not None:
                    total_size += file_size
                    file_count += 1
                else:
                    # It's likely a directory, recurse into it
                    try:
                        ftp.cwd(item)
                        subdir_size, subdir_files, subdir_dirs = get_ftp_directory_size(ftp, '.')
                        total_size += subdir_size
                        file_count += subdir_files
                        dir_count += subdir_dirs + 1
                        ftp.cwd('..')
                    except:
                        # If we can't access it, skip it
                        pass
            except:
                # Skip files we can't access
                pass
        
        # Return to original directory
        ftp.cwd(original_dir)
        
        logging.info(f"Directory {path} contains {file_count} files and {dir_count} directories, total size: {total_size/1024/1024:.2f}MB")
        return total_size, file_count, dir_count
        
    except Exception as e:
        logging.error(f"Error calculating directory size: {str(e)}")
        return 0, 0, 0

def download_ftp_directory(ftp, remote_path, local_path):
    """Download a directory recursively from FTP server."""
    try:
        # Create local directory if it doesn't exist
        os.makedirs(local_path, exist_ok=True)
        
        # Save current directory
        original_dir = ftp.pwd()
        ftp.cwd(remote_path)
        
        # Get directory listing
        files = []
        ftp.retrlines('NLST', files.append)
        
        for item in files:
            local_item_path = os.path.join(local_path, item)
            
            try:
                # Try to get file size (if it's a file)
                file_size = ftp.size(item)
                if file_size is not None:
                    # It's a file, download it
                    logging.info(f"Downloading file: {item} ({file_size} bytes)")
                    with open(local_item_path, 'wb') as local_file:
                        ftp.retrbinary(f'RETR {item}', local_file.write)
                else:
                    # It's likely a directory
                    try:
                        ftp.cwd(item)
                        # Recursively download subdirectory
                        download_ftp_directory(ftp, '.', local_item_path)
                        ftp.cwd('..')
                    except:
                        logging.warning(f"Could not access directory: {item}")
            except:
                # Try as directory if file operations fail
                try:
                    ftp.cwd(item)
                    download_ftp_directory(ftp, '.', local_item_path)
                    ftp.cwd('..')
                except:
                    logging.warning(f"Could not download: {item}")
        
        # Return to original directory
        ftp.cwd(original_dir)
        
    except Exception as e:
        logging.error(f"Error downloading directory: {str(e)}")
        raise

def upload_ftp_directory(ftp, local_path, remote_path):
    """Upload a directory recursively to FTP server."""
    try:
        # Create remote directory
        try:
            ftp.mkd(remote_path)
        except:
            pass  # Directory might already exist
        
        # Change to remote directory
        ftp.cwd(remote_path)
        
        # Upload all files and subdirectories
        for item in os.listdir(local_path):
            local_item_path = os.path.join(local_path, item)
            
            if os.path.isfile(local_item_path):
                # Upload file
                logging.info(f"Uploading file: {item}")
                with open(local_item_path, 'rb') as local_file:
                    ftp.storbinary(f'STOR {item}', local_file)
            elif os.path.isdir(local_item_path):
                # Recursively upload directory
                logging.info(f"Uploading directory: {item}")
                current_dir = ftp.pwd()
                try:
                    ftp.mkd(item)
                except:
                    pass  # Directory might already exist
                
                upload_ftp_directory(ftp, local_item_path, item)
                ftp.cwd(current_dir)
        
    except Exception as e:
        logging.error(f"Error uploading directory: {str(e)}")
        raise

def transfer_directory(
        SOURCE_HOST, SOURCE_PORT, SOURCE_USER, SOURCE_PASS,
        TARGET_HOST, TARGET_PORT, TARGET_USER, TARGET_PASS,
        path, cleanup_temp_files=True, use_chunking=False, 
        max_chunk_size=50*1024*1024, compression_level=1):
    """
    Transfer a directory from source cPanel to target cPanel using FTP.
    
    Args:
        SOURCE_HOST, SOURCE_PORT, SOURCE_USER, SOURCE_PASS: Source server connection details
        TARGET_HOST, TARGET_PORT, TARGET_USER, TARGET_PASS: Target server connection details
        path: Path to transfer (relative to home directory)
        cleanup_temp_files: Whether to remove temporary files after transfer
        use_chunking: Whether to split large directories into smaller chunks
        max_chunk_size: Maximum size for each chunk in bytes (default 50MB)
        compression_level: Level of compression (1=fastest, 9=smallest)
        
    Returns:
        TransferReport object with transfer details
    """
    report = TransferReport()
    report.source_path = path
    report.target_path = path
    
    source_ftp = None
    target_ftp = None
    temp_dir = None
    
    try:
        logging.info(f"--- FTP Transfer Start: {path} ---")
        
        # Create FTP connections
        source_ftp = create_ftp_connection(SOURCE_HOST, SOURCE_PORT, SOURCE_USER, SOURCE_PASS)
        target_ftp = create_ftp_connection(TARGET_HOST, TARGET_PORT, TARGET_USER, TARGET_PASS)
        
        # Get directory size and file count
        total_size, file_count, dir_count = get_ftp_directory_size(source_ftp, path)
        report.total_size_bytes = total_size
        report.file_count = file_count
        report.directory_count = dir_count
        
        logging.info(f"Directory size: {total_size / (1024*1024):.2f} MB")
        
        # Create/use fixed temporary directory for local processing
        temp_dir = "tmp_trans"
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
            logging.info(f"Created temporary directory: {temp_dir}")
        
        # Clear any existing content in temp directory for this transfer
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        transfer_temp_dir = os.path.join(temp_dir, f"transfer_{timestamp}")
        os.makedirs(transfer_temp_dir, exist_ok=True)
        
        local_download_path = os.path.join(transfer_temp_dir, "source")
        
        # Download from source
        logging.info("Downloading from source FTP server...")
        download_ftp_directory(source_ftp, path, local_download_path)
        
        if use_chunking and total_size > max_chunk_size:
            # Handle chunked transfer
            logging.info("Using chunked transfer for large directory")
            success = transfer_in_chunks_ftp(
                local_download_path, target_ftp, path, 
                max_chunk_size, compression_level, report
            )
        else:
            # Standard transfer
            logging.info("Using standard FTP transfer")
            
            if compression_level > 1:
                # Create compressed archive
                archive_path = os.path.join(transfer_temp_dir, f"{os.path.basename(path)}.tar.gz")
                logging.info("Creating compressed archive...")
                
                with tarfile.open(archive_path, "w:gz", compresslevel=compression_level) as tar:
                    tar.add(local_download_path, arcname=os.path.basename(path))
                
                # Upload compressed archive
                logging.info("Uploading compressed archive...")
                with open(archive_path, 'rb') as archive_file:
                    target_ftp.storbinary(f'STOR {os.path.basename(archive_path)}', archive_file)
                
                # Extract on target (this would require shell access, so we'll upload directly)
                logging.warning("Compressed upload completed, but extraction requires manual intervention on target server")
                
            else:
                # Direct upload without compression
                logging.info("Uploading directory structure...")
                upload_ftp_directory(target_ftp, local_download_path, path)
            
            success = True
        
        if success:
            report.transferred_size_bytes = total_size
            report.complete(True)
            logging.info("FTP transfer completed successfully")
        else:
            report.complete(False)
            
    except Exception as e:
        error_msg = f"FTP transfer failed: {str(e)}"
        report.add_error(error_msg)
        report.complete(False)
        logging.error(error_msg)
        
    finally:
        # Close FTP connections
        if source_ftp:
            try:
                source_ftp.quit()
            except:
                pass
        if target_ftp:
            try:
                target_ftp.quit()
            except:
                pass
        
        # Clean up temporary files for this transfer
        if transfer_temp_dir and cleanup_temp_files:
            try:
                shutil.rmtree(transfer_temp_dir)
                logging.info(f"Temporary files cleaned up from {transfer_temp_dir}")
            except:
                logging.warning(f"Could not clean up temporary files from {transfer_temp_dir}")
    
    logging.info(f"--- FTP Transfer Complete: {path} ---")
    return report

def transfer_in_chunks_ftp(local_path, target_ftp, remote_path, max_chunk_size, compression_level, report):
    """Transfer directory in chunks using FTP."""
    try:
        # Implementation for chunked FTP transfer
        # This is a simplified version - you might want to enhance this based on your specific needs
        logging.info("Chunked FTP transfer not fully implemented yet, using standard transfer")
        
        # For now, just upload the directory directly
        upload_ftp_directory(target_ftp, local_path, remote_path)
        return True
        
    except Exception as e:
        logging.error(f"Chunked FTP transfer failed: {str(e)}")
        return False