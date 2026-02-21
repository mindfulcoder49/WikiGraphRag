# Wikipedia GraphRAG Builder

A showcase app that builds a knowledge graph from Wikipedia pages and lets you ask grounded questions with citations.

## Demo Topics

- **Ada Lovelace** – rich biography with many linked concepts and people
- **Python (programming language)** – deep technical graph with organizations, events, and works
- **Climate change** – broad topic connecting places, organizations, events, and concepts

---

## Architecture

```
Browser ──▶ React (Vite, TypeScript, Cytoscape.js)
              │  REST + WebSocket
              ▼
          FastAPI (Python 3.11)
              │
    ┌─────────┴─────────┐
    │                   │
 Neo4j              OpenAI API
 (graph DB)         (GPT-5, Responses API)
```

**Data flow:**
1. User submits topic → POST `/api/builds`
2. Backend creates Build node, starts async worker
3. Worker crawls Wikipedia (BFS, bounded by `max_pages` / `max_depth`)
4. Each page → chunked → LLM extraction → entities + claims written to Neo4j
5. Worker pushes events over WebSocket → UI updates graph in real time
6. After "Done!", user asks questions → planner → graph retrieval → grounded answer

---

## Requirements

- Docker + Docker Compose v2
- An OpenAI API key with access to `gpt-5`

---

## Quick Start

```bash
# 1. Clone / enter the repo
cd WikiGraphRag

# 2. Copy and fill in env vars
cp .env.example .env
# Edit .env and set OPENAI_API_KEY

# 3. Start everything
docker compose up --build

# 4. Open the app
open http://localhost:5173
```

Neo4j Browser is available at http://localhost:7474 (user: neo4j, password: pleasechange).

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENAI_API_KEY` | ✅ | — | Your OpenAI API key |
| `NEO4J_URI` | — | `bolt://neo4j:7687` | Neo4j connection URI |
| `NEO4J_USER` | — | `neo4j` | Neo4j username |
| `NEO4J_PASSWORD` | — | `pleasechange` | Neo4j password |
| `WIKIPEDIA_USER_AGENT` | — | `WikiGraphRAG-MVP/0.1` | User-Agent for Wikipedia API |
| `OPENAI_MODEL` | — | `gpt-5` | OpenAI model name |

---

## API Reference

| Method | Path | Description |
|---|---|---|
| POST | `/api/builds` | Start a new build |
| GET | `/api/builds/{id}` | Get build status |
| POST | `/api/builds/{id}/stop` | Cancel a running build |
| GET | `/api/builds/{id}/graph` | Get graph snapshot |
| GET | `/api/builds/{id}/entity/{eid}` | Get entity detail |
| POST | `/api/builds/{id}/ask` | Ask a question |
| WS | `/ws/build/{id}` | Stream build events |

---

## Project Structure

```
repo/
  docker-compose.yml
  README.md
  .env.example
  backend/
    Dockerfile
    pyproject.toml
    src/app/
      main.py          # FastAPI app, all routes
      config.py        # Pydantic settings
      db/              # Neo4j driver + schema
      wiki/            # Wikipedia API client + chunker
      llm/             # OpenAI client, prompts, JSON utils
      build/           # Build service, worker, events
      qa/              # Planner, retriever, answer synthesis
      util/            # ID generation, text utilities
  frontend/
    Dockerfile
    package.json
    src/
      App.tsx          # Router
      pages/           # Home, Build
      components/      # GraphView, BuildLog, ProgressBar, NodeDrawer, Chat
```

---

## Limitations / TODOs

- No persistent reconnect: refreshing mid-build loses the streamed log (graph is restored from API)
- No embedding-based semantic search (uses graph traversal + keyword match)
- Wikipedia rate limit: 0.3s between requests; large builds may take a few minutes
- `gpt-5` must be available on your API key
