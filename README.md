# S3 Log Search Tool

A Python tool for searching and analyzing logs stored in AWS S3 buckets.

## Features

- Search logs across multiple timestamps
- Group logs by container name
- Handle gzipped log files
- Secure credential management using environment variables

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file with your AWS credentials:
```
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_SESSION_TOKEN=your_session_token  # Optional, for temporary credentials
BUCKET_NAME=your_bucket_name
```

## Usage

Run the main script:
```bash
python main.py
```

The script will:
1. Search for logs in the specified time range
2. Process and group logs by container name
3. Display matching logs with their container information

## Project Structure

- `main.py`: Main script that orchestrates the log search process
- `s3_operations.py`: Handles all S3-related operations
- `log_processor.py`: Processes and analyzes log files
- `.env`: Configuration file for AWS credentials
- `requirements.txt`: Project dependencies