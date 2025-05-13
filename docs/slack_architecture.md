# LokiLens Slack Integration Architecture

## Command Flow

```mermaid
sequenceDiagram
    participant User
    participant Slack
    participant LokiLens
    participant OpenAI
    participant MCP
    participant S3

    User->>Slack: /loki or /lokilens command
    Slack->>LokiLens: Command received
    Note over LokiLens: 1. Acknowledge command
    
    LokiLens->>OpenAI: Parse natural language input
    OpenAI-->>LokiLens: Structured data (ID + time)
    
    LokiLens->>MCP: Search logs request
    MCP->>S3: Query logs
    S3-->>MCP: Log results
    MCP-->>LokiLens: Processed results
    
    LokiLens->>OpenAI: Generate response
    OpenAI-->>LokiLens: Natural language summary
    
    LokiLens->>Slack: Send response
    Slack->>User: Display results
```

## Components

1. **User Input**
   - Natural language commands in Slack
   - Examples:
     - `/loki 12345 happened yesterday at 3pm`
     - `/lokilens 67890 from last week`

2. **LokiLens Slack App**
   - Handles command routing
   - Manages authentication
   - Coordinates between components

3. **OpenAI Integration**
   - Two main functions:
     1. Natural Language Parsing
        - Converts user input to structured data
        - Extracts search ID and time range
     2. Response Generation
        - Creates human-readable summaries
        - Suggests follow-up actions

4. **MCP (Model Context Protocol)**
   - Handles log search logic
   - Manages time range processing
   - Coordinates with S3

5. **S3 Storage**
   - Stores log files
   - Provides log retrieval
   - Handles file access

## Error Handling

```mermaid
graph TD
    A[Command Received] --> B{Valid Input?}
    B -->|Yes| C[Parse Input]
    B -->|No| D[Send Usage Help]
    C --> E{Parse Success?}
    E -->|Yes| F[Search Logs]
    E -->|No| G[Extract ID + Current Time]
    F --> H{Search Success?}
    H -->|Yes| I[Generate Response]
    H -->|No| J[Send Error Message]
    I --> K[Send to Slack]
    J --> K
    G --> F
```

## Data Flow

1. **Input Processing**
   ```
   User Input → OpenAI Parsing → Structured Data
   ```

2. **Log Search**
   ```
   Structured Data → MCP → S3 Query → Log Results
   ```

3. **Response Generation**
   ```
   Log Results → OpenAI Summary → Slack Message
   ```

## Security

- Slack App Token authentication
- AWS S3 credentials
- OpenAI API key
- All sensitive data stored in environment variables 