# Запуск через Docker

## Требования

- Docker 24+
- Docker Compose v2+

## 1. Подготовка переменных окружения

Создайте `backend/.env.backend` по образцу `backend/env_example.md`:

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
DBPASSWORD=<пароль>
DBHOST=database
DBPORT=5432
DBNAME=ai_agent
RESET_DB=False

SECRET_KEY=<случайная-строка-минимум-32-символа>
ACCESS_TOKEN_EXPIRE_MINUTES=60

# Публичный адрес фронтенда (для CORS)
CORS_ORIGINS=http://localhost

# Первый администратор — создаётся автоматически при старте
ADMIN_LOGIN=admin
ADMIN_PASSWORD=<пароль>
```

> `DBHOST=database` — имя сервиса в Docker-сети, не `localhost`.

Создайте `frontend/.env.frontend` по образцу `frontend/env_example.md`:

```env
# Внутренний адрес бекенда (для Node.js-сервера)
BACKEND_URL=http://backend:8000

# Публичный адрес бекенда (для браузера)
# Пример: https://api.yourdomain.com или http://YOUR_SERVER_IP:8000
PUBLIC_BACKEND_URL=http://localhost:8000

PORT=3000
BACKEND_TIMEOUT=600000
```

## 2. Создание директорий

```bash
mkdir -p backend/tmp backend/reports
```

## 3. Сборка и запуск

```bash
docker compose up -d --build
```

Фронтенд доступен на `http://YOUR_IP` (порт 80).  
Swagger UI бекенда: `http://YOUR_IP:8000/docs` — только если порт 8000 проброшен (по умолчанию не проброшен).

## 4. Сервисы

| Сервис | Порт (хост) | Описание |
|---|---|---|
| `database` | — (внутренний) | PostgreSQL 17 |
| `backend` | — (внутренний) | FastAPI + Uvicorn |
| `frontend` | 80 | Node.js/Express + SPA |

## 5. Volumes

| Volume / Mount | Назначение |
|---|---|
| `pgdata` (named volume) | Данные PostgreSQL |
| `./backend/tmp` | Временные файлы пайплайна |
| `./backend/reports` | Готовые DOCX-отчёты |

## 6. Первый администратор

Если `ADMIN_LOGIN` и `ADMIN_PASSWORD` заданы в `.env.backend`, администратор создаётся автоматически при первом старте.

Альтернативно — через SQL после запуска:

```bash
docker compose exec database psql -U postgres -d ai_agent \
  -c "UPDATE users SET role = 'admin', is_whitelisted = true WHERE login = 'yourlogin';"
```

## 7. Обновление

```bash
docker compose up -d --build
```

## 8. Остановка

```bash
# Остановить (данные сохраняются)
docker compose down

# Остановить и удалить volumes (сброс БД)
docker compose down -v
```

## 9. Полезные команды

```bash
# Логи бекенда
docker compose logs -f backend

# Войти в контейнер бекенда
docker compose exec backend bash

# Проверить статус сервисов
docker compose ps
```
