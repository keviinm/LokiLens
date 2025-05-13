import os
import logging
from dotenv import load_dotenv
import threading

from app.logsearch.s3_operations import S3Operations
from app.slack.slack_app import start_slack_app

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def load_config():
    """Load configuration from environment variables."""
    load_dotenv()
    # Debug prints to check environment variables
    print("SLACK_APP_TOKEN:", os.getenv('SLACK_APP_TOKEN'))
    print("SLACK_BOT_TOKEN:", os.getenv('SLACK_BOT_TOKEN'))
    print("AWS_ACCESS_KEY_ID:", os.getenv('AWS_ACCESS_KEY_ID'))
    print("AWS_SECRET_ACCESS_KEY:", os.getenv('AWS_SECRET_ACCESS_KEY'))
    print("BUCKET_NAME:", os.getenv('BUCKET_NAME'))
    return {
        'aws_access_key_id': os.getenv('AWS_ACCESS_KEY_ID'),
        'aws_secret_access_key': os.getenv('AWS_SECRET_ACCESS_KEY'),
        'bucket_name': os.getenv('BUCKET_NAME'),
        'slack_bot_token': os.getenv('SLACK_BOT_TOKEN'),
        'slack_app_token': os.getenv('SLACK_APP_TOKEN')
    }

def main():
    logger.info("🚀 Starting Loki Lens application...")
    
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

    # Start Slack app in a separate thread
    slack_thread = threading.Thread(target=start_slack_app)
    slack_thread.daemon = True
    slack_thread.start()
    
    logger.info("✅ Slack integration started")
    
    # Keep the main thread running
    try:
        while True:
            pass
    except KeyboardInterrupt:
        logger.info("Shutting down...")

if __name__ == "__main__":
    main() 