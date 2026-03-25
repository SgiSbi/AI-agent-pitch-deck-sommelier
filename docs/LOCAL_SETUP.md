# Локальный запуск

## Требования

- Python 3.12+
- PostgreSQL 15+ (запущенный локально или через Docker)
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
docker-compose up -d database
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
```

Запуск:

```bash
# из директории backend/
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

Swagger UI доступен по адресу: `http://localhost:8000/docs`

## 4. Первый администратор

После первого запуска зарегистрируйте пользователя через API и назначьте ему роль admin напрямую в БД:

```bash
# Регистрация
curl -X POST http://localhost:8000/users/register \
  -H "Content-Type: application/json" \
  -d '{"login": "admin", "password": "yourpassword"}'

# Назначение роли (psql или любой GUI)
UPDATE users SET role = 'admin' WHERE login = 'admin';
```

## 5. Переменные окружения — описание

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
