# Unified Dockerfile for all AgentCore agent containers
# Uses a build arg to select which agent entrypoint to run.
# Platform: linux/arm64 | Port: 8080
#
# Build (from project root):
#   docker build --platform=linux/arm64 \
#     -f backend/agents/agentcore/Dockerfile \
#     --build-arg AGENT_ENTRYPOINT=competitive_intelligence_runtime \
#     -t competitive-intelligence-agent .
#
# Available AGENT_ENTRYPOINT values:
#   - competitive_intelligence_runtime
#   - demand_forecasting_runtime
#   - market_intelligence_runtime
#   - strategy_synthesis_runtime
#   - implementation_monitoring_runtime

FROM --platform=linux/arm64 python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/* && \
    apt-get clean

# Copy and install Python dependencies
COPY backend/agents/agentcore/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy shared business logic modules
COPY shared/ /app/shared/

# Copy backend agents and MCP servers
COPY backend/ /app/backend/

# Copy pyproject.toml for package metadata (editable install)
COPY pyproject.toml /app/pyproject.toml
RUN pip install --no-cache-dir -e /app

# Build arg to select which agent runtime to run
ARG AGENT_ENTRYPOINT=competitive_intelligence_runtime
ENV AGENT_ENTRYPOINT=${AGENT_ENTRYPOINT}

EXPOSE 8080

# Security: Run as non-root user
RUN adduser --disabled-password --gecos "" agent && \
    chown -R agent:agent /app
USER agent

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

CMD ["sh", "-c", "opentelemetry-instrument python -m uvicorn backend.agents.agentcore.${AGENT_ENTRYPOINT}:app --host 0.0.0.0 --port 8080"]
