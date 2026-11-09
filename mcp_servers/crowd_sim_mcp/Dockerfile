FROM python:3.11-slim

# ── Crowd Simulation MCP Server ───────────────────────────────────────────────
# Standalone Streamable HTTP MCP server.
# Exposed internally at port 8001 (no host port mapping — internal Docker only).
# Backend accesses it at http://crowd-sim-mcp:8001/mcp

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY crowd_logic.py .
COPY server.py .
COPY __init__.py .

# Health check: verify the MCP endpoint responds
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/mcp', timeout=5)" || exit 1

# Run on 0.0.0.0 so it's accessible from other Docker containers
ENV MCP_HOST=0.0.0.0
ENV MCP_PORT=8001

CMD ["python3", "server.py"]
