import os
from typing import List, Dict, Any
import json
import requests
from dotenv import load_dotenv
import logging
from openai import OpenAI
import sys
import urllib.parse
import sseclient
from datetime import datetime, timedelta
import re

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class LogSearchClient:
    def __init__(
        self,
        mcp_server_url: str = "http://localhost:8000/mcp",
        openai_api_key: str = None,
        default_model: str = "gpt-4-turbo-preview",
        timeout: int = 5
    ):
        logger.info("Initializing LogSearchClient...")
        # Ensure the URL is properly formatted
        self.mcp_server_url = mcp_server_url.rstrip('/')
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.default_model = default_model
        self.timeout = timeout
        
        if not self.openai_api_key:
            raise ValueError("OpenAI API key is required")
        
        logger.info("Initializing OpenAI client...")
        try:
            self.client = OpenAI(api_key=self.openai_api_key)
            logger.info("OpenAI client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {str(e)}")
            raise
        
        logger.info("Initializing MCP tools...")
        try:
            self._init_mcp_tools()
            logger.info("MCP tools initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize MCP tools: {str(e)}")
            raise
    
    def _parse_date(self, date_str: str) -> str:
        """Parse various date formats and convert to YYYYMMDDHHMM format."""
        try:
            # First check if it's already in YYYYMMDDHHMM format
            if re.match(r'^\d{12}$', date_str):
                # Validate the date components
                try:
                    year = int(date_str[0:4])
                    month = int(date_str[4:6])
                    day = int(date_str[6:8])
                    hour = int(date_str[8:10])
                    minute = int(date_str[10:12])
                    
                    # Validate the date components
                    if not (1 <= month <= 12):
                        raise ValueError(f"Invalid month: {month}")
                    if not (1 <= day <= 31):
                        raise ValueError(f"Invalid day: {day}")
                    if not (0 <= hour <= 23):
                        raise ValueError(f"Invalid hour: {hour}")
                    if not (0 <= minute <= 59):
                        raise ValueError(f"Invalid minute: {minute}")
                    
                    return date_str  # Return as is since it's already in the correct format
                except ValueError as e:
                    raise ValueError(f"Invalid timestamp format: {str(e)}")
            
            # Handle relative dates
            if date_str.lower() in ['today', 'now']:
                dt = datetime.now()
            elif date_str.lower() == 'yesterday':
                dt = datetime.now() - timedelta(days=1)
            else:
                # Try to parse the date string
                formats = [
                    '%Y-%m-%d %H:%M',  # 2025-02-02 23:29
                    '%Y-%m-%d',         # 2025-02-02
                    '%Y/%m/%d %H:%M',   # 2025/02/02 23:29
                    '%Y/%m/%d',         # 2025/02/02
                    '%d-%m-%Y %H:%M',   # 02-02-2025 23:29
                    '%d-%m-%Y',         # 02-02-2025
                    '%d/%m/%Y %H:%M',   # 02/02/2025 23:29
                    '%d/%m/%Y',         # 02/02/2025
                    '%B %d, %Y %H:%M',  # February 2, 2025 23:29
                    '%B %d, %Y',        # February 2, 2025
                    '%b %d, %Y %H:%M',  # Feb 2, 2025 23:29
                    '%b %d, %Y',        # Feb 2, 2025
                ]
                
                dt = None
                for fmt in formats:
                    try:
                        dt = datetime.strptime(date_str, fmt)
                        break
                    except ValueError:
                        continue
                
                if dt is None:
                    # Handle month names without day
                    month_pattern = r'(?:January|February|March|April|May|June|July|August|September|October|November|December|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+(\d{4})'
                    match = re.search(month_pattern, date_str, re.IGNORECASE)
                    if match:
                        year = int(match.group(1))
                        month_name = re.search(r'[A-Za-z]+', date_str).group()
                        dt = datetime.strptime(f"{month_name} 1, {year}", "%B %d, %Y")
                    else:
                        raise ValueError("Unrecognized date format")
            
            # If no time is specified, use 00:00
            if dt.hour == 0 and dt.minute == 0:
                return dt.strftime('%Y%m%d0000')
            return dt.strftime('%Y%m%d%H%M')
            
        except Exception as e:
            logger.error(f"Failed to parse date: {str(e)}")
            raise ValueError(f"Could not parse date: {date_str}. Please provide a valid date and time.")
    
    def _init_mcp_tools(self):
        """Initialize MCP tools from the server."""
        try:
            logger.info(f"Connecting to MCP server at {self.mcp_server_url}")
            # Add headers to ensure proper content type
            headers = {
                'Accept': 'text/event-stream',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive'
            }
            
            response = requests.get(
                self.mcp_server_url,
                headers=headers,
                timeout=self.timeout,
                stream=True
            )
            
            logger.info(f"Response status code: {response.status_code}")
            logger.info(f"Response headers: {response.headers}")
            response.raise_for_status()
            
            # Parse SSE response
            client = sseclient.SSEClient(response)
            for event in client.events():
                if event.event == 'endpoint':
                    # Extract the session ID from the endpoint
                    session_id = event.data.split('=')[-1]
                    logger.info(f"Received session ID: {session_id}")
                    # Initialize tools with the session ID
                    self.tools = {
                        "search_logs": {
                            "name": "search_logs",
                            "description": "Search logs by ID and time ranges. REQUIRES both search_id and at least one time_range.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "search_id": {
                                        "type": "string",
                                        "description": "The ID to search for in logs (REQUIRED)"
                                    },
                                    "time_ranges": {
                                        "type": "array",
                                        "items": {
                                            "type": "string"
                                        },
                                        "description": "List of timestamps to search in format YYYYMMDDHHMM (REQUIRED, at least one)"
                                    }
                                },
                                "required": ["search_id", "time_ranges"]
                            }
                        }
                    }
                    break
            else:
                raise ValueError("No endpoint event received from server")
                
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Could not connect to MCP server at {self.mcp_server_url}. Is the server running?"
            logger.error(error_msg)
            logger.error(f"Connection error details: {str(e)}")
            print(f"\nError: {error_msg}")
            print("Please make sure the FastAPI server is running with:")
            print("uvicorn app:app --reload")
            sys.exit(1)
        except requests.exceptions.Timeout:
            error_msg = f"Connection to MCP server timed out after {self.timeout} seconds"
            logger.error(error_msg)
            print(f"\nError: {error_msg}")
            print("Please check if the server is running and accessible")
            sys.exit(1)
        except Exception as e:
            logger.error(f"Failed to initialize MCP tools: {str(e)}")
            raise
    
    def search_logs(self, search_id: str, time_ranges: List[str]) -> Dict[str, Any]:
        """Search logs using the MCP tool."""
        logger.info(f"Searching logs for ID: {search_id} with time ranges: {time_ranges}")
        
        # Validate parameters
        if not search_id:
            raise ValueError("search_id is required")
        if not time_ranges or len(time_ranges) == 0:
            raise ValueError("At least one time_range is required")
        
        try:
            headers = {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }
            # Use the correct endpoint URL without /mcp prefix
            base_url = self.mcp_server_url.replace('/mcp', '')
            response = requests.post(
                f"{base_url}/api/search",
                json={
                    "search_id": search_id,
                    "time_ranges": time_ranges
                },
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            
            # Try to parse the response as JSON
            try:
                result = response.json()
                if isinstance(result, dict):
                    return result
                else:
                    # If it's not a dictionary, wrap it in one
                    return {"results": result}
            except json.JSONDecodeError:
                # If it's not valid JSON, treat it as a string
                return {"results": response.text}
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to search logs: {str(e)}")
            return {"error": str(e), "results": None}
        except Exception as e:
            logger.error(f"Unexpected error while searching logs: {str(e)}")
            return {"error": str(e), "results": None}
    
    def chat_with_logs(self, query: str, model: str = None) -> str:
        """Chat with logs using natural language."""
        model = model or self.default_model
        logger.info(f"Processing chat query: {query}")
        
        # Prepare the system message
        system_message = """You are a helpful assistant that can search and analyze logs.
        You have access to a log search tool that can find logs by ID and time ranges.
        
        IMPORTANT RULES:
        1. You MUST have both a search_id AND at least one time_range before using the search_logs tool
        2. If the user doesn't provide a time range, use 00:00 as the default time
        3. If the user doesn't provide a search ID, you MUST ask for it
        4. Time ranges should be in format YYYYMMDDHHMM
        5. If the user provides a date without time, automatically use 00:00
        6. If the user provides a month without day, use the first day of the month
        7. If the user provides a relative date (e.g., "yesterday", "today"), convert it to absolute date
        8. Support various date formats:
           - YYYY-MM-DD HH:MM
           - YYYY/MM/DD HH:MM
           - DD-MM-YYYY HH:MM
           - DD/MM/YYYY HH:MM
           - Month Day, Year HH:MM (e.g., February 2, 2025 23:29)
           - Month Year (e.g., February 2025)
           - Relative dates (today, yesterday)
        
        When users ask questions about logs, you should:
        1. Extract relevant search IDs and time ranges from their questions
        2. If search ID is missing, ask for it
        3. For dates without time, automatically use 00:00
        4. For months without day, automatically use the first day
        5. Only use the search_logs tool when you have ALL required parameters
        6. Analyze the results and provide a natural language response
        
        Example interactions:
        User: "What happened with transaction 12345 on February 2?"
        Assistant: "I'll search for logs related to transaction 12345 on February 2, 2025 at 00:00..."
        
        User: "Show me logs from February"
        Assistant: "I'll need a transaction ID to search for. Could you please provide one?"
        
        User: "Find logs for ID 12345 at 2025-02-02 23:29"
        Assistant: "I'll search for logs related to transaction 12345 at the specified time..."
        
        User: "What happened with transaction 12345 yesterday?"
        Assistant: "I'll search for logs related to transaction 12345 from yesterday at 00:00..."
        """
        
        # Prepare the tools description
        tools = [{
            "type": "function",
            "function": {
                "name": "search_logs",
                "description": "Search logs by ID and time ranges. REQUIRES both search_id and at least one time_range.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "search_id": {
                            "type": "string",
                            "description": "The ID to search for in logs (REQUIRED)"
                        },
                        "time_ranges": {
                            "type": "array",
                            "items": {
                                "type": "string"
                            },
                            "description": "List of timestamps to search in format YYYYMMDDHHMM (REQUIRED, at least one)"
                        }
                    },
                    "required": ["search_id", "time_ranges"]
                }
            }
        }]
        
        try:
            logger.info("Sending request to OpenAI...")
            # First call to OpenAI
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": query}
                ],
                tools=tools,
                tool_choice="auto"
            )
            
            message = response.choices[0].message
            logger.info(f"Received response from OpenAI: {message.content}")
            
            # If the model wants to use a tool
            if message.tool_calls:
                tool_call = message.tool_calls[0]
                if tool_call.function.name == "search_logs":
                    # Extract parameters
                    args = json.loads(tool_call.function.arguments)
                    logger.info(f"Searching logs with parameters: {args}")
                    
                    # Validate parameters before making the call
                    if not args.get("search_id"):
                        return "I need a search ID to look up the logs. Could you please provide one?"
                    if not args.get("time_ranges") or len(args["time_ranges"]) == 0:
                        return "I need at least one time range to search for the logs. Please provide a timestamp in YYYYMMDDHHMM format."
                    
                    # Parse and validate time ranges
                    try:
                        parsed_time_ranges = [self._parse_date(time_range) for time_range in args["time_ranges"]]
                        args["time_ranges"] = parsed_time_ranges
                    except ValueError as e:
                        return str(e)
                    
                    # Search logs
                    try:
                        search_results = self.search_logs(
                            args["search_id"],
                            args["time_ranges"]
                        )
                        logger.info(f"Search results: {json.dumps(search_results, indent=2)}")
                        
                        # Ensure search_results is a dictionary
                        if isinstance(search_results, str):
                            search_results = {"results": search_results}
                        elif not isinstance(search_results, dict):
                            search_results = {"results": str(search_results)}
                        
                        # Prepare messages for the second OpenAI call
                        messages = [
                            {"role": "system", "content": system_message},
                            {"role": "user", "content": query},
                            {"role": "assistant", "content": message.content, "tool_calls": [tool_call]},
                            {"role": "tool", "content": json.dumps(search_results), "tool_call_id": tool_call.id}
                        ]
                        
                        # Send results back to the model
                        response = self.client.chat.completions.create(
                            model=model,
                            messages=messages
                        )
                        return response.choices[0].message.content
                    except Exception as e:
                        logger.error(f"Failed to process search results: {str(e)}")
                        return f"I found the logs but encountered an error while processing them: {str(e)}"
            
            return message.content if message.content else "I couldn't process your request. Please try again."
            
        except Exception as e:
            logger.error(f"Failed to chat with logs: {str(e)}")
            return f"An error occurred while processing your request: {str(e)}"

def main():
    try:
        logger.info("Starting Log Search Assistant...")
        # Example usage
        client = LogSearchClient()
        
        print("\nWelcome to Log Search Assistant!")
        print("You can ask questions about logs in natural language.")
        print("Example queries:")
        print("- What happened with transaction 672375962477797376 at 2025-02-02 23:29?")
        print("- Show me logs from yesterday")
        print("- Find logs for ID 12345 in February 2025")
        print("Type 'quit' to exit\n")
        
        while True:
            try:
                query = input("\nAsk a question about the logs (or 'quit' to exit): ")
                if query.lower() == 'quit':
                    break
                
                response = client.chat_with_logs(query)
                print(f"\nAssistant: {response}")
                
            except Exception as e:
                print(f"Error: {str(e)}")
                logger.error(f"Error in main loop: {str(e)}")
                
    except Exception as e:
        logger.error(f"Fatal error: {str(e)}")
        print(f"Fatal error: {str(e)}")
        print("Please check the logs for more details.")

if __name__ == "__main__":
    main() 