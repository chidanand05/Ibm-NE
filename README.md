# Namma Exodus 🚦

**Agentic AI-powered crowd-exit prediction and multi-modal transport coordination system for Bengaluru.**

> *"Uber shows where cabs are. Namma Exodus shows where Bengaluru will need them."*

Namma Exodus predicts crowd movement 20–40 minutes before major events end and coordinates
Bengaluru Metro, BMTC buses, auto-rickshaws, traffic police, and event authorities to prepare
a safe, explainable exit plan — subject to human officer approval before any operational action.

---

## Architecture Overview

| Component | Technology |
|---|---|
| **7 Specialized AI Agents** | Python + LiteLLM (IBM Granite / Gemini / Groq) |
| **Multi-Agent Orchestrator** | LangGraph `StateGraph` with interrupt/resume |
| **MCP Tool Layer** | Python MCP SDK v2 — 6 in-process modules + 1 Streamable HTTP server |
| **Crowd Simulator** | Deterministic physics model — H3 spatial indexing (resolution 7) |
| **Decision Engine** | Weighted 4-component scoring — fully explainable |
| **Backend** | Python 3.11 + FastAPI + SQLAlchemy 2.0 (async) |
| **Database** | PostgreSQL 16 + PostGIS 3.4 |
| **Cache / WebSocket** | Redis 7 pub/sub fan-out |
| **Vector Memory** | ChromaDB + sentence-transformers (RAG) |
| **Frontend** | Next.js 14 + TypeScript + Tailwind CSS + MapLibre GL |
| **Observability** | OpenTelemetry + Jaeger |

---

## Prerequisites

| Tool | Version | Install |
|---|---|---|
| Docker Desktop | 24+ | https://docs.docker.com/get-docker/ |
| Docker Compose | V2 (2.20+) | Included with Docker Desktop |

> **No local Python or Node.js required** — everything runs inside Docker containers.

---

## Environment Variable Setup

### Step 1 — Copy the template

```bash
cd namma-exodus
cp .env.example .env
```

### Step 2 — Add API keys (optional but recommended)

Open `.env` in a text editor and fill in:

```bash
# ── IBM watsonx.ai (primary LLM — Strategic Planner + Event Intelligence)
WATSONX_URL=https://us-south.ml.cloud.ibm.com   # change region if needed
WATSONX_APIKEY=your-ibm-cloud-api-key
WATSONX_PROJECT_ID=your-watsonx-project-id

# ── Google Gemini (secondary — Citizen Guidance multilingual)
GEMINI_API_KEY=your-google-ai-studio-key

# ── Groq (fallback — Transport Supply, Police, Learning agents)
GROQ_API_KEY=your-groq-api-key

# ── Security (generate a strong secret)
JWT_SECRET=run-openssl-rand-hex-32-and-paste-here
```

> **Running without API keys:** The system works fully in demo mode without any keys.
> Each agent automatically falls back to deterministic structured responses
> (labeled `llm_fallback: true`). Add at least one key for real LLM reasoning.

| Provider | Free Tier | Get Key |
|---|---|---|
| IBM watsonx.ai | Lite plan available | https://cloud.ibm.com → watsonx.ai |
| Google Gemini | Yes (Gemini 1.5 Flash) | https://aistudio.google.com |
| Groq | Yes (generous limits) | https://console.groq.com |

---

## Docker Startup

### Start all services

```bash
docker compose up --build
```

First build takes ~5–8 minutes (downloading base images and Python/Node packages).
Subsequent starts: ~30 seconds.

### Services started

| Service | URL | Description |
|---|---|---|
| `backend` | http://localhost:8000 | FastAPI REST API + WebSocket |
| `frontend` | http://localhost:3000 | Next.js dashboard |
| `postgres` | localhost:5432 | PostgreSQL + PostGIS |
| `redis` | localhost:6379 | Cache + WebSocket pub/sub |
| `chromadb` | internal (8000) | Vector DB (RAG memory) |
| `crowd-sim-mcp` | internal (8001) | Crowd Simulation MCP server |
| `jaeger` | http://localhost:16686 | Distributed tracing UI |

### Verify the stack is running

```bash
curl http://localhost:8000/health
# Expected: {"status":"ok","service":"namma-exodus-backend",...}
```

Open http://localhost:3000 to see the dashboard.

---

## Database Setup

The backend Dockerfile runs `alembic upgrade head` automatically on startup.
If you need to run migrations manually:

```bash
docker compose exec backend alembic upgrade head
```

---

## Database Seeding

Seed the RCB demo event, Chinnaswamy Stadium venue, agent model configs,
and ChromaDB historical records:

```bash
docker compose exec backend python -m app.seed.run_seed
```

This creates:
- M. Chinnaswamy Stadium venue (UUID: `10000000-0000-0000-0000-000000000001`)
- RCB vs MI IPL 2027 demo event (UUID: `20000000-0000-0000-0000-000000000001`)
- 7 agent model configuration records
- 3 synthetic historical event records in ChromaDB

---

## Running the Namma Exodus Demo Replay

### Via the Frontend (recommended for demos)

1. Open http://localhost:3000/replay
2. Click **"Start Replay"**
3. Watch the 9 phases execute (Event Intelligence → Crowd Forecast → Transport → Police → Planner → **Approval Gate** → Citizen Guidance → Learning)
4. When Phase 6 shows the approval banner, click **"Auto-Approve Demo"** to resume the workflow

### Via the REST API

```bash
# Start the demo orchestrator run
curl -X POST http://localhost:8000/api/v1/replay/start \
  -H "Content-Type: application/json"

# Check status (replace SESSION_ID with the returned session_id)
curl http://localhost:8000/api/v1/replay/status/SESSION_ID

# Auto-approve (for demo)
curl -X POST http://localhost:8000/api/v1/replay/auto-approve/SESSION_ID
```

---

## Running All Tests

Tests run locally (no Docker required) using stubs for DB/Redis:

```bash
cd backend

# Install test dependencies (one-time)
pip install h3 mcp pytest pytest-asyncio

# Run all 357 tests
python -m pytest tests/unit/ -v

# Run specific test suites
python -m pytest tests/unit/test_agents.py -v           # 7 AI agents
python -m pytest tests/unit/test_orchestrator.py -v    # LangGraph
python -m pytest tests/unit/test_simulator.py -v       # Crowd simulator
python -m pytest tests/unit/test_mcp_servers.py -v     # MCP tools
python -m pytest tests/unit/test_decision_engine.py -v # Decision engine
```

### TypeScript validation

```bash
cd frontend
npm install
npx tsc --noEmit
```

---

## Project Structure

```
namma-exodus/
├── backend/
│   ├── app/
│   │   ├── agents/               # 7 specialized AI agents
│   │   │   ├── base.py           # BaseAgent — LiteLLM + MCP + DB tracking
│   │   │   ├── event_intelligence.py
│   │   │   ├── egress_forecast.py
│   │   │   ├── supply.py
│   │   │   ├── police_coordination.py
│   │   │   ├── planner.py        # Central reasoning + approval trigger
│   │   │   ├── citizen_guidance.py  # EN / KN / HI multilingual
│   │   │   └── learning.py       # ChromaDB outcome storage
│   │   ├── orchestrator/
│   │   │   ├── state.py          # ExodusState TypedDict
│   │   │   ├── graph.py          # LangGraph StateGraph
│   │   │   └── runner.py         # Session lifecycle manager
│   │   ├── mcp_servers/          # In-process MCP tool modules
│   │   │   ├── h3_server.py      # H3 geospatial tools
│   │   │   ├── transit_server.py # Metro/BMTC tools
│   │   │   ├── supply_server.py  # Transport supply gap tools
│   │   │   ├── event_server.py   # Event lookup tools
│   │   │   ├── history_server.py # ChromaDB RAG
│   │   │   └── crowd_sim_client.py # MCP HTTP client → crowd-sim-mcp
│   │   ├── llm_gateway/          # LiteLLM multi-provider gateway
│   │   ├── simulator/            # Deterministic crowd/transport/traffic
│   │   ├── services/
│   │   │   ├── decision_engine.py # Weighted scoring engine
│   │   │   ├── ws_manager.py     # WebSocket connection registry
│   │   │   └── ws_broadcaster.py # Redis pub/sub fan-out
│   │   ├── models/db/            # 15 SQLAlchemy ORM models
│   │   ├── api/v1/               # FastAPI route handlers
│   │   ├── seed/                 # Demo data seeding
│   │   ├── security/             # JWT + RBAC
│   │   └── observability/        # OpenTelemetry + structlog
│   ├── migrations/               # Alembic database migrations
│   ├── tests/unit/               # 357 unit tests
│   ├── Dockerfile
│   ├── pyproject.toml
│   └── alembic.ini
├── frontend/
│   ├── src/
│   │   ├── app/                  # Next.js 14 App Router pages
│   │   │   ├── dashboard/        # Command Centre
│   │   │   ├── map/              # H3 Crowd Intelligence Map
│   │   │   ├── agents/           # Agent Execution Monitor
│   │   │   ├── approvals/        # Human Approval Centre
│   │   │   ├── guidance/         # Multilingual Citizen Guidance
│   │   │   ├── llm/              # LLM Gateway Monitor
│   │   │   ├── observability/    # System Observability
│   │   │   └── replay/           # Demo Replay Controller
│   │   ├── components/
│   │   │   ├── map/              # BaseMap, H3Layer, DemandLegend
│   │   │   └── shared/           # GlassCard, AgentTimeline, etc.
│   │   └── lib/                  # api.ts, ws.ts, store.ts, constants.ts
│   ├── Dockerfile
│   ├── package.json
│   └── next.config.ts
├── mcp_servers/
│   └── crowd_sim_mcp/            # Standalone Streamable HTTP MCP server
│       ├── server.py             # MCPServer v2 with 3 tools
│       ├── crowd_logic.py        # Self-contained simulation logic
│       ├── requirements.txt
│       └── Dockerfile
├── docs/                         # Architecture documentation
│   ├── architecture.md
│   ├── implementation-plan.md
│   ├── database-schema.md
│   ├── agent-contracts.md
│   ├── api-contracts.md
│   └── acceptance-tests.md
├── docker-compose.yml            # Full development stack
├── docker-compose.prod.yml       # Production overrides
├── .env.example                  # Environment variable template
└── README.md
```

---

## Stopping and Cleanup

```bash
# Stop all services (data volumes preserved)
docker compose down

# Stop and delete all data (full reset)
docker compose down -v

# Rebuild after code changes
docker compose up --build
```

---

## Development Tips

```bash
# Live backend logs
docker compose logs -f backend

# Live frontend logs
docker compose logs -f frontend

# Access PostgreSQL directly
docker compose exec postgres psql -U namma -d namma_exodus

# Access Redis CLI
docker compose exec redis redis-cli

# Re-run database migrations
docker compose exec backend alembic upgrade head

# Re-run seed data
docker compose exec backend python -m app.seed.run_seed
```

---

## Important: Simulated Data Disclaimer

All crowd predictions, transport data, and response plans are **synthetically simulated**
for demonstration purposes. Every output carries `data_source: "SIMULATED"`.

**No agent can autonomously:**
- Issue official public instructions
- Dispatch vehicles or change transport operations
- Order evacuations or crowd-control actions

Every operational action plan requires explicit approval from an authorized human officer.

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `docker compose up` fails on M1/M2 Mac | Add `platform: linux/amd64` to problematic services in docker-compose.yml |
| Port 5432 already in use | Stop local PostgreSQL: `brew services stop postgresql` |
| Port 3000 already in use | Change frontend port in docker-compose.yml: `"3001:3000"` |
| ChromaDB model download slow | First run downloads ~80MB sentence-transformer model; subsequent runs use cache |
| Agents return `llm_fallback: true` | No API keys configured — add at least `GROQ_API_KEY` in `.env` |
| Backend crashes on startup | Check `docker compose logs backend` — usually a missing env var or DB connection issue |
| Frontend shows "No simulation data" | Run seed: `docker compose exec backend python -m app.seed.run_seed` |

---

## License

Built for academic demonstration. All crowd data, event data, and transport data are synthetic.
