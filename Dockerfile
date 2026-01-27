FROM python:3.11-slim

LABEL maintainer="PKI Manager"
LABEL description="PKI Management MCP Server"

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml .
COPY pki_mcp_server/ ./pki_mcp_server/

# Install Python dependencies
RUN pip install --no-cache-dir .

# Create directories for PKI data and backups
RUN mkdir -p /data/pki /data/backups

# Set environment variables
ENV PKI_ROOT_DIR=/data/pki
ENV PKI_BACKUP_DIR=/data/backups
ENV PKI_LOG_FILE=/data/pki-manager.log

# Expose SSE port
EXPOSE 8000

# Run the MCP server with SSE transport
CMD ["python", "-m", "pki_mcp_server", "--transport", "sse", "--host", "0.0.0.0", "--port", "8000"]
