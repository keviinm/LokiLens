import boto3
import logging
from typing import List
from botocore.exceptions import ClientError
from app.utils.logging_config import setup_logging

# Setup logging
loggers = setup_logging()
logger = loggers['s3']

class S3Operations:
    def __init__(self, aws_access_key_id=None, aws_secret_access_key=None):
        """Initialize S3 operations with AWS credentials."""
        logger.info("Initializing S3 operations")
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=self.aws_access_key_id,
                aws_secret_access_key=self.aws_secret_access_key
            )
            logger.info("S3 client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize S3 client: {str(e)}", exc_info=True)
            raise

    def list_buckets(self):
        """List all S3 buckets."""
        logger.info("Listing S3 buckets")
        try:
            response = self.s3_client.list_buckets()
            buckets = [bucket['Name'] for bucket in response['Buckets']]
            logger.info(f"Found {len(buckets)} buckets")
            return buckets
        except Exception as e:
            logger.error(f"Error listing buckets: {str(e)}", exc_info=True)
            raise

    def list_objects(self, bucket_name, prefix=''):
        """List objects in an S3 bucket with optional prefix."""
        logger.info(f"Listing objects in bucket {bucket_name} with prefix {prefix}")
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=bucket_name,
                Prefix=prefix
            )
            objects = [obj['Key'] for obj in response.get('Contents', [])]
            logger.info(f"Found {len(objects)} objects")
            return objects
        except Exception as e:
            logger.error(f"Error listing objects: {str(e)}", exc_info=True)
            raise

    def get_object(self, bucket_name, object_key):
        """Get an object from S3."""
        logger.info(f"Getting object {object_key} from bucket {bucket_name}")
        try:
            response = self.s3_client.get_object(
                Bucket=bucket_name,
                Key=object_key
            )
            content = response['Body'].read().decode('utf-8')
            logger.info(f"Successfully retrieved object {object_key}")
            return content
        except Exception as e:
            logger.error(f"Error getting object: {str(e)}", exc_info=True)
            raise

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