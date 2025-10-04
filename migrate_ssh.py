#!/usr/bin/env python3
"""
cPanel Migration Tool - SSH-Based Workflow
Transfers directories between cPanel servers using SSH compression and FTP download.
"""

import argparse
import logging
import os
import sys

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    # If python-dotenv is not available, try to load manually
    try:
        with open('.env', 'r') as f:
            for line in f:
                if '=' in line and not line.strip().startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value
    except FileNotFoundError:
        pass

# Import the SSH-based transfer service
from service_ssh import transfer_directory_ssh

def main():
    """Main migration function using SSH-based workflow."""
    
    # Set up argument parser
    parser = argparse.ArgumentParser(
        description="cPanel Migration Tool - SSH-Based Workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example usage:
  pipenv run python migrate.py --path mail/domain.com/account
  pipenv run python migrate.py --path public_html --verbose
        """
    )
    
    # Path arguments
    parser.add_argument('--path', 
                       help='Path to transfer (relative to home directory)',
                       default=os.getenv('TRANSFER_PATH', ''))
    
    # Output options
    parser.add_argument('--verbose', 
                       action='store_true',
                       help='Enable verbose output (default: False)')
    
    args = parser.parse_args()
    
    # Configure logging based on verbose flag
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Load configuration from environment
    try:
        # Source server configuration
        SOURCE_HOST = os.getenv('SOURCE_HOST')
        SOURCE_PORT = int(os.getenv('SOURCE_SSH_PORT', '22'))
        SOURCE_USER = os.getenv('SOURCE_USER')
        SOURCE_PASS = os.getenv('SOURCE_PASSWORD')
        
        # Target server configuration
        TARGET_HOST = os.getenv('TARGET_HOST')
        TARGET_PORT = int(os.getenv('TARGET_SSH_PORT', '22'))
        TARGET_USER = os.getenv('TARGET_USER')
        TARGET_PASS = os.getenv('TARGET_PASSWORD')
        
        # Transfer path
        path = args.path or os.getenv('TRANSFER_PATH')
        
        # Validate required configuration
        required_vars = [
            ('SOURCE_HOST', SOURCE_HOST),
            ('SOURCE_USER', SOURCE_USER),
            ('SOURCE_PASSWORD', SOURCE_PASS),
            ('TARGET_HOST', TARGET_HOST),
            ('TARGET_USER', TARGET_USER),
            ('TARGET_PASSWORD', TARGET_PASS),
            ('TRANSFER_PATH', path)
        ]
        
        missing_vars = [name for name, value in required_vars if not value]
        if missing_vars:
            print(f"Error: Missing required environment variables: {', '.join(missing_vars)}")
            print("Please check your .env file configuration.")
            return 1
            
    except ValueError as e:
        print(f"Error: Invalid port configuration: {e}")
        return 1
    except Exception as e:
        print(f"Error loading configuration: {e}")
        return 1
    
    # Display configuration summary
    print("=== cPanel Migration Tool - SSH Workflow ===")
    print(f"Source: {SOURCE_USER}@{SOURCE_HOST}:{SOURCE_PORT}")
    print(f"Target: {TARGET_USER}@{TARGET_HOST}:{TARGET_PORT}")
    print(f"Path: {path}")
    print("=" * 45)
    
    try:
        # Execute the SSH-based transfer
        logging.info("Starting SSH-based directory transfer...")
        
        report = transfer_directory_ssh(
            SOURCE_HOST, SOURCE_PORT, SOURCE_USER, SOURCE_PASS,
            TARGET_HOST, TARGET_PORT, TARGET_USER, TARGET_PASS,
            path, cleanup_temp_files=True
        )
        
        # Save transfer report
        report.save_csv_report("transfers_results.csv")
        
        # Display results
        if report.success:
            duration = report.get_duration()
            size_mb = report.total_size_bytes / (1024*1024)
            speed_mbps = (size_mb / duration) if duration > 0 else 0
            
            print(f"\n✅ Transfer completed successfully!")
            print(f"📁 Files transferred: {report.file_count}")
            print(f"📊 Total size: {size_mb:.2f} MB")
            print(f"⏱️  Duration: {duration:.2f} seconds")
            print(f"🚀 Average speed: {speed_mbps:.2f} MB/s")
            print(f"📋 Report saved to: transfers_results.csv")
            return 0
        else:
            print(f"\n❌ Transfer failed!")
            if report.errors:
                print("Errors:")
                for error in report.errors:
                    print(f"  - {error}")
            return 1
            
    except KeyboardInterrupt:
        print("\n⚠️  Transfer interrupted by user")
        return 1
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        logging.error(f"Unexpected error: {e}")
        return 1

if __name__ == '__main__':
    sys.exit(main())