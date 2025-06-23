from fastapi import FastAPI
from pydantic import BaseModel
from mcp_client import LogSearchClient
import os

app = FastAPI()

# Use environment variable for MCP server URL, fallback to deployed server
MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "https://lokilens-1.onrender.com/mcp")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = LogSearchClient(
    mcp_server_url=MCP_SERVER_URL,
    openai_api_key=OPENAI_API_KEY
)

class QueryRequest(BaseModel):
    query: str

@app.post("/chat")
async def chat_with_logs(request: QueryRequest):
    try:
        response = client.chat_with_logs(request.query)
        return {"response": response}
    except Exception as e:
        return {"error": str(e)} 