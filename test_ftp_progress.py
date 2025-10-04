#!/usr/bin/env python3
"""
Test script for FTP download progress functionality.
This script demonstrates the enhanced progress tracking features.
"""

import os
import sys
import time
import tempfile
from service_ftp import format_bytes, format_time, show_progress

def test_progress_display():
    """Test the progress display functions."""
    print("Testing progress display functions...")
    
    # Test format_bytes
    print("\n--- Testing format_bytes ---")
    test_sizes = [0, 512, 1024, 1024*1024, 1024*1024*1024, 1024*1024*1024*1024]
    for size in test_sizes:
        print(f"{size:>15} bytes = {format_bytes(size)}")
    
    # Test format_time
    print("\n--- Testing format_time ---")
    test_times = [0, 30, 90, 3600, 3661, 7200]
    for seconds in test_times:
        print(f"{seconds:>6} seconds = {format_time(seconds)}")
    
    # Test show_progress with simulated download
    print("\n--- Testing show_progress ---")
    print("Simulating file download progress...")
    
    file_size = 10 * 1024 * 1024  # 10MB file
    start_time = time.time()
    
    # Simulate download in chunks
    chunk_size = 64 * 1024  # 64KB chunks
    downloaded = 0
    
    while downloaded < file_size:
        downloaded += chunk_size
        if downloaded > file_size:
            downloaded = file_size
        
        show_progress(downloaded, file_size, start_time, "test_file.txt")
        time.sleep(0.1)  # Simulate network delay
    
    print("\nProgress display test completed!")

def demo_download_simulation():
    """Demonstrate what FTP download progress would look like."""
    print("\n" + "="*70)
    print("DEMONSTRATION: Simulated FTP Download Progress")
    print("="*70)
    
    # Simulate downloading multiple files
    files = [
        ("config.php", 2048),
        ("database.sql", 5 * 1024 * 1024),
        ("images.zip", 25 * 1024 * 1024),
        ("logs.tar.gz", 8 * 1024 * 1024),
        ("readme.txt", 1024)
    ]
    
    total_files = len(files)
    
    for i, (filename, file_size) in enumerate(files, 1):
        print(f"\n[{i}/{total_files}] Downloading: {filename}")
        
        start_time = time.time()
        downloaded = 0
        
        # Simulate variable download speeds
        if file_size < 1024 * 1024:  # Small files download faster
            chunk_size = 32768
            delay = 0.05
        else:  # Large files with more realistic speeds
            chunk_size = 65536
            delay = 0.1
        
        while downloaded < file_size:
            downloaded += chunk_size
            if downloaded > file_size:
                downloaded = file_size
            
            show_progress(downloaded, file_size, start_time, filename)
            time.sleep(delay)
    
    print(f"\nAll {total_files} files downloaded successfully!")

if __name__ == "__main__":
    print("FTP Progress Display Test")
    print("=" * 50)
    
    try:
        # Run basic tests
        test_progress_display()
        
        # Ask user if they want to see the demo
        response = input("\nWould you like to see a simulated download demo? (y/n): ").lower().strip()
        if response in ['y', 'yes']:
            demo_download_simulation()
        
        print("\nTest completed successfully!")
        
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user.")
    except Exception as e:
        print(f"\nError during test: {e}")
        sys.exit(1)