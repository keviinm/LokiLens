# LokiLens Microservices Architecture

LokiLens is now split into two microservices:

- **Server**: FastAPI backend for log search, S3 access, and web UI.
- **Client**: FastAPI (or CLI) client for AI-driven log search/chat, communicating with the server via API.

## Directory Structure

```
/server   # Backend API, S3, log processing, web UI
/client   # AI/LLM client, chat API
```

## Running with Docker Compose

1. Copy your `.env` file to the project root with AWS and OpenAI credentials.
2. Build and start both services:

```bash
docker-compose up --build
```

- Server: http://localhost:8000
- Client: http://localhost:8001

## Development

- To run the server only:
  ```bash
  cd server
  uvicorn app:app --reload --host 0.0.0.0 --port 8000
  ```
- To run the client only:
  ```bash
  cd client
  uvicorn mcp_client_api:app --reload --host 0.0.0.0 --port 8001
  ```

## Environment Variables
- `OPENAI_API_KEY`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_BUCKET_NAME` (server)
- `OPENAI_API_KEY`, `MCP_SERVER_URL` (client)

## Notes
- The client microservice communicates with the server via the internal Docker network using the service name `server`.
- You can scale, deploy, or test each service independently.