from fastapi import FastAPI, Request, Form
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi_mcp import FastApiMCP
import logging
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from s3_operations import S3Operations
from log_processor import LogProcessor
from typing import List, Optional
from pydantic import BaseModel
from mcp_client import LogSearchClient

# Configure logging with more detailed format
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for more detailed logs
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Check required environment variables
required_env_vars = ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_BUCKET_NAME']
missing_vars = [var for var in required_env_vars if not os.getenv(var)]

if missing_vars:
    raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")

# Initialize FastAPI app
app = FastAPI(
    title="LokiLens",
    description="Log Search and Analysis Tool",
    version="1.0.0"
)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Initialize templates
templates = Jinja2Templates(directory="templates")

# Initialize S3 operations
s3_ops = S3Operations(
    aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY')
)

# Initialize log processor
log_processor = LogProcessor()

# Initialize MCP
mcp = FastApiMCP(
    app,
    name="LokiLens MCP",
    description="Model Context Protocol interface for LokiLens log search",
    describe_all_responses=True,
    describe_full_response_schema=True
)

# Pydantic models for request/response
class SearchRequest(BaseModel):
    search_id: str
    time_ranges: List[str]

class LogEntry(BaseModel):
    timestamp: str
    container_name: str
    message: str

class SearchResponse(BaseModel):
    search_id: str
    time_ranges: List[str]
    results: dict[str, List[LogEntry]]
    total_results: int

class ChatQueryRequest(BaseModel):
    query: str

MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "https://lokilens-1.onrender.com/mcp")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

def parse_timestamp(timestamp_str: str) -> datetime:
    """Parse timestamp in various formats to datetime object."""
    logger.debug(f"Attempting to parse timestamp: {timestamp_str}")
    
    formats = [
        "%Y%m%d%H%M",  # YYYYMMDDHHMM (for S3 bucket filenames)
        "%Y%m%d%H%M_%S",  # YYYYMMDDHHMM_SS (for S3 bucket filenames with seconds)
        "%Y-%m-%dT%H:%M:%S%z",  # ISO format with timezone
        "%Y-%m-%dT%H:%M:%S",  # ISO format without timezone
        "%Y-%m-%d %H:%M:%S"  # Standard format
    ]
    
    for fmt in formats:
        try:
            parsed = datetime.strptime(timestamp_str, fmt)
            logger.debug(f"Successfully parsed timestamp with format {fmt}: {parsed}")
            return parsed
        except ValueError as e:
            logger.debug(f"Failed to parse with format {fmt}: {str(e)}")
            continue
    
    raise ValueError(f"Invalid timestamp format: {timestamp_str}")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render the home page with search form."""
    return templates.TemplateResponse(
        "home.html",
        {"request": request}
    )

@app.post("/search", response_class=HTMLResponse)
async def search_logs_html(
    request: Request,
    search_id: str = Form(...),
    time_ranges: list = Form(...)
):
    """Search logs for the given ID across multiple time ranges and return HTML results."""
    try:
        results = await search_logs(search_id, time_ranges)
        return templates.TemplateResponse(
            "results.html",
            {
                "request": request,
                "search_id": search_id,
                "results": results["results"],
                "time_ranges": time_ranges
            }
        )
    except Exception as e:
        logger.error(f"Error searching logs: {str(e)}")
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "error": str(e)
            }
        )

@app.post("/api/search", response_model=SearchResponse, operation_id="search_logs")
async def search_logs_api(request: SearchRequest):
    """Search logs for the given ID across multiple time ranges and return JSON results."""
    try:
        logger.info(f"Received API request: search_id={request.search_id}, time_ranges={request.time_ranges}")
        results = await search_logs(request.search_id, request.time_ranges)
        return JSONResponse(content=results)
    except Exception as e:
        logger.error(f"Error searching logs: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )

async def search_logs(search_id: str, time_ranges: list) -> dict:
    """Common search function used by both HTML and API endpoints."""
    all_results = []
    bucket_name = os.getenv('AWS_BUCKET_NAME')
    
    if not bucket_name:
        raise ValueError("AWS bucket name is not configured")
    
    logger.info(f"Starting search for ID: {search_id}")
    logger.info(f"Time ranges: {time_ranges}")
    logger.info(f"Using bucket: {bucket_name}")
    
    for timestamp_str in time_ranges:
        try:
            # Parse the timestamp
            search_time = parse_timestamp(timestamp_str)
            logger.info(f"Searching for timestamp: {search_time}")
            
            # Format the timestamp for S3 filename search
            s3_prefix = search_time.strftime('%Y%m%d%H%M')
            logger.info(f"Searching for S3 files with prefix: {s3_prefix}")
            
            # Search for logs
            results = []
            
            try:
                # List all files in the bucket
                files = s3_ops.list_files_for_date(bucket_name, s3_prefix)
                logger.info(f"Found {len(files) if files else 0} files with prefix {s3_prefix}")
                
                if files:
                    logger.debug(f"Files found: {files}")
                    
                    for file in files:
                        try:
                            logger.info(f"Processing file: {file}")
                            content = s3_ops.get_file_content(bucket_name, file)
                            logger.debug(f"File content length: {len(content) if content else 0}")
                            
                            matches = log_processor.process_gzipped_logs(content, search_id)
                            if matches:
                                logger.info(f"Found matches in file {file}")
                                logger.debug(f"Matches: {matches}")
                                # Convert matches to the expected format
                                for container_name, logs in matches.items():
                                    for log in logs:
                                        results.append({
                                            'container_name': container_name,
                                            'message': log,
                                            'timestamp': timestamp_str
                                        })
                        except Exception as e:
                            logger.error(f"Error processing file {file}: {str(e)}")
                
                if results:
                    all_results.extend(results)
                    logger.info(f"Added {len(results)} results for timestamp {timestamp_str}")
            
            except Exception as e:
                logger.error(f"Error listing files for prefix {s3_prefix}: {str(e)}")
                continue
        
        except ValueError as e:
            logger.warning(f"Invalid timestamp format: {timestamp_str}")
            continue
    
    # Group results by container name
    grouped_results = {}
    for result in all_results:
        container_name = result.get('container_name', 'unknown')
        if container_name not in grouped_results:
            grouped_results[container_name] = []
        grouped_results[container_name].append(result)
    
    logger.info(f"Total results found: {len(all_results)}")
    if all_results:
        logger.debug(f"Results: {grouped_results}")
    
    return {
        "search_id": search_id,
        "time_ranges": time_ranges,
        "results": grouped_results,
        "total_results": len(all_results)
    }

@app.post("/chat")
async def chat_with_logs(request: ChatQueryRequest):
    try:
        logsearch_client = LogSearchClient(
            mcp_server_url=MCP_SERVER_URL,
            openai_api_key=OPENAI_API_KEY
        )
        response = logsearch_client.chat_with_logs(request.query)
        return {"response": response}
    except Exception as e:
        return {"error": str(e)}

# Mount the MCP server
mcp.mount()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 