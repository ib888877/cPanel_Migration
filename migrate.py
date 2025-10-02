# Updated cpanel_transfer.py

import os
import sys
import logging
import argparse
import json
import datetime
from service_ftp import (
    transfer_directory, 
    TransferReport
)

# Pipenv automatically loads .env file when using 'pipenv run' or 'pipenv shell'

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

def validate_environment_variables():
    """Validate that all required environment variables are set."""
    required_vars = [
        "SOURCE_HOST", "SOURCE_USER", "SOURCE_PASSWORD",
        "TARGET_HOST", "TARGET_USER", "TARGET_PASSWORD"
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.getenv(var)
        if not value or value.strip() == "":
            missing_vars.append(var)
    
    if missing_vars:
        logging.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logging.error("Please ensure all required variables are set in your .env file")
        sys.exit(1)
    
    # Validate ports are valid integers
    try:
        source_port = int(os.getenv("SOURCE_PORT", 21))
        target_port = int(os.getenv("TARGET_PORT", 21))
        if not (1 <= source_port <= 65535) or not (1 <= target_port <= 65535):
            logging.error("Port numbers must be between 1 and 65535")
            sys.exit(1)
    except ValueError:
        logging.error("Invalid port number in environment variables")
        sys.exit(1)
    
    logging.info("Environment validation passed")

# Validate environment before proceeding (skip if --help is used)
if not any(arg in sys.argv for arg in ['--help', '-h']):
    validate_environment_variables()

# FTP configuration
SOURCE_HOST = os.getenv("SOURCE_HOST")
SOURCE_PORT = int(os.getenv("SOURCE_PORT", 21))
SOURCE_USER = os.getenv("SOURCE_USER")
SOURCE_PASS = os.getenv("SOURCE_PASSWORD")

TARGET_HOST = os.getenv("TARGET_HOST")
TARGET_PORT = int(os.getenv("TARGET_PORT", 21))
TARGET_USER = os.getenv("TARGET_USER")
TARGET_PASS = os.getenv("TARGET_PASSWORD")

# Transfer Options
# Always clean temp files - no configuration needed
CLEANUP_TEMP_FILES = True
# Fixed report filename - always save to this file
REPORT_FILE = "transfers_results.csv"
USE_CHUNKING = os.getenv("USE_CHUNKING", "true").lower() == "true"
MAX_CHUNK_SIZE = int(os.getenv("MAX_CHUNK_SIZE", 50*1024*1024))  # 50MB default

# Configuration
# Default path to transfer (can be overridden by command line arguments)
PATH = os.getenv("TRANSFER_PATH", "mail/abyar-alrumaila.com")

def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="cPanel Migration Tool - FTP Only")
    
    # Main options
    parser.add_argument(
        "--path", 
        help="Path to transfer (relative to home directory)", 
        default=PATH
    )
    
    # Transfer strategy options
    strategy_group = parser.add_argument_group('Transfer Strategy')
    
    strategy_group.add_argument(
        "--chunking", 
        action="store_true",
        default=USE_CHUNKING,
        help="Use chunking for large directories to manage disk quota (default: from USE_CHUNKING env variable)"
    )
    
    strategy_group.add_argument(
        "--chunk-size", 
        type=int,
        default=MAX_CHUNK_SIZE,
        help="Maximum chunk size in bytes for chunked transfers (default: from MAX_CHUNK_SIZE env variable)"
    )
    
    # Performance and space options
    perf_group = parser.add_argument_group('Performance and Space')
    
    perf_group.add_argument(
        "--compression-level", 
        type=int,
        choices=range(1, 10),
        default=1,
        help="Compression level (1=fastest, 9=smallest, default: 1)"
    )
    
    # Output and cleanup options
    output_group = parser.add_argument_group('Output and Cleanup')
    
    output_group.add_argument(
        "--verbose", 
        action="store_true",
        default=False,
        help="Enable verbose output (default: False)"
    )
    
    return parser.parse_args()


def main():
    """Main execution function with error handling."""
    args = None
    try:
        args = parse_args()
        
        # Configure logging level based on verbose flag
        if args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)
            logging.debug("Verbose logging enabled")
        
        logging.info("=" * 60)
        logging.info("cPanel Migration Tool v2.1 (FTP Only)")
        logging.info("=" * 60)
        logging.info(f"Transfer protocol: FTP")
        
        # Log transfer strategy
        if args.chunking:
            logging.info(f"Transfer strategy: Chunked (max chunk: {args.chunk_size/1024/1024:.2f}MB)")
        else:
            logging.info("Transfer strategy: Standard FTP")
        
        if args.compression_level > 1:
            logging.info(f"Compression: Level {args.compression_level}")
        else:
            logging.info("Compression: Disabled (fastest)")
        
        # Initialize report list
        reports = []
        
        # Validate path is provided
        if not args.path:
            logging.error("No path specified for transfer")
            sys.exit(1)
        
        # Transfer directory
        logging.info(f"Transfer path: {args.path}")
        logging.info("-" * 60)
        
        # Create a custom configuration dictionary from arguments
        transfer_config = {
            'cleanup_temp_files': True,  # Always clean temp files
            'use_chunking': args.chunking,
            'max_chunk_size': args.chunk_size,
            'compression_level': args.compression_level
        }
        
        # Use dictionary unpacking for cleaner code
        dir_report = transfer_directory(
            SOURCE_HOST, SOURCE_PORT, SOURCE_USER, SOURCE_PASS,
            TARGET_HOST, TARGET_PORT, TARGET_USER, TARGET_PASS,
            args.path, **transfer_config
        )
        
        reports.append(dir_report)
        
        if dir_report.success:
            logging.info("✓ Directory transfer completed successfully")
        else:
            logging.error("✗ Directory transfer failed")
            # Log specific errors for better debugging
            if dir_report.errors:
                logging.error("Errors encountered:")
                for error in dir_report.errors:
                    logging.error(f"  - {error}")
        
        # Generate and save individual CSV reports
        for report in reports:
            # Save all transfers to CSV for tracking (both success and failure)
            report.save_csv_report(REPORT_FILE)
        
        # Calculate and display summary statistics
        logging.info("=" * 60)
        logging.info("Transfer Summary")
        logging.info("=" * 60)
        
        total_bytes_transferred = sum(report.transferred_size_bytes for report in reports)
        total_duration = sum(report.get_duration() for report in reports) if reports else 0
        
        # Print detailed summary
        if total_bytes_transferred > 0:
            total_mb = total_bytes_transferred / (1024 * 1024)
            logging.info(f"Total data transferred: {total_mb:.2f} MB")
            
            if total_duration > 0:
                speed_mbps = total_mb / total_duration
                logging.info(f"Average transfer speed: {speed_mbps:.2f} MB/s")
                logging.info(f"Total duration: {total_duration:.2f} seconds")
        
        successful = sum(1 for r in reports if r.success)
        failed = len(reports) - successful
        logging.info(f"Transfers: {successful} successful, {failed} failed")
        logging.info(f"Report saved to: {REPORT_FILE}")
        
        # Check if any transfers failed
        if any(not report.success for report in reports):
            logging.error("=" * 60)
            logging.error("Migration completed with errors. Check the report for details.")
            logging.error("=" * 60)
            sys.exit(1)
        else:
            logging.info("=" * 60)
            logging.info("Migration completed successfully!")
            logging.info("=" * 60)
        
    except KeyboardInterrupt:
        logging.warning("\nMigration interrupted by user")
        sys.exit(130)
    except Exception as e:
        logging.error(f"Migration failed with error: {str(e)}")
        if args and args.verbose:
            import traceback
            logging.error(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()


