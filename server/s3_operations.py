import boto3
import logging
from typing import List
from botocore.exceptions import ClientError

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class S3Operations:
    def __init__(self, aws_access_key_id: str, aws_secret_access_key: str):
        """Initialize S3 client with AWS credentials."""
        self.s3_client = boto3.client(
            's3',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key
        )

    def list_bucket_contents(self, bucket: str, prefix: str = '') -> List[str]:
        """
        List all contents of the bucket for debugging.
        
        Args:
            bucket: S3 bucket name
            prefix: Optional prefix to filter results
            
        Returns:
            List of all keys in the bucket
        """
        try:
            logger.info(f"Listing contents of bucket {bucket} with prefix {prefix}")
            response = self.s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
            
            if "Contents" in response:
                keys = [obj["Key"] for obj in response["Contents"]]
                logger.info(f"Found {len(keys)} objects in bucket")
                for key in keys:
                    logger.info(f"  - {key}")
                return keys
            else:
                logger.info("No objects found in bucket")
                return []
            
        except ClientError as e:
            logger.error(f"Error listing bucket contents: {e}")
            return []

    def list_files_for_date(self, bucket: str, date_prefix: str) -> List[str]:
        """
        List all S3 files matching the given date.
        
        Args:
            bucket: S3 bucket name
            date_prefix: Date prefix to search for
            
        Returns:
            List of file keys matching the prefix
        """
        try:
            # Try different path patterns
            prefixes = [
                f"logs/{date_prefix}",
                f"kubernetes.var.log.containers/{date_prefix}",
                date_prefix  # Try without any prefix
            ]
            
            all_files = []
            for prefix in prefixes:
                logger.debug(f"Trying prefix: {prefix}")
                response = self.s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
                
                if "Contents" in response:
                    files = [obj["Key"] for obj in response["Contents"]]
                    logger.info(f"Found {len(files)} files with prefix {prefix}")
                    all_files.extend(files)
            
            return all_files
            
        except ClientError as e:
            logger.error(f"Error listing files for date {date_prefix}: {e}")
            return []

    def get_file_content(self, bucket: str, file_key: str) -> bytes:
        """
        Get the content of an S3 file.
        
        Args:
            bucket: S3 bucket name
            file_key: Key of the file to retrieve
            
        Returns:
            File content as bytes
        """
        try:
            response = self.s3_client.get_object(Bucket=bucket, Key=file_key)
            return response["Body"].read()
        except ClientError as e:
            logger.error(f"Error getting file {file_key}: {e}")
            raise 