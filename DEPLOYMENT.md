# M-Autofill Deployment Guide

This guide covers deploying the M-Autofill API service using Docker.

## Prerequisites

- Docker & Docker Compose installed
- OpenRouter or OpenAI API key
- Basic understanding of environment variables

## Quick Start (Docker Compose)

This is the **recommended** deployment method.

### 1. Clone and Configure

```bash
git clone https://github.com/pxl-be/expat-geant.git
cd expat-geant

# Copy environment template
cp .env.example .env
```

### 2. Edit Configuration

Open `.env` and set **required** values:

```bash
# Required: Add your API key (choose one or both)
OPENROUTER_API_KEY=sk-or-v1-xxxxx  # Get from https://openrouter.ai/keys
# OR
OPENAI_API_KEY=sk-xxxxx            # Get from https://platform.openai.com

# Required: Change JWT secret (use a secure random string)
JWT_SECRET=your-secure-random-secret-here-min-32-chars

# Optional: Choose LLM model
LLM_MODEL=anthropic/claude-haiku-4.5
```

**💡 Tip:** Generate a secure JWT secret:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Start the Service

```bash
# Build and start
docker-compose up --build

# Or run in background (detached mode)
docker-compose up -d --build
```

### 4. Verify Deployment

```bash
# Health check
curl http://localhost:8001/health
# Expected: {"status":"healthy"}

# Privacy statement (public endpoint)
curl http://localhost:8001/privacy

# API documentation
open http://localhost:8001/docs
```

### 5. Monitor Logs

```bash
# View logs (follow mode)
docker-compose logs -f m-autofill

# Check recent logs
docker-compose logs --tail=50 m-autofill
```

### 6. Stop the Service

```bash
# Stop containers (data persists)
docker-compose down

# Stop and remove volumes (deletes all data)
docker-compose down -v
```

## Manual Docker Deployment

If you prefer not to use Docker Compose:

### Build the Image

```bash
docker build -t m-autofill:latest .
```

### Run the Container

```bash
docker run -d \
  --name m-autofill \
  -p 8001:8001 \
  -e JWT_SECRET="your-secure-secret-here" \
  -e OPENROUTER_API_KEY="sk-or-v1-xxxxx" \
  -e SESSION_TTL_HOURS=24 \
  -e MAX_FILE_SIZE_MB=50 \
  -v sessions_data:/app/data/sessions \
  -v chroma_data:/app/data/chroma \
  --restart unless-stopped \
  m-autofill:latest
```

### Container Management

```bash
# View logs
docker logs -f m-autofill

# Stop container
docker stop m-autofill

# Start stopped container
docker start m-autofill

# Remove container
docker rm -f m-autofill
```

## Local Development (Without Docker)

For development without Docker:

### Setup

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip3 install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

### Run

```bash
# Start API server
python3 run_api.py

# API available at http://localhost:8001
# Docs at http://localhost:8001/docs
```

## Environment Variables Reference

### Required

| Variable             | Description                  | Example                |
| -------------------- | ---------------------------- | ---------------------- |
| `OPENROUTER_API_KEY` | OpenRouter API key           | `sk-or-v1-xxxxx`       |
| `OPENAI_API_KEY`     | OpenAI API key (alternative) | `sk-xxxxx`             |
| `JWT_SECRET`         | Secret for JWT signing       | 32+ char random string |

### Optional

| Variable               | Default                      | Description                |
| ---------------------- | ---------------------------- | -------------------------- |
| `LLM_MODEL`            | `anthropic/claude-haiku-4.5` | LLM model to use           |
| `SESSION_TTL_HOURS`    | `24`                         | Session lifetime (hours)   |
| `MAX_FILE_SIZE_MB`     | `50`                         | Upload limit (MB)          |
| `AUDIT_RETENTION_DAYS` | `365`                        | Audit log retention (days) |
| `PORT`                 | `8001`                       | API server port            |
| `LOG_LEVEL`            | `INFO`                       | Logging level              |

## Testing Your Deployment

### 1. Health Check

```bash
curl http://localhost:8001/health
```

Expected: `{"status":"healthy"}`

### 2. Public Endpoints

```bash
# Privacy statement (no auth required)
curl http://localhost:8001/privacy

# API documentation (no auth required)
curl http://localhost:8001/docs
```

### 3. Authenticated Endpoints

First, generate a JWT token (for testing):

```python
# test_token.py
import jwt
from datetime import datetime, timedelta, timezone

secret = "your-jwt-secret-from-env"
payload = {
    "user_id": "test_user",
    "session_id": "test_session",
    "org": "test_org",
    "roles": ["respondent"],
    "iat": datetime.now(timezone.utc),
    "exp": datetime.now(timezone.utc) + timedelta(hours=24)
}
token = jwt.encode(payload, secret, algorithm="HS256")
print(token)
```

Then test authenticated endpoints:

```bash
TOKEN="your-generated-token-here"

# Get session stats
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8001/session/stats
```

### 4. Full Workflow Test

See [tests/test_session_api.py](tests/test_session_api.py) for comprehensive integration tests.

Run tests:

```bash
source .venv/bin/activate
python3 -m pytest tests/test_session_api.py -v
```

## Troubleshooting

### Container won't start

**Check logs:**

```bash
docker logs m-autofill
```

**Common issues:**

- Missing API key → Check `.env` file has `OPENROUTER_API_KEY` or `OPENAI_API_KEY`
- Port conflict → Change port in docker-compose.yml or stop conflicting service
- Invalid JWT secret → Ensure `JWT_SECRET` is set and at least 32 characters

### "No LLM API key found" warning

The service will start but suggestion endpoints won't work without an API key.

**Fix:** Add to `.env`:

```bash
OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

Then restart:

```bash
docker-compose restart
```

### Permission denied on volumes

**Linux users may need:**

```bash
sudo chown -R $(whoami):$(whoami) .
```

### Can't connect to Docker daemon

**macOS:** Start Docker Desktop application

**Linux:**

```bash
sudo systemctl start docker
```

## Data Persistence

Docker volumes persist data across container restarts:

- `sessions_data` - Session files and audit logs
- `chroma_data` - Vector database (document embeddings)

**Backup volumes:**

```bash
docker run --rm \
  -v sessions_data:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/sessions-backup.tar.gz /data
```

**Restore volumes:**

```bash
docker run --rm \
  -v sessions_data:/data \
  -v $(pwd):/backup \
  alpine tar xzf /backup/sessions-backup.tar.gz -C /
```

## Security Considerations

### Production Deployment

1. **Change JWT secret** - Use strong random string (32+ chars)
2. **Enable HTTPS** - Use reverse proxy (nginx, Caddy, Traefik)
3. **Firewall rules** - Restrict access to API port
4. **Update regularly** - Keep dependencies and base images updated
5. **Monitor logs** - Set up log aggregation and alerting
6. **Backup data** - Regular backups of Docker volumes
7. **Network isolation** - Use Docker networks for multi-service deployments

### Example Nginx Reverse Proxy

```nginx
server {
    listen 443 ssl;
    server_name api.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Support

- Documentation: [README.md](README.md)
- Project specs: [openspec/project.md](openspec/project.md)
- Issues: [GitHub Issues](https://github.com/pxl-be/expat-geant/issues)
