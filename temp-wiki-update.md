# Hytale RAG Database

LLM-agnostic semantic search for Hytale code and game data. Includes indexed methods from both server and client code, plus 23,000+ game data items searchable by natural language.

---

## Option 1: Claude Code Integration (Recommended)

Use hytale-rag as an MCP server in Claude Code for AI-assisted modding. The setup script handles everything automatically.

### Setup

1. Get a free API key at https://www.voyageai.com/

2. Run the setup script:
   ```bash
   cd hytale-rag
   python setup.py
   ```
   The script will:
   - Download and extract the database automatically
   - Prompt for your API key
   - Install dependencies
   - Optionally configure Claude Code integration

3. Restart Claude Code (if you enabled Claude integration)

### Example Queries

Once configured, you can ask Claude things like:

- "Search the Hytale server code for player movement handling"
- "Search the client UI files for inventory layout"
- "Find methods related to inventory management"
- "What items drop from zombies?"
- "How does the farming system work?"

---

## Option 2: Docker

Run the RAG server as a standalone REST API using Docker.

### Setup

1. Get a free API key at https://www.voyageai.com/

2. Run the setup script and decline Claude integration:
   ```bash
   cd hytale-rag
   python setup.py
   ```
   When prompted "Do you want to configure Claude Code integration?", enter `n`.

3. Run the server:

   **Linux/Mac:**
   ```bash
   docker run --env-file .env -p 3000:3000 \
     -v $(pwd)/data/lancedb:/app/data/lancedb:ro \
     ghcr.io/logan-mcduffie/hytale-rag
   ```

   **Windows (PowerShell):**
   ```powershell
   docker run --env-file .env -p 3000:3000 `
     -v "${PWD}/data/lancedb:/app/data/lancedb:ro" `
     ghcr.io/logan-mcduffie/hytale-rag
   ```

The REST API is now available at `http://localhost:3000`.

---

## Option 3: Local Development

Run the server directly with Node.js for development or manual CLI usage.

### Setup

1. Get a free API key at https://www.voyageai.com/

2. Run the setup script and decline Claude integration:
   ```bash
   cd hytale-rag
   python setup.py
   ```
   When prompted "Do you want to configure Claude Code integration?", enter `n`.

3. Start the server:
   ```bash
   npm start
   ```

### CLI Search

You can also search directly from the command line:

```bash
npx tsx src/search.ts "player movement handling"
npx tsx src/search.ts "inventory management" --limit 10
npx tsx src/search.ts "how to craft iron sword" --type recipe
npx tsx src/search.ts --stats
```

---

## Server Modes

Set the `HYTALE_RAG_MODE` environment variable to choose which server(s) to run:

| Mode | Description |
|------|-------------|
| `mcp` | MCP server for Claude Code (default when running via stdio) |
| `rest` | REST API on port 3000 (default for Docker) |
| `openai` | OpenAI-compatible function calling on port 3001 |
| `all` | All servers simultaneously |

---

## REST API Usage

### Search Server Code

```bash
curl -X POST http://localhost:3000/v1/search/code \
  -H "Content-Type: application/json" \
  -d '{"query": "player inventory management"}'
```

### Search Client UI Files

```bash
curl -X POST http://localhost:3000/v1/search/client-code \
  -H "Content-Type: application/json" \
  -d '{"query": "inventory hotbar layout"}'
```

### Search Game Data

```bash
curl -X POST http://localhost:3000/v1/search/gamedata \
  -H "Content-Type: application/json" \
  -d '{"query": "zombie drops"}'
```

---

## Database Structure

After setup, your folder structure should look like:

```
hytale-rag/
├── data/
│   └── lancedb/
│       ├── hytale_client_ui.lance/
│       ├── hytale_gamedata.lance/
│       └── hytale_methods.lance/
├── src/
├── package.json
└── setup.py
```

> **Note:** If you see `.lance` folders inside `lancedb/`, you've extracted it correctly. If you only see another `lancedb/` folder inside, you may have extracted one level too deep.
