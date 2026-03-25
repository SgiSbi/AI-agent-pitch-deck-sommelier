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
DBPASSWORD=postgres
DBHOST=database
DBPORT=5432
DBNAME=ai_agent
RESET_DB=False

SECRET_KEY=<случайная-строка-минимум-32-символа>
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

> Важно: `DBHOST=database` — это имя сервиса в Docker-сети, не `localhost`.

## 2. Сборка и запуск

```bash
# Сборка образов и запуск всех сервисов
docker-compose up -d --build

# Просмотр логов
docker-compose logs -f backend

# Остановка
docker-compose down

# Остановка с удалением volumes (сброс БД)
docker-compose down -v
```

## 3. Сервисы

| Сервис | Порт | Описание |
|---|---|---|
| `database` | 5432 | PostgreSQL 17 |
| `backend` | 8000 | FastAPI + Uvicorn |

Swagger UI: `http://localhost:8000/docs`

## 4. Volumes

| Volume / Mount | Назначение |
|---|---|
| `pgdata` (named volume) | Данные PostgreSQL |

## 5. Первый администратор

После запуска зарегистрируйте пользователя и назначьте роль admin:

```bash
# Регистрация
curl -X POST http://localhost:8000/users/register \
  -H "Content-Type: application/json" \
  -d '{"login": "admin", "password": "yourpassword"}'

# Подключение к БД внутри контейнера
docker-compose exec database psql -U postgres -d ai_agent \
  -c "UPDATE users SET role = 'admin' WHERE login = 'admin';"
```

## 6. Пересборка после изменений

```bash
# Пересобрать только backend
docker-compose up -d --build backend

# Принудительная пересборка без кэша
docker-compose build --no-cache backend
docker-compose up -d
```

## 7. Полезные команды

```bash
# Войти в контейнер backend
docker-compose exec backend bash

# Посмотреть размер tmp
docker-compose exec backend du -sh /app/tmp

# Проверить статус сервисов
docker-compose ps
```
