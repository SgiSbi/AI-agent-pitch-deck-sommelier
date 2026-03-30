# Деплой

## Требования
- Docker >= 24
- Docker Compose >= 2.20

## Быстрый старт

### 1. Настройка переменных окружения

```bash
cp backend/env_example.md backend/.env.backend
cp frontend/env_example.md frontend/.env.frontend
```

Заполни `backend/.env.backend`:
- `QWEN_API_KEY` / `DEEPSEEK_API_KEY` — ключи LLM провайдера
- `TAVILY_API_KEY` — ключ Tavily
- `DBPASSWORD` — пароль базы данных
- `SECRET_KEY` — случайная строка для JWT (сгенерировать: `python -c "import secrets; print(secrets.token_hex(32))"`)
- `CORS_ORIGINS` — публичный адрес фронта (например `https://yourdomain.com`)
- `ADMIN_LOGIN` / `ADMIN_PASSWORD` — учётные данные первого администратора

Заполни `frontend/.env.frontend`:
- `PUBLIC_BACKEND_URL` — публичный адрес бэкенда, доступный из браузера (например `https://api.yourdomain.com` или `http://YOUR_IP:8000`)

### 2. Создать директории для данных

```bash
mkdir -p backend/tmp backend/reports
```

### 3. Запуск

```bash
docker compose up -d --build
```

Фронт доступен на `http://YOUR_IP:3000`

## Обновление

```bash
docker compose pull
docker compose up -d --build
```

## Остановка

```bash
docker compose down
```

Данные БД, отчёты и tmp сохраняются в volumes/папках на хосте.
