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
from typing import Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

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
        self.current_file = ""  # Current file being transferred
        self.files_completed = 0  # Number of files completed
        
    def add_error(self, error_msg):
        """Add error message to report."""
        self.errors.append(error_msg)
        logging.error(error_msg)
        
    def complete(self, success=True):
        """Mark transfer as complete."""
        self.end_time = datetime.datetime.now()
        self.success = success
        
    def update_progress(self, current_file, files_completed):
        """Update transfer progress."""
        self.current_file = current_file
        self.files_completed = files_completed
        if self.file_count > 0:
            progress = (files_completed / self.file_count) * 100
            logging.info(f"Progress: {progress:.1f}% ({files_completed}/{self.file_count} files)")
    
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

def create_ftp_connection(host, port, user, password, timeout=60):
    """Create and return an optimized FTP connection with retry logic.
    
    Args:
        host: FTP server hostname
        port: FTP server port
        user: Username for authentication
        password: Password for authentication
        timeout: Connection timeout in seconds
        
    Returns:
        FTP connection object
    """
    # Use port 21 if the provided port is SSH port
    ftp_port = port if port != 22 and port != 2222 else 21
    
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            logging.info(f"Connecting to FTP server {host}:{ftp_port} (attempt {attempt + 1}/{max_retries})")
            ftp = FTP()
            ftp.connect(host, ftp_port, timeout=timeout)
            ftp.login(user, password)
            
            # Enable passive mode for better compatibility
            ftp.set_pasv(True)
            
            # Set binary mode for file transfers
            ftp.voidcmd('TYPE I')
            
            logging.info("FTP connection established successfully")
            return ftp
            
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                logging.warning(f"Connection attempt {attempt + 1} failed: {str(e)}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logging.error(f"Failed to connect to FTP server after {max_retries} attempts: {str(e)}")
                raise

def get_ftp_directory_size(ftp, path):
    """Calculate the total size of a directory via FTP with optimization.
    
    Args:
        ftp: FTP connection object
        path: Remote path to analyze
        
    Returns:
        Tuple of (total_size, file_count, dir_count)
    """
    total_size = 0
    file_count = 0
    dir_count = 0
    
    try:
        # Try to change to the directory
        original_dir = ftp.pwd()
        
        try:
            ftp.cwd(path)
        except ftplib.error_perm:
            logging.error(f"Cannot access directory: {path}")
            return 0, 0, 0
        
        # Get directory listing with better parsing
        files = []
        dirs = []
        
        # Use MLSD if available (more reliable than NLST)
        try:
            for name, facts in ftp.mlsd():
                if name in ('.', '..'):
                    continue
                if facts.get('type') == 'file':
                    files.append((name, int(facts.get('size', 0))))
                elif facts.get('type') == 'dir':
                    dirs.append(name)
        except (ftplib.error_perm, AttributeError):
            # Fall back to NLST if MLSD is not supported
            items = []
            ftp.retrlines('NLST', items.append)
            
            for item in items:
                try:
                    file_size = ftp.size(item)
                    if file_size is not None:
                        files.append((item, file_size))
                    else:
                        dirs.append(item)
                except:
                    # Assume it's a directory if size check fails
                    dirs.append(item)
        
        # Process files
        for filename, size in files:
            total_size += size
            file_count += 1
        
        # Process directories recursively
        for dirname in dirs:
            try:
                ftp.cwd(dirname)
                subdir_size, subdir_files, subdir_dirs = get_ftp_directory_size(ftp, '.')
                total_size += subdir_size
                file_count += subdir_files
                dir_count += subdir_dirs + 1
                ftp.cwd('..')
            except Exception as e:
                logging.warning(f"Could not access subdirectory {dirname}: {str(e)}")
        
        # Return to original directory
        ftp.cwd(original_dir)
        
        if file_count > 0 or dir_count > 0:
            logging.info(f"Directory {path} - {file_count} files, {dir_count} dirs, {total_size/1024/1024:.2f}MB")
        return total_size, file_count, dir_count
        
    except Exception as e:
        logging.error(f"Error calculating directory size: {str(e)}")
        return 0, 0, 0

def download_ftp_file_with_retry(ftp, remote_file, local_file, max_retries=3):
    """Download a single file with retry logic and progress tracking.
    
    Args:
        ftp: FTP connection object
        remote_file: Remote filename
        local_file: Local file path
        max_retries: Maximum number of retry attempts
        
    Returns:
        True if successful, False otherwise
    """
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            file_size = ftp.size(remote_file)
            if file_size is None:
                file_size = 0
            
            with open(local_file, 'wb') as f:
                def callback(data):
                    f.write(data)
                
                ftp.retrbinary(f'RETR {remote_file}', callback, blocksize=8192)
            
            # Verify file was downloaded
            if os.path.exists(local_file):
                downloaded_size = os.path.getsize(local_file)
                if file_size == 0 or downloaded_size == file_size:
                    return True
                else:
                    logging.warning(f"Size mismatch for {remote_file}: expected {file_size}, got {downloaded_size}")
                    
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt)
                logging.warning(f"Download attempt {attempt + 1} failed for {remote_file}: {str(e)}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logging.error(f"Failed to download {remote_file} after {max_retries} attempts: {str(e)}")
                return False
    
    return False


def download_ftp_directory(ftp, remote_path, local_path):
    """Download a directory recursively from FTP server with optimizations.
    
    Args:
        ftp: FTP connection object
        remote_path: Remote directory path
        local_path: Local directory path
    """
    try:
        # Create local directory if it doesn't exist
        os.makedirs(local_path, exist_ok=True)
        
        # Save current directory
        original_dir = ftp.pwd()
        ftp.cwd(remote_path)
        
        # Get directory listing
        items_to_download = []
        dirs_to_process = []
        
        # Use MLSD if available for better performance
        try:
            for name, facts in ftp.mlsd():
                if name in ('.', '..'):
                    continue
                if facts.get('type') == 'file':
                    items_to_download.append((name, int(facts.get('size', 0))))
                elif facts.get('type') == 'dir':
                    dirs_to_process.append(name)
        except (ftplib.error_perm, AttributeError):
            # Fall back to NLST
            files = []
            ftp.retrlines('NLST', files.append)
            
            for item in files:
                try:
                    file_size = ftp.size(item)
                    if file_size is not None:
                        items_to_download.append((item, file_size))
                    else:
                        dirs_to_process.append(item)
                except:
                    dirs_to_process.append(item)
        
        # Download files
        for filename, file_size in items_to_download:
            local_file_path = os.path.join(local_path, filename)
            logging.info(f"Downloading file: {filename} ({file_size} bytes)")
            download_ftp_file_with_retry(ftp, filename, local_file_path)
        
        # Process subdirectories
        for dirname in dirs_to_process:
            local_dir_path = os.path.join(local_path, dirname)
            try:
                ftp.cwd(dirname)
                logging.info(f"Entering directory: {dirname}")
                download_ftp_directory(ftp, '.', local_dir_path)
                ftp.cwd('..')
            except Exception as e:
                logging.warning(f"Could not download directory {dirname}: {str(e)}")
        
        # Return to original directory
        ftp.cwd(original_dir)
        
    except Exception as e:
        logging.error(f"Error downloading directory: {str(e)}")
        raise

def upload_ftp_file_with_retry(ftp, local_file, remote_file, max_retries=3):
    """Upload a single file with retry logic.
    
    Args:
        ftp: FTP connection object
        local_file: Local file path
        remote_file: Remote filename
        max_retries: Maximum number of retry attempts
        
    Returns:
        True if successful, False otherwise
    """
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            with open(local_file, 'rb') as f:
                ftp.storbinary(f'STOR {remote_file}', f, blocksize=8192)
            return True
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = retry_delay * (2 ** attempt)
                logging.warning(f"Upload attempt {attempt + 1} failed for {remote_file}: {str(e)}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                logging.error(f"Failed to upload {remote_file} after {max_retries} attempts: {str(e)}")
                return False
    
    return False


def upload_ftp_directory(ftp, local_path, remote_path):
    """Upload a directory recursively to FTP server with optimizations.
    
    Args:
        ftp: FTP connection object
        local_path: Local directory path
        remote_path: Remote directory path
    """
    try:
        # Create remote directory
        try:
            ftp.mkd(remote_path)
            logging.info(f"Created remote directory: {remote_path}")
        except ftplib.error_perm:
            # Directory might already exist
            pass
        
        # Change to remote directory
        ftp.cwd(remote_path)
        
        # Get list of items to upload
        items = os.listdir(local_path)
        
        # Upload all files and subdirectories
        for item in items:
            local_item_path = os.path.join(local_path, item)
            
            if os.path.isfile(local_item_path):
                # Upload file
                file_size = os.path.getsize(local_item_path)
                logging.info(f"Uploading file: {item} ({file_size} bytes)")
                upload_ftp_file_with_retry(ftp, local_item_path, item)
                
            elif os.path.isdir(local_item_path):
                # Recursively upload directory
                logging.info(f"Uploading directory: {item}")
                current_dir = ftp.pwd()
                try:
                    ftp.mkd(item)
                except ftplib.error_perm:
                    # Directory might already exist
                    pass
                
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
    transfer_temp_dir = None
    
    try:
        logging.info(f"--- FTP Transfer Start: {path} ---")
        logging.info(f"Configuration: chunking={use_chunking}, compression_level={compression_level}")
        
        # Create FTP connections with timeout and retry logic
        source_ftp = create_ftp_connection(SOURCE_HOST, SOURCE_PORT, SOURCE_USER, SOURCE_PASS, timeout=60)
        target_ftp = create_ftp_connection(TARGET_HOST, TARGET_PORT, TARGET_USER, TARGET_PASS, timeout=60)
        
        # Get directory size and file count
        logging.info("Analyzing source directory...")
        total_size, file_count, dir_count = get_ftp_directory_size(source_ftp, path)
        report.total_size_bytes = total_size
        report.file_count = file_count
        report.directory_count = dir_count
        
        logging.info(f"Directory analysis complete:")
        logging.info(f"  Size: {total_size / (1024*1024):.2f} MB")
        logging.info(f"  Files: {file_count}")
        logging.info(f"  Directories: {dir_count}")
        
        # Validate that directory is not empty
        if file_count == 0 and dir_count == 0:
            logging.warning("Source directory appears to be empty")
        
        # Create/use fixed temporary directory for local processing
        temp_dir = "tmp_trans"
        if not os.path.exists(temp_dir):
            os.makedirs(temp_dir)
            logging.info(f"Created temporary directory: {temp_dir}")
        
        # Create unique transfer directory
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        transfer_temp_dir = os.path.join(temp_dir, f"transfer_{timestamp}")
        os.makedirs(transfer_temp_dir, exist_ok=True)
        
        local_download_path = os.path.join(transfer_temp_dir, "source")
        
        # Download from source
        logging.info("Downloading from source FTP server...")
        start_download = time.time()
        download_ftp_directory(source_ftp, path, local_download_path)
        download_duration = time.time() - start_download
        logging.info(f"Download completed in {download_duration:.2f} seconds")
        
        # Determine transfer strategy
        if use_chunking and total_size > max_chunk_size:
            # Handle chunked transfer
            logging.info(f"Using chunked transfer (directory size {total_size/1024/1024:.2f}MB exceeds chunk size {max_chunk_size/1024/1024:.2f}MB)")
            start_upload = time.time()
            success = transfer_in_chunks_ftp(
                local_download_path, target_ftp, path, 
                max_chunk_size, compression_level, report
            )
            upload_duration = time.time() - start_upload
            logging.info(f"Chunked upload completed in {upload_duration:.2f} seconds")
        else:
            # Standard transfer
            logging.info("Using standard FTP transfer")
            start_upload = time.time()
            
            if compression_level > 1:
                # Create compressed archive
                archive_path = os.path.join(transfer_temp_dir, f"{os.path.basename(path)}.tar.gz")
                logging.info(f"Creating compressed archive (level {compression_level})...")
                
                with tarfile.open(archive_path, "w:gz", compresslevel=compression_level) as tar:
                    tar.add(local_download_path, arcname=os.path.basename(path))
                
                archive_size = os.path.getsize(archive_path)
                compression_ratio = (1 - archive_size / total_size) * 100 if total_size > 0 else 0
                logging.info(f"Archive created: {archive_size/1024/1024:.2f}MB (compression: {compression_ratio:.1f}%)")
                
                # Upload compressed archive
                logging.info("Uploading compressed archive...")
                with open(archive_path, 'rb') as archive_file:
                    target_ftp.storbinary(f'STOR {os.path.basename(archive_path)}', archive_file, blocksize=8192)
                
                logging.info("Compressed upload completed")
                logging.info("Note: Archive needs to be extracted on the target server")
                
            else:
                # Direct upload without compression
                logging.info("Uploading directory structure...")
                upload_ftp_directory(target_ftp, local_download_path, path)
            
            upload_duration = time.time() - start_upload
            logging.info(f"Upload completed in {upload_duration:.2f} seconds")
            success = True
        
        if success:
            report.transferred_size_bytes = total_size
            report.complete(True)
            
            # Calculate and log performance metrics
            total_duration = report.get_duration()
            if total_duration > 0:
                speed_mbps = (total_size / (1024*1024)) / total_duration
                logging.info(f"Average transfer speed: {speed_mbps:.2f} MB/s")
            
            logging.info("FTP transfer completed successfully")
        else:
            report.complete(False)
            logging.error("FTP transfer failed")
            
    except Exception as e:
        error_msg = f"FTP transfer failed: {str(e)}"
        report.add_error(error_msg)
        report.complete(False)
        logging.error(error_msg)
        
        # Log stack trace for debugging
        import traceback
        logging.debug(traceback.format_exc())
        
    finally:
        # Close FTP connections gracefully
        if source_ftp:
            try:
                source_ftp.quit()
                logging.debug("Source FTP connection closed")
            except:
                try:
                    source_ftp.close()
                except:
                    pass
                    
        if target_ftp:
            try:
                target_ftp.quit()
                logging.debug("Target FTP connection closed")
            except:
                try:
                    target_ftp.close()
                except:
                    pass
        
        # Clean up temporary files for this transfer
        if transfer_temp_dir and cleanup_temp_files:
            try:
                if os.path.exists(transfer_temp_dir):
                    shutil.rmtree(transfer_temp_dir)
                    logging.info(f"Temporary files cleaned up from {transfer_temp_dir}")
            except Exception as e:
                logging.warning(f"Could not clean up temporary files from {transfer_temp_dir}: {str(e)}")
    
    logging.info(f"--- FTP Transfer Complete: {path} ---")
    return report

def transfer_in_chunks_ftp(local_path, target_ftp, remote_path, max_chunk_size, compression_level, report):
    """Transfer directory in chunks using FTP with proper implementation.
    
    This function splits large directories into smaller chunks based on file size,
    compresses each chunk separately, and uploads them to avoid memory issues.
    
    Args:
        local_path: Local directory path
        target_ftp: Target FTP connection
        remote_path: Remote directory path
        max_chunk_size: Maximum size for each chunk in bytes
        compression_level: Compression level (1-9)
        report: TransferReport object for tracking progress
        
    Returns:
        True if successful, False otherwise
    """
    try:
        logging.info(f"Starting chunked transfer with max chunk size: {max_chunk_size/1024/1024:.2f}MB")
        
        # Collect all files with their sizes
        all_files = []
        for root, dirs, files in os.walk(local_path):
            for filename in files:
                filepath = os.path.join(root, filename)
                filesize = os.path.getsize(filepath)
                rel_path = os.path.relpath(filepath, local_path)
                all_files.append((filepath, rel_path, filesize))
        
        # Sort by size to better distribute chunks
        all_files.sort(key=lambda x: x[2], reverse=True)
        
        # Create chunks
        chunks = []
        current_chunk = []
        current_chunk_size = 0
        chunk_num = 0
        
        for filepath, rel_path, filesize in all_files:
            # If adding this file exceeds chunk size and current chunk is not empty, start new chunk
            if current_chunk_size + filesize > max_chunk_size and current_chunk:
                chunks.append((chunk_num, current_chunk))
                chunk_num += 1
                current_chunk = []
                current_chunk_size = 0
            
            current_chunk.append((filepath, rel_path))
            current_chunk_size += filesize
        
        # Add the last chunk if not empty
        if current_chunk:
            chunks.append((chunk_num, current_chunk))
        
        logging.info(f"Created {len(chunks)} chunks for transfer")
        
        # Process each chunk
        chunk_temp_dir = tempfile.mkdtemp(prefix="chunk_")
        
        try:
            for chunk_num, chunk_files in chunks:
                logging.info(f"Processing chunk {chunk_num + 1}/{len(chunks)} ({len(chunk_files)} files)")
                
                # Create chunk directory structure
                chunk_dir = os.path.join(chunk_temp_dir, f"chunk_{chunk_num}")
                os.makedirs(chunk_dir, exist_ok=True)
                
                # Copy files to chunk directory maintaining structure
                for filepath, rel_path in chunk_files:
                    dest_path = os.path.join(chunk_dir, rel_path)
                    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                    shutil.copy2(filepath, dest_path)
                
                # Compress chunk
                archive_name = f"chunk_{chunk_num}.tar.gz"
                archive_path = os.path.join(chunk_temp_dir, archive_name)
                
                logging.info(f"Compressing chunk {chunk_num + 1}...")
                with tarfile.open(archive_path, "w:gz", compresslevel=compression_level) as tar:
                    tar.add(chunk_dir, arcname=f"chunk_{chunk_num}")
                
                # Upload compressed chunk
                logging.info(f"Uploading chunk {chunk_num + 1}...")
                with open(archive_path, 'rb') as f:
                    target_ftp.storbinary(f'STOR {archive_name}', f, blocksize=8192)
                
                # Clean up chunk files after successful upload
                shutil.rmtree(chunk_dir)
                os.remove(archive_path)
                
                logging.info(f"Chunk {chunk_num + 1}/{len(chunks)} completed")
            
            logging.info("All chunks transferred successfully")
            logging.info("Note: Chunks need to be extracted and merged on the target server")
            return True
            
        finally:
            # Clean up temp directory
            if os.path.exists(chunk_temp_dir):
                shutil.rmtree(chunk_temp_dir)
        
    except Exception as e:
        logging.error(f"Chunked FTP transfer failed: {str(e)}")
        return False