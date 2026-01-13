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

### Quick Testing with Dev Token Endpoint

For development and testing, use the `/dev/token` endpoint to quickly generate valid JWT tokens:

**⚠️ Note**: This endpoint is automatically disabled in production (`ENVIRONMENT=production`).

#### 1. Generate a Development Token

```bash
# Generate token with defaults
curl -X POST http://localhost:8001/dev/token \
  -H "Content-Type: application/json" \
  -d '{}'

# Or with custom parameters
curl -X POST http://localhost:8001/dev/token \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "john_doe",
    "org": "pxl_university",
    "roles": ["respondent"]
  }'
```

**Response:**

```json
{
  "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user_id": "john_doe",
  "expires_in_hours": 24,
  "message": "Token generated successfully. Use in Authorization header: Bearer <token>"
}
```

#### 2. Complete Workflow Example

```bash
# Step 1: Generate token
TOKEN=$(curl -s -X POST http://localhost:8001/dev/token -H "Content-Type: application/json" -d '{"user_id":"test_user"}' | grep -o '"token":"[^"]*' | cut -d'"' -f4)

# Step 2: Upload a document
curl -X POST http://localhost:8001/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@sample_document.pdf"

# Step 3: Get answer suggestion
curl -X POST http://localhost:8001/suggest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is my employment status?",
    "context": "Current situation"
  }'

# Step 4: Check session stats
curl -X GET http://localhost:8001/session/stats \
  -H "Authorization: Bearer $TOKEN"

# Step 5: Get audit report
curl -X GET http://localhost:8001/audit-report \
  -H "Authorization: Bearer $TOKEN"

# Step 6: Delete session (cleanup)
curl -X DELETE http://localhost:8001/session \
  -H "Authorization: Bearer $TOKEN"
```

#### 3. Python Testing Example

```python
import requests

# Generate token
response = requests.post(
    "http://localhost:8001/dev/token",
    json={"user_id": "python_tester"}
)
token = response.json()["token"]

# Use token for authenticated requests
headers = {"Authorization": f"Bearer {token}"}

# Upload document
with open("document.pdf", "rb") as f:
    upload_response = requests.post(
        "http://localhost:8001/upload",
        headers=headers,
        files={"file": f}
    )
print(upload_response.json())

# Get suggestion
suggest_response = requests.post(
    "http://localhost:8001/suggest",
    headers=headers,
    json={"question": "What is my current role?"}
)
print(suggest_response.json())
```

### Health Checks

```bash
# Basic health check
curl http://localhost:8001/health
# Expected: {"status":"healthy"}

# API root
curl http://localhost:8001/
# Expected: {"service":"m-autofill","status":"running"}
```

### Public Endpoints (No Auth Required)

```bash
# Privacy statement
curl http://localhost:8001/privacy

# API documentation (interactive)
open http://localhost:8001/docs
```

### Manual JWT Token Generation (Advanced)

If you need to generate tokens manually (e.g., for institutional integration testing):

```python
# manual_token.py
import jwt
from datetime import datetime, timedelta, timezone

secret = "your-jwt-secret-from-env"
payload = {
    "user_id": "institutional_user",
    "session_id": "sess_12345",
    "org": "institution_name",
    "roles": ["respondent"],
    "iat": datetime.now(timezone.utc),
    "exp": datetime.now(timezone.utc) + timedelta(hours=24)
}
token = jwt.encode(payload, secret, algorithm="HS256")
print(token)
```

### Running Integration Tests

Run the full test suite to verify deployment:

```bash
source .venv/bin/activate
python3 -m pytest tests/ -v

# Specific test suites
python3 -m pytest tests/test_session_api.py -v    # API tests
python3 -m pytest tests/test_dev_token.py -v      # Dev token tests
python3 -m pytest tests/test_auth.py -v           # Auth tests
```

### Institutional Integration

For production deployments with institutional authentication, see:

📖 **[docs/INTEGRATION.md](docs/INTEGRATION.md)** — Complete integration guide with:

- JWT requirements and claim structure
- Shibboleth / Azure AD / OIDC examples
- Troubleshooting common auth issues
- Security best practices

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
