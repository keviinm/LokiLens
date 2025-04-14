import os
import logging
from typing import List
from collections import defaultdict
from dotenv import load_dotenv

from s3_operations import S3Operations
from log_processor import LogProcessor

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for more detailed logging
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_config():
    """Load configuration from environment variables."""
    load_dotenv()
    return {
        'aws_access_key_id': os.getenv('AWS_ACCESS_KEY_ID'),
        'aws_secret_access_key': os.getenv('AWS_SECRET_ACCESS_KEY'),
        'bucket_name': os.getenv('BUCKET_NAME')
    }

def main():
    logger.info("🚀 Starting S3 log search script...")
    
    # Load configuration
    config = load_config()
    if not all(config.values()):
        logger.error("Missing required environment variables")
        return

    # Initialize S3 operations
    s3_ops = S3Operations(
        aws_access_key_id=config['aws_access_key_id'],
        aws_secret_access_key=config['aws_secret_access_key']
    )

    # First, let's see what's in the bucket
    logger.info("🔍 Listing bucket contents to understand structure...")
    s3_ops.list_bucket_contents(config['bucket_name'])

    # Search parameters
    search_id = "672375962477797376"
    
    # Let's try searching with different prefixes
    prefixes = [
        "kubernetes.var.log.containers",
        "logs",
        ""  # root level
    ]
    
    for prefix in prefixes:
        logger.info(f"\n🔍 Searching with prefix: {prefix}")
        files = s3_ops.list_bucket_contents(config['bucket_name'], prefix)
        
        if files:
            logger.info(f"Found {len(files)} files with prefix {prefix}")
            # Process each file
            final_grouped_logs = defaultdict(list)
            for log_file in files:
                logger.info(f"📜 Processing file: {log_file}")
                try:
                    file_content = s3_ops.get_file_content(config['bucket_name'], log_file)
                    grouped_matches = LogProcessor.process_gzipped_logs(file_content, search_id)
                    
                    # Merge results
                    for container, logs in grouped_matches.items():
                        final_grouped_logs[container].extend(logs)
                        
                except Exception as e:
                    logger.error(f"Error processing file {log_file}: {e}")

            # Display results
            if final_grouped_logs:
                logger.info("\n✅ Grouped Log Matches by container_name:")
                for container, logs in final_grouped_logs.items():
                    logger.info(f"\n🛠️ Container: {container} ({len(logs)} matches)")
                    for log in logs:
                        logger.info(log)
                break  # Stop searching if we found matches
            else:
                logger.info(f"No matches found with prefix {prefix}")

if __name__ == "__main__":
    main() 