# Backend environment variables
# Copy this file content to backend/.env.backend and fill in the values

# LLM API
QWEN_API_KEY=
QWEN_API_BASE=https://routerai.ru/api/v1
QWEN_MODEL=qwen/qwen3-vl-32b-instruct
DEEPSEEK_API_KEY=
DEEPSEEK_API_BASE=https://routerai.ru/api/v1
DEEPSEEK_MODEL=deepseek/deepseek-v4-flash
DEEPSEEK_QUERYGEN_MODEL=deepseek/deepseek-v4-flash

# Tavily search
TAVILY_API_KEY=

# Database
DBUSER=postgres
DBPASSWORD=
DBHOST=database
DBPORT=5432
DBNAME=ai_agent

# App
RESET_DB=False
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=
ACCESS_TOKEN_EXPIRE_MINUTES=60

# CORS: comma-separated list of allowed origins (e.g. https://yourdomain.com)
CORS_ORIGINS=http://localhost:3000

# Initial admin user (created on first startup if not exists)
ADMIN_LOGIN=
ADMIN_PASSWORD=

# SMTP (for password reset OTP emails)
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_SENDER=
