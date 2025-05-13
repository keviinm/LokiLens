import os
import sys
from pathlib import Path

# Add the project root to Python path
project_root = str(Path(__file__).parent.parent.parent)
sys.path.append(project_root)

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from dotenv import load_dotenv
from app.logsearch.s3_operations import S3Operations
from app.logsearch.log_search import search_logs
from openai import OpenAI
from app.mcp.mcp_client import LogSearchClient
from datetime import datetime
from app.utils.logging_config import setup_logging

# Setup logging
loggers = setup_logging()
logger = loggers['slack']

# Load environment variables
logger.info("Loading environment variables...")
load_dotenv()
logger.info("Environment variables loaded successfully")

# Initialize the Slack app
logger.info("Initializing Slack app...")
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))
logger.info("Slack app initialized successfully")

# Initialize S3 operations
logger.info("Initializing S3 operations...")
s3_ops = S3Operations(
    aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY")
)
logger.info("S3 operations initialized successfully")

# Initialize OpenAI client
logger.info("Initializing OpenAI client...")
openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
logger.info("OpenAI client initialized successfully")

# Initialize MCP client
logger.info("Initializing MCP client...")
mcp_client = LogSearchClient(openai_api_key=os.environ.get("OPENAI_API_KEY"))
logger.info("MCP client initialized successfully")

def generate_response(search_id, results):
    """Generate a lively response using OpenAI based on the search results."""
    logger.info(f"Generating response for search_id: {search_id}")
    
    if not results:
        logger.warning(f"No logs found for ID: {search_id}")
        return f"No logs found for ID: {search_id}. Would you like to try another search?"
    
    # Format the results for the prompt
    logger.debug("Formatting results for OpenAI prompt")
    formatted_results = ""
    for container, logs in results.items():
        formatted_results += f"Container: {container} ({len(logs)} matches)\n"
        for log in logs:
            formatted_results += f"{log}\n"
    
    # Create a prompt for OpenAI
    prompt = f"""
    I searched for logs with ID: {search_id}. Here are the results:
    {formatted_results}
    Can you summarize these logs and suggest any follow-up actions or questions?
    """
    
    logger.debug("Sending request to OpenAI")
    # Call OpenAI API
    response = openai_client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=150
    )
    
    logger.info("Successfully generated response from OpenAI")
    return response.choices[0].message.content

def parse_natural_language_input(text):
    """Use AI to parse natural language input into search_id and time_range."""
    logger.info(f"Parsing natural language input: {text}")
    
    prompt = f"""
    Parse the following text into a search ID and a time range.
    The time range should be in the format YYYYMMDDHHMM (e.g., 202205130933 for May 13, 2022 at 09:33).
    If the time is not specified, use the current time.
    If the date is not specified, use today's date.
    
    Text: {text}
    
    Return ONLY the search ID and time range in this exact format:
    search_id: <id>
    time_range: <YYYYMMDDHHMM>
    
    Do not include any other text or explanation.
    """
    
    try:
        logger.debug("Sending request to OpenAI for parsing")
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=100
        )
        
        # Parse the response
        result = response.choices[0].message.content.strip()
        logger.debug(f"Received parsing response: {result}")
        
        # Try different parsing approaches
        try:
            # First try: exact format
            lines = result.split('\n')
            if len(lines) >= 2:
                search_id = lines[0].split(': ')[1].strip()
                time_range = lines[1].split(': ')[1].strip()
                logger.info(f"Successfully parsed input - search_id: {search_id}, time_range: {time_range}")
                return search_id, time_range
        except Exception as e:
            logger.warning(f"First parsing attempt failed: {str(e)}")
            
        try:
            # Second try: look for patterns in the text
            import re
            search_id_match = re.search(r'search_id:\s*(\S+)', result)
            time_range_match = re.search(r'time_range:\s*([^\n]+)', result)
            
            if search_id_match and time_range_match:
                search_id = search_id_match.group(1)
                time_range = time_range_match.group(1)
                logger.info(f"Successfully parsed input using regex - search_id: {search_id}, time_range: {time_range}")
                return search_id, time_range
        except Exception as e:
            logger.warning(f"Second parsing attempt failed: {str(e)}")
            
        # If all parsing attempts fail, try to extract just the ID and use current time
        import re
        id_match = re.search(r'\b\d+\b', text)
        if id_match:
            search_id = id_match.group(0)
            time_range = datetime.now().strftime('%Y%m%d%H%M')
            logger.info(f"Using fallback parsing - search_id: {search_id}, time_range: {time_range}")
            return search_id, time_range
            
        raise ValueError("Could not parse the input into a search ID and time range")
        
    except Exception as e:
        logger.error(f"Error parsing natural language input: {str(e)}")
        raise ValueError(f"Could not understand the input. Please try again with a clearer format. Example: '12345 happened yesterday at 3pm'")

@app.command("/loki")
def handle_loki_command(ack, body, say):
    """Handle the /loki command in Slack"""
    logger.info(f"Received /loki command: {body}")
    ack()
    
    # Get the command text from the user
    command_text = body.get('text', '').strip()
    logger.debug(f"Command text: {command_text}")
    
    if not command_text:
        logger.warning("Empty command text received")
        say("Please provide a search ID and time information. Example: `/loki 12345 happened yesterday at 3pm`")
        return
    
    try:
        # Parse the natural language input using AI
        logger.info("Starting natural language parsing")
        search_id, time_range = parse_natural_language_input(command_text)
        logger.info(f"Parsed input - search_id: {search_id}, time_range: {time_range}")
        
        # Search for logs using MCP client
        logger.info("Searching logs using MCP client")
        results = mcp_client.search_logs(search_id, [time_range])
        logger.debug(f"MCP client response: {results}")
        
        # Check if there was an error
        if "error" in results:
            logger.error(f"MCP client error: {results['error']}")
            say(f"Error searching logs: {results['error']}")
            return
            
        # Get the actual results
        log_results = results.get("results", {})
        logger.info(f"Found {len(log_results)} containers with logs")
        
        # Generate a lively response using OpenAI
        logger.info("Generating response")
        response = generate_response(search_id, log_results)
        logger.info("Sending response to Slack")
        say(response)
            
    except Exception as e:
        logger.error(f"Error processing command: {str(e)}", exc_info=True)
        say(f"Error processing command: {str(e)}")

@app.command("/lokilens")
def handle_lokilens_command(ack, body, say):
    """Handle the /lokilens command in Slack"""
    logger.info(f"Received /lokilens command: {body}")
    ack()
    
    # Get the command text from the user
    command_text = body.get('text', '').strip()
    logger.debug(f"Command text: {command_text}")
    
    if not command_text:
        logger.warning("Empty command text received")
        say("Please provide a search ID and time information. Example: `/lokilens 12345 happened yesterday at 3pm`")
        return
    
    try:
        # Parse the natural language input using AI
        logger.info("Starting natural language parsing")
        search_id, time_range = parse_natural_language_input(command_text)
        logger.info(f"Parsed input - search_id: {search_id}, time_range: {time_range}")
        
        # Search for logs using MCP client
        logger.info("Searching logs using MCP client")
        results = mcp_client.search_logs(search_id, [time_range])
        logger.debug(f"MCP client response: {results}")
        
        # Check if there was an error
        if "error" in results:
            logger.error(f"MCP client error: {results['error']}")
            say(f"Error searching logs: {results['error']}")
            return
            
        # Get the actual results
        log_results = results.get("results", {})
        logger.info(f"Found {len(log_results)} containers with logs")
        
        # Generate a lively response using OpenAI
        logger.info("Generating response")
        response = generate_response(search_id, log_results)
        logger.info("Sending response to Slack")
        say(response)
            
    except Exception as e:
        logger.error(f"Error processing command: {str(e)}", exc_info=True)
        say(f"Error processing command: {str(e)}")

def start_slack_app():
    """Start the Slack app in Socket Mode"""
    logger.info("Starting Slack app in Socket Mode")
    handler = SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))
    handler.start()
    logger.info("Slack app started successfully")

if __name__ == "__main__":
    logger.info("Starting application...")
    start_slack_app() 