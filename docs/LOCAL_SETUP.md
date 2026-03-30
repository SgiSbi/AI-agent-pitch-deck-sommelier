# Локальный запуск

## Требования

- Python 3.12+
- Node.js 18+
- PostgreSQL 15+ (локально или через Docker)
- Git

## 1. Клонирование репозитория

```bash
git clone <repo-url>
cd Ai-agent
```

## 2. База данных

Запустите PostgreSQL и создайте базу данных:

```sql
CREATE DATABASE ai_agent;
```

Или поднимите только контейнер с БД:

```bash
docker compose up -d database
```

## 3. Backend

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

Создайте файл `backend/.env.backend` по образцу `backend/env_example.md`:

```env
QWEN_API_KEY=<ключ>
QWEN_API_BASE=https://routerai.ru/api/v1
QWEN_MODEL=qwen/qwen3-vl-32b-instruct

DEEPSEEK_API_KEY=<ключ>
DEEPSEEK_API_BASE=https://routerai.ru/api/v1
DEEPSEEK_MODEL=deepseek/deepseek-r1-0528
DEEPSEEK_QUERYGEN_MODEL=deepseek/deepseek-v3.2

TAVILY_API_KEY=<ключ>

DBUSER=postgres
DBPASSWORD=postgres
DBHOST=localhost
DBPORT=5432
DBNAME=ai_agent
RESET_DB=False

SECRET_KEY=<случайная-строка-минимум-32-символа>
ACCESS_TOKEN_EXPIRE_MINUTES=60

CORS_ORIGINS=http://localhost:3000

# Опционально: автосоздание администратора при старте
ADMIN_LOGIN=admin
ADMIN_PASSWORD=<пароль>
```

Запуск:

```bash
# из директории backend/
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

Swagger UI: `http://localhost:8000/docs`

## 4. Frontend

```bash
cd frontend
npm install
```

Создайте файл `frontend/.env.frontend` по образцу `frontend/env_example.md`:

```env
BACKEND_URL=http://localhost:8000
PUBLIC_BACKEND_URL=http://localhost:8000
PORT=3000
BACKEND_TIMEOUT=600000
```

Запуск:

```bash
node app.js
```

Фронтенд доступен по адресу: `http://localhost:3000`

## 5. Первый администратор

Если `ADMIN_LOGIN` и `ADMIN_PASSWORD` заданы в `.env.backend`, администратор создаётся автоматически при первом старте бекенда.

Альтернативно — через SQL:

```sql
UPDATE users SET role = 'admin', is_whitelisted = true WHERE login = 'yourlogin';
```

## 6. Переменные окружения — описание

### backend/.env.backend

| Переменная | Описание |
|---|---|
| `QWEN_API_KEY` | API-ключ для Qwen (RouterAI) |
| `QWEN_API_BASE` | Базовый URL RouterAI |
| `QWEN_MODEL` | Название vision-модели |
| `DEEPSEEK_API_KEY` | API-ключ для DeepSeek (RouterAI) |
| `DEEPSEEK_API_BASE` | Базовый URL RouterAI |
| `DEEPSEEK_MODEL` | Основная reasoning-модель |
| `DEEPSEEK_QUERYGEN_MODEL` | Модель для генерации Tavily-запросов |
| `TAVILY_API_KEY` | API-ключ Tavily Web Search |
| `DBUSER` | Пользователь PostgreSQL |
| `DBPASSWORD` | Пароль PostgreSQL |
| `DBHOST` | Хост PostgreSQL |
| `DBPORT` | Порт PostgreSQL (по умолчанию 5432) |
| `DBNAME` | Имя базы данных |
| `RESET_DB` | `True` — пересоздать таблицы при старте |
| `SECRET_KEY` | Секрет для подписи JWT-токенов |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Время жизни токена в минутах |
| `CORS_ORIGINS` | Разрешённые origins через запятую |
| `ADMIN_LOGIN` | Логин первого администратора |
| `ADMIN_PASSWORD` | Пароль первого администратора |

### frontend/.env.frontend

| Переменная | Описание |
|---|---|
| `BACKEND_URL` | Внутренний адрес бекенда (для Node.js-сервера) |
| `PUBLIC_BACKEND_URL` | Публичный адрес бекенда (для браузера) |
| `PORT` | Порт Node.js-сервера (по умолчанию 3000) |
| `BACKEND_TIMEOUT` | Таймаут запросов к бекенду в мс (по умолчанию 600000) |
