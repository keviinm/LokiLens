import logging
from collections import defaultdict
from app.logsearch.s3_operations import S3Operations
from app.logsearch.log_processor import LogProcessor

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def search_logs(search_id: str, bucket_name: str, s3_ops: S3Operations) -> dict:
    """Search logs for a given ID and return grouped results."""
    prefixes = [
        "kubernetes.var.log.containers",
        "logs",
        ""  # root level
    ]
    
    final_grouped_logs = defaultdict(list)
    
    for prefix in prefixes:
        logger.info(f"\n🔍 Searching with prefix: {prefix}")
        files = s3_ops.list_bucket_contents(bucket_name, prefix)
        
        if files:
            logger.info(f"Found {len(files)} files with prefix {prefix}")
            for log_file in files:
                logger.info(f"📜 Processing file: {log_file}")
                try:
                    file_content = s3_ops.get_file_content(bucket_name, log_file)
                    grouped_matches = LogProcessor.process_gzipped_logs(file_content, search_id)
                    
                    for container, logs in grouped_matches.items():
                        final_grouped_logs[container].extend(logs)
                        
                except Exception as e:
                    logger.error(f"Error processing file {log_file}: {e}")

            if final_grouped_logs:
                break  # Stop searching if we found matches
    
    return final_grouped_logs 