#!/usr/bin/env python3
"""
Test script to validate enhancements to the cPanel Migration Tool.
Tests connection logic, retry mechanisms, and optimization features.
"""

import unittest
import tempfile
import os
import shutil
from unittest.mock import Mock, patch, MagicMock
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from service_ftp import (
    TransferReport,
    create_ftp_connection,
    download_ftp_file_with_retry,
    upload_ftp_file_with_retry
)


class TestTransferReport(unittest.TestCase):
    """Test TransferReport class enhancements."""
    
    def test_report_initialization(self):
        """Test that report initializes with correct default values."""
        report = TransferReport()
        self.assertEqual(report.protocol_name, "ftp")
        self.assertEqual(report.file_count, 0)
        self.assertEqual(report.directory_count, 0)
        self.assertFalse(report.success)
        self.assertEqual(report.files_completed, 0)
        
    def test_add_error(self):
        """Test error tracking."""
        report = TransferReport()
        report.add_error("Test error")
        self.assertEqual(len(report.errors), 1)
        self.assertIn("Test error", report.errors)
        
    def test_progress_tracking(self):
        """Test progress tracking functionality."""
        report = TransferReport()
        report.file_count = 10
        report.update_progress("test.txt", 5)
        self.assertEqual(report.current_file, "test.txt")
        self.assertEqual(report.files_completed, 5)
        
    def test_duration_calculation(self):
        """Test duration calculation."""
        report = TransferReport()
        import time
        time.sleep(0.1)
        duration = report.get_duration()
        self.assertGreater(duration, 0)
        
    def test_complete_success(self):
        """Test marking transfer as complete."""
        report = TransferReport()
        report.complete(True)
        self.assertTrue(report.success)
        self.assertIsNotNone(report.end_time)


class TestFTPConnectionRetry(unittest.TestCase):
    """Test FTP connection with retry logic."""
    
    @patch('service_ftp.FTP')
    @patch('service_ftp.time.sleep')
    def test_connection_retry_on_failure(self, mock_sleep, mock_ftp):
        """Test that connection retries on failure."""
        # Setup mock to fail twice then succeed
        mock_ftp_instance = MagicMock()
        mock_ftp.return_value = mock_ftp_instance
        mock_ftp_instance.connect.side_effect = [
            Exception("Connection failed"),
            Exception("Connection failed"),
            None  # Success on third attempt
        ]
        
        # This should succeed after retries
        result = create_ftp_connection("test.com", 21, "user", "pass", timeout=30)
        
        # Verify retries occurred
        self.assertEqual(mock_ftp_instance.connect.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)  # Sleep between retries
        
    @patch('service_ftp.FTP')
    def test_connection_success_first_try(self, mock_ftp):
        """Test successful connection on first attempt."""
        mock_ftp_instance = MagicMock()
        mock_ftp.return_value = mock_ftp_instance
        
        result = create_ftp_connection("test.com", 21, "user", "pass", timeout=30)
        
        # Should only try once
        self.assertEqual(mock_ftp_instance.connect.call_count, 1)
        self.assertEqual(mock_ftp_instance.login.call_count, 1)
        
    @patch('service_ftp.FTP')
    @patch('service_ftp.time.sleep')
    def test_connection_fails_after_max_retries(self, mock_sleep, mock_ftp):
        """Test that connection fails after max retries."""
        mock_ftp_instance = MagicMock()
        mock_ftp.return_value = mock_ftp_instance
        mock_ftp_instance.connect.side_effect = Exception("Connection failed")
        
        # This should raise an exception after max retries
        with self.assertRaises(Exception):
            create_ftp_connection("test.com", 21, "user", "pass", timeout=30)


class TestFileTransferRetry(unittest.TestCase):
    """Test file transfer with retry logic."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.test_dir, "test.txt")
        with open(self.test_file, 'w') as f:
            f.write("test content")
    
    def tearDown(self):
        """Clean up test environment."""
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
    
    @patch('service_ftp.time.sleep')
    def test_download_retry_logic(self, mock_sleep):
        """Test download retry logic."""
        mock_ftp = MagicMock()
        mock_ftp.size.return_value = 12  # Match actual content length
        
        dest_file = os.path.join(self.test_dir, "downloaded.txt")
        
        # Create a list to track calls
        call_count = [0]
        
        def retrbinary_side_effect(cmd, callback, blocksize=8192):
            call_count[0] += 1
            if call_count[0] < 3:
                raise Exception("Download failed")
            # On success, write data via callback
            with open(dest_file, 'wb') as f:
                f.write(b"test content")
        
        mock_ftp.retrbinary.side_effect = retrbinary_side_effect
        
        result = download_ftp_file_with_retry(mock_ftp, "remote.txt", dest_file, max_retries=3)
        
        # Should succeed after retries
        self.assertTrue(result)
        self.assertEqual(mock_sleep.call_count, 2)
    
    @patch('service_ftp.time.sleep')
    def test_upload_retry_logic(self, mock_sleep):
        """Test upload retry logic."""
        mock_ftp = MagicMock()
        mock_ftp.storbinary.side_effect = [
            Exception("Upload failed"),
            None  # Success on second attempt
        ]
        
        result = upload_ftp_file_with_retry(mock_ftp, self.test_file, "remote.txt", max_retries=3)
        
        # Should succeed after retry
        self.assertTrue(result)
        self.assertEqual(mock_sleep.call_count, 1)


class TestOptimizations(unittest.TestCase):
    """Test optimization features."""
    
    def test_passive_mode_enabled(self):
        """Test that passive mode is enabled in connections."""
        with patch('service_ftp.FTP') as mock_ftp:
            mock_ftp_instance = MagicMock()
            mock_ftp.return_value = mock_ftp_instance
            
            create_ftp_connection("test.com", 21, "user", "pass")
            
            # Verify passive mode was set
            mock_ftp_instance.set_pasv.assert_called_once_with(True)
    
    def test_binary_mode_enabled(self):
        """Test that binary mode is set for transfers."""
        with patch('service_ftp.FTP') as mock_ftp:
            mock_ftp_instance = MagicMock()
            mock_ftp.return_value = mock_ftp_instance
            
            create_ftp_connection("test.com", 21, "user", "pass")
            
            # Verify binary mode was set
            mock_ftp_instance.voidcmd.assert_called_once_with('TYPE I')


def run_tests():
    """Run all tests and return results."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    suite.addTests(loader.loadTestsFromTestCase(TestTransferReport))
    suite.addTests(loader.loadTestsFromTestCase(TestFTPConnectionRetry))
    suite.addTests(loader.loadTestsFromTestCase(TestFileTransferRetry))
    suite.addTests(loader.loadTestsFromTestCase(TestOptimizations))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
