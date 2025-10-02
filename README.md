# cPanel Migration Tool - FTP Only

A highly optimized Python tool for transferring directories between cPanel servers using FTP protocol only.

## Features

- **FTP-Only Transfer**: No SSH dependencies, works with standard FTP access
- **Enhanced Reliability**: Automatic retry logic with exponential backoff for failed transfers
- **Optimized Performance**: Binary mode, passive mode, and optimized buffer sizes for faster transfers
- **Directory Transfer**: Recursively transfer entire directory structures with progress tracking
- **Compression Support**: Optional tar.gz compression for faster transfers
- **Chunked Transfer**: Handle large directories by splitting into manageable chunks
- **Detailed Reporting**: Track transfer progress and generate comprehensive reports
- **Cross-Platform**: Works on Windows, macOS, and Linux
- **Robust Error Handling**: Better error detection, logging, and recovery mechanisms

## Requirements

- Python 3.6+
- FTP access to both source and target cPanel accounts
- Pipenv (for virtual environment management and automatic .env loading)
- Sufficient local disk space in `tmp_trans/` directory for temporary files during transfer

## Installation

1. **Install Pipenv** (if not already installed):
   ```bash
   pip install pipenv
   ```

2. **Install dependencies and create virtual environment**:
   ```bash
   pipenv install
   ```

3. **Configure environment variables**:
   - Edit the `.env` file with your FTP server credentials

## Environment Configuration

Edit your `.env` file:

```properties
# Source FTP Server
SOURCE_HOST=source.hostgator.com
SOURCE_PORT=21
SOURCE_USER=your_username
SOURCE_PASSWORD=your_password

# Target FTP Server
TARGET_HOST=target.hosting.com
TARGET_PORT=21
TARGET_USER=target_username
TARGET_PASSWORD=target_password

# Transfer Options
TRANSFER_PATH=mail/your-domain.com
USE_CHUNKING=true
MAX_CHUNK_SIZE=52428800
```

## Usage

You can run the tool in two ways with pipenv:

### Option 1: Using pipenv run (recommended)
```bash
pipenv run python migrate.py --path mail/your-domain.com
```

### Option 2: Using pipenv shell
```bash
pipenv shell
python migrate.py --path mail/your-domain.com
```

### Basic Transfer

```bash
pipenv run python migrate.py --path mail/your-domain.com
```
*Results are automatically saved to `transfers_results.csv`*

### Chunked Transfer for Large Directories

```bash
pipenv run python migrate.py --path mail/your-domain.com --chunking --chunk-size 10485760
```

### With Compression

```bash
pipenv run python migrate.py --path mail/your-domain.com --compression-level 6
```

### Verbose Output

```bash
pipenv run python migrate.py --path mail/your-domain.com --verbose
```

## Command Line Options

### Main Options
- `--path PATH`: Directory path to transfer (relative to FTP root)

### Transfer Strategy
- `--chunking`: Enable chunked transfer for large directories
- `--chunk-size SIZE`: Maximum chunk size in bytes (default: 50MB)

### Performance Options
- `--compression-level {1-9}`: Compression level (1=fastest, 9=smallest, default: 1)

### Output and Cleanup
- `--verbose`: Enable detailed logging

## How It Works

1. **Connect**: Establishes FTP connections to both source and target servers with retry logic and timeout management
2. **Analyze**: Calculates directory size and file count using optimized MLSD commands when available
3. **Download**: Downloads the source directory structure via FTP to `tmp_trans/` directory with automatic retry on failure
4. **Process**: Optionally compresses or chunks the data based on size and settings
5. **Upload**: Uploads the processed data to the target server via FTP with progress tracking
6. **Cleanup**: Automatically removes temporary files after transfer
7. **Report**: Generates detailed transfer report with statistics and performance metrics

### Transfer Reliability Features

- **Exponential Backoff**: Failed operations automatically retry with increasing delays (2s, 4s, 8s)
- **Connection Recovery**: Dropped connections are automatically re-established
- **File Verification**: Downloaded files are verified for size match when possible
- **Graceful Degradation**: Falls back to basic FTP commands if modern MLSD is unavailable

## Transfer Strategies

### Standard Transfer
- Best for: Small to medium directories (< 50MB)
- Process: Direct download → optional compression → upload
- Pros: Simple and fast
- Cons: Requires local disk space equal to source directory size

### Chunked Transfer
- Best for: Large directories or limited local disk space
- Process: Download in chunks → compress each chunk → upload chunks
- Pros: Handles very large directories, manages disk space usage
- Cons: More complex, potentially slower

### Compression Options
- **Level 1** (fastest): Minimal compression, fastest processing
- **Level 6** (balanced): Good compression ratio with reasonable speed
- **Level 9** (smallest): Maximum compression, slowest processing

## Limitations

- **Database Transfer**: Not supported - this tool only handles file transfers via FTP
- **SSH/SCP/SFTP**: Not supported in this FTP-only version
- **Large Files**: May be slower than SSH-based methods for very large transfers
- **Temporary Space**: Requires local disk space in `tmp_trans/` directory for temporary files during transfer
- **FTP Limitations**: Subject to FTP timeout and connection stability

## Troubleshooting

### FTP Connection Issues

1. **Verify credentials** in `.env` file
2. **Check FTP service** is enabled on both servers
3. **Firewall settings** - ensure FTP ports (21, and passive ports) are open
4. **Passive vs Active FTP** - most hosting providers use passive FTP
5. **Port configuration** - verify correct FTP ports (usually 21)

### Large File Issues

1. **Use chunking** for directories larger than available local disk space:
   ```bash
   pipenv run python migrate.py --path large-directory --chunking --chunk-size 10485760
   ```

2. **Lower compression level** to reduce processing time:
   ```bash
   pipenv run python migrate.py --path large-directory --compression-level 1
   ```

3. **Ensure sufficient local disk space** for temporary files

### Transfer Failures

1. **Check transfer report** for detailed error information in `transfers_results.csv`
2. **Use verbose logging** for debugging:
   ```bash
   pipenv run python migrate.py --path problem-directory --verbose
   ```

3. **Try smaller subdirectories** individually if large transfers fail
4. **Check FTP timeouts** - some servers have strict timeout limits
5. **Network issues**: The tool now automatically retries failed operations up to 3 times
6. **Check logs**: Review `general.log` for detailed error traces and timing information

### Performance Issues

1. **Slow transfers**: 
   - Verify network speed between servers
   - Try disabling compression (`--compression-level 1`)
   - Check if server has bandwidth limitations
   
2. **Connection drops**:
   - The tool automatically retries with exponential backoff
   - Consider transferring during off-peak hours
   - Check firewall settings for FTP passive mode ports
   
3. **Memory issues**:
   - Use chunked transfer for large directories
   - Reduce chunk size: `--chunk-size 10485760` (10MB)
   - Ensure sufficient disk space in `tmp_trans/`

### Common Error Messages

- **"FTP connection failed"**: Check credentials, hostname, and port
- **"Permission denied"**: Verify FTP user has read/write permissions
- **"Directory not found"**: Ensure the source path exists and is accessible
- **"Disk space exceeded"**: Use chunking or free up local disk space

## Examples

### Transfer Email Directory
```bash
pipenv run python migrate.py --path mail/example.com --chunking
```

### Transfer Website Files
```bash
pipenv run python migrate.py --path public_html --compression-level 6
```

### Transfer Large Directory with Custom Settings
```bash
pipenv run python migrate.py --path backups/large-backup --chunking --chunk-size 5242880 --compression-level 3 --verbose
```

## Transfer Reports

After each transfer, a CSV report is automatically generated and appended to `transfers_results.csv` in the current directory. This allows you to track multiple transfers over time in a single spreadsheet-compatible file.

The CSV contains the following columns:

- **timestamp**: When the report was generated
- **success**: SUCCESS or FAILED
- **protocol**: Transfer protocol used (always "ftp")
- **source_path**: Source directory path
- **target_path**: Target directory path  
- **start_time**: Transfer start time
- **end_time**: Transfer end time
- **duration_seconds**: Transfer duration
- **total_size_mb**: Total directory size in MB
- **transferred_size_mb**: Actual transferred size in MB
- **transfer_speed_mbps**: Transfer speed in MB/s
- **file_count**: Number of files transferred
- **directory_count**: Number of directories
- **errors**: Any error messages (semicolon-separated)

Example CSV output:
```csv
timestamp,success,protocol,source_path,target_path,start_time,end_time,duration_seconds,total_size_mb,transferred_size_mb,transfer_speed_mbps,file_count,directory_count,errors
2025-10-02 14:30:15,SUCCESS,ftp,mail/example.com,mail/example.com,2025-10-02 14:28:30,2025-10-02 14:30:15,105.0,50.0,50.0,0.48,1250,45,
```

## Performance Tips

1. **Use compression** for directories with many text files (emails, logs)
2. **Disable compression** for directories with already compressed files (images, videos)
3. **Use chunking** for very large directories to avoid timeouts and manage disk space
4. **Stable internet connection** is crucial for FTP transfers
5. **Transfer during off-peak hours** for better server performance
6. **Use verbose mode** (`--verbose`) for debugging performance issues

## New in v2.1 - Performance Enhancements

### Reliability Improvements
- **Automatic Retry Logic**: Connections and transfers automatically retry with exponential backoff
- **Better Error Recovery**: More robust handling of network interruptions and timeouts
- **Connection Optimization**: FTP connections use passive mode and binary mode for better compatibility

### Performance Optimizations
- **Optimized Buffer Sizes**: 8KB transfer buffers for optimal throughput
- **MLSD Support**: Uses modern FTP MLSD command when available for faster directory listing
- **Better Progress Tracking**: Real-time progress updates during transfers
- **Chunked Transfer Implementation**: Properly implemented chunked transfer for large directories

### Code Quality
- **Enhanced Logging**: Structured, informative logging with timing information
- **Better Validation**: Input validation and environment variable checking
- **Type Hints**: Improved code documentation and IDE support

## Testing

Run the test suite to verify enhancements:

```bash
python test_enhancements.py
```

This will test:
- Connection retry logic
- File transfer retry mechanisms
- Progress tracking
- Error handling
- Optimization features

## Security Notes

- FTP transfers are not encrypted by default
- Credentials are sent in plain text over FTP
- Consider using secure hosting providers with proper network security
- This tool is designed for trusted server-to-server transfers

## Notes

- This version does not require SSH access or external libraries - uses only built-in Python modules
- All transfers use standard FTP protocol (RFC 959)
- Temporary files are created in `tmp_trans/` directory and automatically cleaned up after each transfer
- The tool automatically handles directory structures and file permissions available via FTP
- Cross-platform compatibility with Windows, macOS, and Linux
- Transfer results are automatically saved to `transfers_results.csv` in the current directory
- **Pipenv automatically loads .env files** - no need for manual environment configuration when using `pipenv run` or `pipenv shell`