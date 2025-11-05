# FastMCP - MCP Aggregator

A powerful **Model Context Protocol (MCP) aggregator** that unifies multiple MCP servers into a single, manageable interface with a web-based UI and authentication.

## What is FastMCP?

FastMCP is a centralized hub that:

1. **Aggregates Multiple MCP Servers** - Connect and manage multiple MCP servers (HTTP-based, Stdio-based, and background services) from a single point
2. **Discovers Tools Dynamically** - Automatically discovers and exposes all tools from connected upstream MCP servers
3. **Provides a Unified Interface** - Presents all tools through a single MCP server endpoint, making it easy for clients to access tools from multiple sources
4. **Includes Web Management UI** - Manage servers, view tool counts, and monitor service status through an intuitive web dashboard
5. **Handles Authentication** - Supports both API token authentication for the MCP endpoint and password-protected web UI access
6. **Manages Service Lifecycle** - Automatically starts, monitors, and manages background MCP services (like Serena)

## Key Features

### 🔌 Multi-Protocol Support

- **HTTP Servers** - Connect to HTTP-based MCP servers with optional Bearer token authentication
- **Stdio Servers** - Integrate Node.js, Python, and other command-line MCP servers
- **Service Servers** - Automatically start and manage background services (e.g., Serena MCP server on port 9121)

### 🛡️ Security

- **API Token Authentication** - Secure the `/mcp` endpoint with Bearer token authentication
- **Session-Based UI Access** - Password-protected web interface with session management
- **Environment Variable Support** - Reference sensitive tokens via environment variables (e.g., `$MY_TOKEN_ENV_VAR`)

### 🎛️ Web Dashboard

- View all connected servers (HTTP, Stdio, Service)
- Monitor service status (Running, Crashed, Not Started)
- See tool counts for each server
- Add/remove servers dynamically
- Real-time server list updates

### 🔄 Dynamic Tool Discovery

- Automatically discovers tools from all upstream servers
- Exposes tools with prefixed names (e.g., `serena_find_symbol`, `context7_search`)
- Handles different result types (strings, objects, structured data)
- Graceful error handling for non-JSON-serializable objects

### 🚀 Background Service Management

- Automatically starts service servers in background threads
- Health checks to ensure services are ready before use
- Graceful shutdown and cleanup on exit
- Process monitoring and crash detection

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│           FastMCP (MCP Aggregator)                      │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Web UI (Port 3050)                              │  │
│  │  - Server Management                             │  │
│  │  - Authentication                                │  │
│  │  - Real-time Updates                             │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  MCP Server (Stdio/HTTP)                         │  │
│  │  - Tool Discovery & Routing                      │  │
│  │  - Authentication Middleware                     │  │
│  │  - Upstream Tool Wrapping                        │  │
│  └──────────────────────────────────────────────────┘  │
│                                                         │
│  ┌──────────────────────────────────────────────────┐  │
│  │  Upstream Manager                                │  │
│  │  - HTTP Servers (gofastmcp)                      │  │
│  │  - Stdio Servers (context7, filesystem)          │  │
│  │  - Service Servers (Serena)                      │  │
│  └──────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
    ┌─────────┐          ┌─────────┐         ┌─────────┐
    │ HTTP    │          │ Stdio   │         │Service  │
    │ Servers │          │Servers  │         │Servers  │
    └─────────┘          └─────────┘         └─────────┘
```

## Getting Started

### Prerequisites

- Python 3.11+
- `uv` package manager
- Environment variables configured (see below)

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd fastmcp

# Install dependencies
uv sync

# Create .env file
cp .env.example .env
```

### Configuration

Create a `.env` file in the project root:

```env
# API token for /mcp endpoint (optional)
MCP_API_TOKEN=your-secret-token-here

# Password for web UI (default: admin)
UI_PASSWORD=your-secure-password

# Optional: Reference environment variables in server configs
MY_API_KEY=secret-key-value
```

### Running FastMCP

```bash
# Start the aggregator
uv run main.py

# The web UI will be available at http://localhost:3050
# The MCP server will be available via stdio or HTTP
```

## Usage

### Web Dashboard

1. Navigate to `http://localhost:3050`
2. Login with your configured password
3. View connected servers and their tools
4. Add new servers using the forms
5. Monitor service status in real-time

### Adding Servers

#### HTTP Server
```
Name: my-http-server
URL: https://example.com/mcp
Bearer Token: $MY_API_KEY (or literal token)
```

#### Stdio Server
```
Name: my-stdio-server
Command: npx
Args: -y,@my-org/my-mcp-server
```

#### Service Server
```
Name: my-service
Command: uvx
Args: --from,git+https://github.com/org/repo,start-server
Port: 9121
```

### Using with MCP Clients

FastMCP exposes all discovered tools through a single MCP server interface. Tools are prefixed with their server name:

- `serena_find_symbol` - From Serena server
- `context7_search` - From Context7 server
- `gofastmcp_*` - From GoFastMCP server

Configure your MCP client to connect to FastMCP's stdio or HTTP endpoint.

### Exposing FastMCP with ngrok

To expose FastMCP's web UI and MCP endpoint to the internet securely, use ngrok:

```bash
# Install ngrok (if not already installed)
# https://ngrok.com/download

# Expose port 3050 with ngrok
ngrok http 3050

# You'll get a public URL like: https://abc123.ngrok.io
# Use this URL to access FastMCP from anywhere
```

**Security with ngrok:**

1. **API Token Protection** - All MCP endpoint requests (`/mcp`) are protected by the `MCP_API_TOKEN` from your `.env` file
2. **Web UI Password** - The dashboard (`/ui`) requires the `UI_PASSWORD` from your `.env` file
3. **Session Tokens** - Web UI sessions are managed with secure session cookies

**Example with authentication:**

```bash
# Access the web UI through ngrok
# https://abc123.ngrok.io/ui
# Login with your UI_PASSWORD

# Access the MCP endpoint with token
curl -H "Authorization: Bearer your-mcp-api-token" https://abc123.ngrok.io/mcp
```

**Best Practices:**

- Always set strong values for `MCP_API_TOKEN` and `UI_PASSWORD` in `.env`
- Use environment variables for sensitive tokens (e.g., `$MY_SECRET_TOKEN`)
- Rotate tokens regularly
- Monitor ngrok logs for unauthorized access attempts
- Consider using ngrok's authentication features for additional security

### Adding FastMCP to Simtheory

You can integrate FastMCP as a custom MCP in Simtheory to access all aggregated tools directly from the AI interface.

#### Step 1: Start FastMCP

First, ensure FastMCP is running:

```bash
cd /path/to/fastmcp
uv run main.py
```

The server will be available at `http://localhost:3050` and the MCP endpoint at `http://localhost:3050/mcp`.

#### Step 2: Expose with ngrok (Optional)

If you want to access FastMCP from a remote Simtheory instance, expose it with ngrok:

```bash
ngrok http 3050
# Note the URL: https://abc123.ngrok.io
```

#### Step 3: Add to Simtheory

In Simtheory, go to **Settings** → **Custom MCPs** and click **Add custom MCP**:

**Configuration:**

- **MCP Name:** `MCP Aggregator`
- **Description:** `Aggregates upstream MCP servers and allows access via a single unified interface`
- **MCP URL:**
  - Remote (ngrok): `https://abc123.ngrok.io/mcp`
- **Authentication:** `Bearer token`
- **Bearer Token:** Your `MCP_API_TOKEN` from `.env`

#### Step 4: Verify Connection

Once added, Simtheory will:
1. Connect to mcp aggregator via the MCP endpoint
2. Discover all available tools from upstream servers
3. Display them with prefixed names (e.g., `serena_find_symbol`, `filesystem_read_file`)
4. Allow you to use all tools directly in conversations

#### Example Usage in Simtheory

```
User: "Activate the fastmcp project and show me the main.py file structure"

Simtheory will:
1. Use serena_activate_project to activate the project
2. Use serena_get_symbols_overview to analyze main.py
3. Display the code structure and available symbols
4. Allow further analysis and modifications
```

#### Troubleshooting Simtheory Integration

**Connection refused:**
- Ensure FastMCP is running: `uv run main.py`
- Check that port 3050 is not blocked by a firewall
- If using ngrok, verify the URL is correct and ngrok is still running

**Authentication failed:**
- Verify the Bearer token matches your `MCP_API_TOKEN` in `.env`
- Check that the token is not empty or None
- Ensure you're using the correct URL (http vs https)

**Tools not appearing:**
- Check that upstream servers are running and healthy
- Verify tool discovery completed successfully (check FastMCP logs)
- Try refreshing the Simtheory connection

**Slow tool discovery:**
- FastMCP discovers tools on startup
- If you added new servers, restart FastMCP
- Check network latency if using ngrok

### Working with Serena Projects

**Serena** is a powerful coding agent toolkit that's integrated as a service in FastMCP. Here's how to use it:

#### Starting a Serena Project

You can ask the agent to activate and work on a Serena project:

```
"Activate the project /path/to/my/project"
"Activate the project my-project-name"
```

The agent will:
1. Activate the project in Serena
2. Discover the project structure
3. Start language servers for supported languages
4. Make all Serena tools available for code analysis and editing

#### File Access Restrictions

**Important Security Note:** Serena can only access files in the directory where the FastMCP server is running.

```bash
# If you start FastMCP from /home/user/projects/fastmcp
cd /home/user/projects/fastmcp
uv run main.py

# Serena can access:
# ✅ /home/user/projects/fastmcp/
# ✅ /home/user/projects/fastmcp/src/
# ✅ /home/user/projects/fastmcp/.serena/

# Serena CANNOT access:
# ❌ /home/user/other-project/
# ❌ /etc/passwd
# ❌ Files outside the working directory
```

This sandboxing ensures that Serena cannot access files outside the project directory, providing an important security boundary.

#### Available Serena Tools

Once a project is activated, you can use tools like:

- `serena_find_symbol` - Find code symbols by name
- `serena_find_referencing_symbols` - Find where a symbol is used
- `serena_get_symbols_overview` - Get an overview of a file's structure
- `serena_read_file` - Read file contents
- `serena_replace_symbol_body` - Replace function/method implementations
- `serena_insert_after_symbol` - Insert code after a symbol
- `serena_search_for_pattern` - Search for patterns in code
- `serena_execute_shell_command` - Run shell commands (within the project directory)
- And many more...

#### Example Workflow

```
1. User: "Activate the project /home/user/my-app"
   → Serena activates the project
   → Language servers start
   → Project structure is analyzed

2. User: "Find all functions that use the database"
   → Serena uses find_symbol and find_referencing_symbols
   → Returns matching code locations

3. User: "Update the login function to add rate limiting"
   → Serena finds the login function
   → Reads the current implementation
   → Modifies the code using replace_symbol_body
   → Runs tests to verify changes

4. User: "Commit these changes"
   → Serena executes git commands
   → Creates a commit with the changes
```

#### Supported Languages in Serena

Serena supports semantic analysis for:
- Python
- TypeScript/JavaScript
- Go
- Rust
- Java
- C/C++
- And many more (see `.serena/project.yml` for full list)

Your FastMCP project is configured for Python and Markdown.

## Project Structure

```
fastmcp/
├── main.py                 # Main application (UpstreamManager, routes, etc.)
├── .serena/
│   └── project.yml        # Serena project configuration
├── .env.example           # Environment variables template
├── README.md              # This file
└── pyproject.toml         # Project dependencies
```

## Core Components

### UpstreamManager

Manages all upstream MCP servers:
- **HTTP Servers** - Connect to remote HTTP-based MCP servers
- **Stdio Servers** - Launch and communicate with command-line MCP servers
- **Service Servers** - Start and manage background MCP services
- **Tool Discovery** - Dynamically discover tools from all servers
- **Tool Routing** - Route tool calls to appropriate upstream servers

### AuthMiddleware

Provides authentication for:
- `/mcp` endpoint - Bearer token authentication
- `/ui` routes - Session-based authentication

### Web Routes

- `GET /login` - Login page
- `POST /login` - Handle login
- `GET /logout` - Logout
- `GET /ui` - Main dashboard
- `GET /api/servers` - List all servers
- `POST /api/servers/http` - Add HTTP server
- `POST /api/servers/stdio` - Add Stdio server
- `POST /api/servers/service` - Add Service server
- `DELETE /api/servers/{name}` - Remove server

## Supported Languages

- Python
- Markdown

## Error Handling

FastMCP includes robust error handling:
- JSON serialization errors are caught and converted to strings
- Service startup failures are logged with detailed error messages
- Tool discovery failures don't prevent other servers from working
- Graceful cleanup on shutdown

## Development

### Debugging

Enable verbose logging by checking the console output when running:

```bash
uv run main.py
```

### Testing

Run the application and use the web UI to:
1. Add test servers
2. Verify tool discovery
3. Test tool execution
4. Monitor service status

## License

[Add your license here]

## Contributing

[Add contribution guidelines here]

## Troubleshooting

### Service won't start
- Check that the port is not already in use
- Verify the command and arguments are correct
- Check environment variables are set properly

### Tools not appearing
- Ensure the upstream server is running
- Check the health check endpoint is responding
- Verify authentication tokens are correct

### JSON serialization errors
- The application now handles non-JSON-serializable objects gracefully
- Check the console logs for detailed error messages

### Serena can't access my project
- Ensure FastMCP is running from the parent directory of your project
- Check that the project path is correct
- Verify the project has a `.serena/project.yml` configuration file

## Future Enhancements

- Tool caching and indexing for faster discovery
- Tool execution history and logging
- Advanced filtering and search in the web UI
- Metrics and analytics dashboard
- Rate limiting and usage quotas
- Multi-user support with role-based access control
