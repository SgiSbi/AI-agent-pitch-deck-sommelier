# AI-ассистент для анализа стартап-презентаций

Система автоматизированного анализа pitch-deck презентаций. Принимает PDF, анализирует через мультимодальные LLM и веб-поиск, возвращает структурированный инвестиционный отчёт в формате DOCX.

## Быстрый старт

- [Локальный запуск](docs/LOCAL_SETUP.md)
- [Запуск через Docker](docs/DOCKER_SETUP.md)
- [API Reference](docs/API_REFERENCE.md)
- [Остальное](docs/TECHNICAL_DOCUMENTATION.md)

---

## Развёртывание

### Требования

- Docker 24+ и Docker Compose v2+  
  _или_ Python 3.12 и PostgreSQL 17

### Шаг 1 — Клонировать репозиторий

```bash
git clone <repo-url>
cd Ai-agent
```

### Шаг 2 — Создать файл переменных окружения

Создайте `backend/.env.backend`:

```env
# RouterAI — Qwen (vision)
QWEN_API_KEY=<ключ от routerai.ru>
QWEN_API_BASE=https://routerai.ru/api/v1
QWEN_MODEL=qwen/qwen3-vl-32b-instruct

# RouterAI — DeepSeek (reasoning)
DEEPSEEK_API_KEY=<ключ от routerai.ru>
DEEPSEEK_API_BASE=https://routerai.ru/api/v1
DEEPSEEK_MODEL=deepseek/deepseek-r1-0528
DEEPSEEK_QUERYGEN_MODEL=deepseek/deepseek-v3.2

# Tavily Web Search
TAVILY_API_KEY=<ключ от tavily.com>

# PostgreSQL
DBUSER=postgres
DBPASSWORD=postgres
DBHOST=database        # для Docker; для локального запуска — localhost
DBPORT=5432
DBNAME=ai_agent
RESET_DB=False

# JWT
SECRET_KEY=<случайная строка, минимум 32 символа>
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

Получить ключи:
- RouterAI: [routerai.ru](https://routerai.ru)
- Tavily: [tavily.com](https://tavily.com)

### Шаг 3 — Запустить

**Docker (рекомендуется):**

```bash
docker-compose up -d --build
```

**Локально:**

```bash
# Backend
cd backend
python -m venv .venv && .venv\Scripts\activate   # Windows
# python -m venv .venv && source .venv/bin/activate  # Linux/macOS
pip install -r requirements.txt
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### Шаг 4 — Создать администратора

```bash
# 1. Зарегистрировать пользователя
curl -X POST http://localhost:8000/users/register \
  -H "Content-Type: application/json" \
  -d '{"login": "admin", "password": "yourpassword"}'

# 2. Назначить роль admin (Docker)
docker-compose exec database psql -U postgres -d ai_agent \
  -c "UPDATE users SET role = 'admin' WHERE login = 'admin';"

# 2. Назначить роль admin (локально, через psql)
psql -U postgres -d ai_agent \
  -c "UPDATE users SET role = 'admin' WHERE login = 'admin';"
```

### Шаг 5 — Добавить пользователей в вайтлист

Только пользователи из вайтлиста (или администраторы) могут запускать анализ.

```bash
# 1. Получить токен администратора
curl -X POST http://localhost:8000/users/login \
  -H "Content-Type: application/json" \
  -d '{"login": "admin", "password": "yourpassword"}'

# 2. Добавить пользователя в вайтлист (используя полученный токен)
curl -X PATCH http://localhost:8000/admin/users/<user_id>/whitelist \
  -H "Authorization: Bearer <admin_token>"
```

### Шаг 6 — Проверить работу

Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)

```bash
# Авторизоваться и запустить анализ
curl -X POST http://localhost:8000/pipeline/process-pdf \
  -H "Authorization: Bearer <token>" \
  -F "file=@presentation.pdf" \
  -o report.docx
```

---

## Стек

| Компонент | Технология |
|---|---|
| API | FastAPI + Uvicorn |
| БД | PostgreSQL 17 + SQLAlchemy (async) |
| Vision LLM | Qwen VL 32B (RouterAI) |
| Reasoning LLM | DeepSeek R1 (RouterAI) |
| Веб-поиск | Tavily |
| Авторизация | JWT (bcrypt + python-jose) |
| Контейнеризация | Docker + Docker Compose |
