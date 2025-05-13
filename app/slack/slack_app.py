import os
import sys
import json
import re
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

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

# Initialize cache for search results
search_cache = defaultdict(dict)
CACHE_EXPIRY = timedelta(hours=1)  # Cache results for 1 hour

# Track the last search for each user
user_last_search = {}

def is_followup_question(text):
    """Check if the message is likely a follow-up question."""
    followup_phrases = [
        "what about", "tell me more", "explain", "how about",
        "what else", "and", "also", "more", "further",
        "additionally", "what happened", "show me", "find",
        "search", "look up", "check", "can you", "could you",
        "please", "help me", "i need", "i want to know",
        "why", "how", "when", "where", "who", "what",
        "show", "details", "error", "issue", "problem",
        "failed", "failure", "exception", "stack trace"
    ]
    text_lower = text.lower()
    return any(phrase in text_lower for phrase in followup_phrases) or text_lower.endswith('?')

def extract_search_id(text):
    """Extract a search ID from the text if present."""
    # Look for a 12+ digit number
    match = re.search(r'\b\d{12,}\b', text)
    return match.group(0) if match else None

@app.event("message")
def handle_message_events(body, say):
    """Handle regular message events for follow-up questions."""
    logger.info(f"Received message event: {body}")
    
    # Ignore messages from bots to prevent loops
    if body.get('bot_id'):
        logger.debug("Ignoring bot message")
        return
        
    # Get the message text and user
    text = body.get('text', '').strip()
    user_id = body.get('user')
    channel = body.get('channel')
    
    logger.info(f"Processing message from user {user_id} in channel {channel}: {text}")
    
    # Check if this is a follow-up question
    if not is_followup_question(text):
        logger.debug("Not a follow-up question, ignoring")
        return
        
    # Get the user's last search
    last_search = user_last_search.get(user_id)
    if not last_search:
        logger.info(f"No previous search found for user {user_id}")
        say("I don't have any previous search to follow up on. Please use `/loki` or `/lokilens` to start a new search.")
        return
        
    try:
        # Use the last search parameters
        search_id = last_search['search_id']
        time_range = last_search['time_range']
        
        logger.info(f"Processing follow-up question for search_id: {search_id}, time_range: {time_range}")
        
        # Check cache for the results
        cached_data = get_cached_results(search_id, time_range)
        if cached_data:
            logger.info("Using cached results for follow-up question")
            # Create a prompt for the follow-up question
            prompt = f"""
            Based on the previous search results for ID {search_id}, please answer this follow-up question:
            {text}
            
            Focus specifically on what was asked in the question. If the question is about errors or issues, provide detailed information about:
            1. The exact error message
            2. When and where it occurred
            3. Any relevant context or sequence of events
            4. Any error handling or recovery attempts
            
            Here are the logs to analyze:
            {json.dumps(cached_data['results'], indent=2)}
            """
            
            # Call OpenAI API for the follow-up response
            response = openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant analyzing log data. Provide clear, detailed answers based on the available log information, especially when discussing errors or issues."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000
            )
            
            say(response.choices[0].message.content)
        else:
            logger.info("No cached results found for follow-up question")
            say("I'm sorry, but I can't find the previous search results. Please start a new search using `/loki` or `/lokilens`.")
            
    except Exception as e:
        logger.error(f"Error processing follow-up question: {str(e)}", exc_info=True)
        say(f"Error processing your question: {str(e)}")

def cache_search_results(search_id, time_range, results):
    """Cache search results with timestamp."""
    cache_key = f"{search_id}_{time_range}"
    search_cache[cache_key] = {
        'results': results,
        'timestamp': datetime.now(),
        'summary': None  # Will store the AI summary
    }
    logger.info(f"Cached search results for {cache_key}")

def get_cached_results(search_id, time_range):
    """Get cached results if they exist and haven't expired."""
    cache_key = f"{search_id}_{time_range}"
    cached_data = search_cache.get(cache_key)
    
    if cached_data:
        # Check if cache has expired
        if datetime.now() - cached_data['timestamp'] < CACHE_EXPIRY:
            logger.info(f"Retrieved cached results for {cache_key}")
            return cached_data
        else:
            # Remove expired cache entry
            del search_cache[cache_key]
            logger.info(f"Cache expired for {cache_key}")
    
    return None

def generate_response(search_id, results, time_range, is_followup=False):
    """Generate a lively response using OpenAI based on the search results."""
    logger.info(f"Generating response for search_id: {search_id} (followup: {is_followup})")
    
    if not results:
        logger.warning(f"No logs found for ID: {search_id}")
        return f"No logs found for ID: {search_id}. Would you like to try another search?"
    
    # Format the results for the prompt
    logger.debug("Formatting results for OpenAI prompt")
    formatted_results = ""
    for container, logs in results.items():
        formatted_results += f"Container: {container} ({len(logs)} matches)\n"
        for log in logs:
            # Handle both string and dictionary log entries
            if isinstance(log, dict):
                log_str = json.dumps(log, indent=2)
            else:
                log_str = str(log)
            formatted_results += f"{log_str}\n"
    
    # Create a prompt for OpenAI
    prompt = f"""
    I searched for logs with ID: {search_id}. Here are the results:
    {formatted_results}
    
    Please provide:
    1. A concise summary of what happened
    2. Any errors or issues found
    3. Suggested follow-up actions or questions
    
    If this is a follow-up question, focus on providing additional insights or analysis based on the existing logs.
    """
    
    logger.debug("Sending request to OpenAI")
    # Call OpenAI API
    response = openai_client.chat.completions.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500
    )
    
    summary = response.choices[0].message.content
    
    # Cache the summary
    cache_key = f"{search_id}_{time_range}"
    if cache_key in search_cache:
        search_cache[cache_key]['summary'] = summary
    
    # Add a reference to the cached results
    if not is_followup:
        summary += f"\n\n💡 You can ask follow-up questions about these logs by just typing your question in the channel."
    
    return summary

def parse_natural_language_input(text):
    """Use AI to parse natural language input into search_id and time_range."""
    logger.info(f"Parsing natural language input: {text}")
    
    # Check if this is a follow-up question
    is_followup = any(phrase in text.lower() for phrase in [
        "what about", "tell me more", "explain", "how about",
        "what else", "and", "also", "more", "further",
        "additionally", "what happened", "show me", "find",
        "search", "look up", "check"
    ])
    
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
                return search_id, time_range, is_followup
        except Exception as e:
            logger.warning(f"First parsing attempt failed: {str(e)}")
            
        try:
            # Second try: look for patterns in the text
            search_id_match = re.search(r'search_id:\s*(\S+)', result)
            time_range_match = re.search(r'time_range:\s*([^\n]+)', result)
            
            if search_id_match and time_range_match:
                search_id = search_id_match.group(1)
                time_range = time_range_match.group(1)
                logger.info(f"Successfully parsed input using regex - search_id: {search_id}, time_range: {time_range}")
                return search_id, time_range, is_followup
        except Exception as e:
            logger.warning(f"Second parsing attempt failed: {str(e)}")
            
        # If all parsing attempts fail, try to extract just the ID and use current time
        import re
        id_match = re.search(r'\b\d+\b', text)
        if id_match:
            search_id = id_match.group(0)
            time_range = datetime.now().strftime('%Y%m%d%H%M')
            logger.info(f"Using fallback parsing - search_id: {search_id}, time_range: {time_range}")
            return search_id, time_range, is_followup
            
        raise ValueError("Could not parse the input into a search ID and time range")
        
    except Exception as e:
        logger.error(f"Error parsing natural language input: {str(e)}")
        raise ValueError(f"Could not understand the input. Please try again with a clearer format. Example: '12345 happened yesterday at 3pm'")

@app.command("/loki")
def handle_loki_command(ack, body, say):
    """Handle the /loki command in Slack"""
    logger.info(f"Received /loki command: {body}")
    
    # Get the command text from the user
    command_text = body.get('text', '').strip()
    user_id = body.get('user_id')
    logger.debug(f"Command text: {command_text}")
    
    if not command_text:
        logger.warning("Empty command text received")
        ack("Please provide a search ID and time information. Example: `/loki 12345 happened yesterday at 3pm`")
        return
    
    try:
        # Acknowledge the command with the original text
        ack(f"Searching logs for: {command_text}")
        
        # Parse the natural language input using AI
        logger.info("Starting natural language parsing")
        search_id, time_range, is_followup = parse_natural_language_input(command_text)
        logger.info(f"Parsed input - search_id: {search_id}, time_range: {time_range}, is_followup: {is_followup}")
        
        # Store the search parameters for this user
        user_last_search[user_id] = {
            'search_id': search_id,
            'time_range': time_range,
            'timestamp': datetime.now()
        }
        
        # Check cache for follow-up questions
        if is_followup:
            cached_data = get_cached_results(search_id, time_range)
            if cached_data:
                logger.info("Using cached results for follow-up question")
                response = generate_response(search_id, cached_data['results'], time_range, is_followup=True)
                say(response)
                return
        
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
        
        # Cache the results
        cache_search_results(search_id, time_range, log_results)
        
        # Generate a lively response using OpenAI
        logger.info("Generating response")
        response = generate_response(search_id, log_results, time_range)
        logger.info("Sending response to Slack")
        say(response)
            
    except Exception as e:
        logger.error(f"Error processing command: {str(e)}", exc_info=True)
        say(f"Error processing command: {str(e)}")

@app.command("/lokilens")
def handle_lokilens_command(ack, body, say):
    """Handle the /lokilens command in Slack"""
    logger.info(f"Received /lokilens command: {body}")
    
    # Get the command text from the user
    command_text = body.get('text', '').strip()
    user_id = body.get('user_id')
    logger.debug(f"Command text: {command_text}")
    
    if not command_text:
        logger.warning("Empty command text received")
        ack("Please provide a search ID and time information. Example: `/lokilens 12345 happened yesterday at 3pm`")
        return
    
    try:
        # Acknowledge the command with the original text
        ack(f"Searching logs for: {command_text}")
        
        # Parse the natural language input using AI
        logger.info("Starting natural language parsing")
        search_id, time_range, is_followup = parse_natural_language_input(command_text)
        logger.info(f"Parsed input - search_id: {search_id}, time_range: {time_range}, is_followup: {is_followup}")
        
        # Store the search parameters for this user
        user_last_search[user_id] = {
            'search_id': search_id,
            'time_range': time_range,
            'timestamp': datetime.now()
        }
        
        # Check cache for follow-up questions
        if is_followup:
            cached_data = get_cached_results(search_id, time_range)
            if cached_data:
                logger.info("Using cached results for follow-up question")
                response = generate_response(search_id, cached_data['results'], time_range, is_followup=True)
                say(response)
                return
        
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
        
        # Cache the results
        cache_search_results(search_id, time_range, log_results)
        
        # Generate a lively response using OpenAI
        logger.info("Generating response")
        response = generate_response(search_id, log_results, time_range)
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