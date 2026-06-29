# Деплой со своим nginx

Используй этот вариант если на сервере нет других сайтов.
nginx запускается в Docker вместе с приложением и занимает порты 80 и 443.

```
браузер → nginx контейнер (80/443) → frontend (3000) — SPA и /api/*
                                    → backend (8000) — только /docs, /openapi.json
```

Браузер не обращается к backend напрямую: Express на frontend проксирует `/api/*` на FastAPI внутри Docker-сети.

## Требования
- Docker >= 24, Docker Compose >= 2.20
- Порты 80 и 443 свободны на сервере
- certbot установлен на хосте (`sudo apt install certbot`)
- DNS A-запись домена указывает на IP сервера

---

## 1. Клонируй репозиторий

```bash
git clone <repo_url>
cd <project_folder>
mkdir -p backend/tmp backend/reports
```

## 2. Настрой переменные окружения

**`.env`**:
```dotenv
DOMAIN=yourdomain.com
BACKEND_PORT=8000
FRONTEND_PORT=3000

POSTGRES_USER=postgres
POSTGRES_PASSWORD=надёжный_пароль
POSTGRES_DB=ai_agent
```

**`backend/.env.backend`**:
```dotenv
CORS_ORIGINS=https://yourdomain.com
PORT=8000
# остальные ключи: QWEN_API_KEY, DEEPSEEK_API_KEY, TAVILY_API_KEY, SECRET_KEY, ADMIN_LOGIN, ADMIN_PASSWORD
```

**`frontend/.env.frontend`**:
```dotenv
BACKEND_URL=http://backend:8000
PORT=3000
FRONTEND_PORT=3000
BACKEND_TIMEOUT=600000
```

## 3. Получи TLS-сертификат

Порт 80 должен быть свободен. Certbot сам поднимет временный сервер для верификации:

```bash
sudo apt install certbot
sudo certbot certonly --standalone -d yourdomain.com --email your@email.com --agree-tos --no-eff-email
```

Сертификат сохранится в `/etc/letsencrypt/live/yourdomain.com/`.

## 4. Запусти приложение

```bash
docker compose -f docker-compose.own-nginx.yml up -d --build
```

Проверь:
```bash
docker compose -f docker-compose.own-nginx.yml ps
```

Открой: `https://yourdomain.com`  
Swagger UI: `https://yourdomain.com/docs`

---

## Обновление

```bash
git pull
docker compose -f docker-compose.own-nginx.yml up -d --build
```

## Логи

```bash
docker compose -f docker-compose.own-nginx.yml logs -f nginx
docker compose -f docker-compose.own-nginx.yml logs -f backend
docker compose -f docker-compose.own-nginx.yml logs -f frontend
```

## Обновление сертификата (раз в 3 месяца)

```bash
docker compose -f docker-compose.own-nginx.yml stop nginx
sudo certbot renew
docker compose -f docker-compose.own-nginx.yml start nginx
```
