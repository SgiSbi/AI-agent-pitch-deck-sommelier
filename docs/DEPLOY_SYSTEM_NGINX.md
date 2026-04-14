# Деплой с системным nginx

Используй этот вариант если на сервере уже есть nginx, который обслуживает другие сайты.
Приложение запускается в Docker, системный nginx проксирует трафик на него.

```
браузер → системный nginx (80/443) → localhost:3000 (frontend)
                                    → localhost:8000 (backend)
```

## Требования
- Docker >= 24, Docker Compose >= 2.20
- nginx установлен на хосте
- certbot установлен на хосте

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
BACKEND_PORT=8000
FRONTEND_PORT=3000

POSTGRES_USER=postgres
POSTGRES_PASSWORD=надёжный_пароль
POSTGRES_DB=ai_agent
```

**`backend/.env.backend`**:
```dotenv
CORS_ORIGINS=https://app.yourdomain.com
PUBLIC_BACKEND_URL=https://app.yourdomain.com
PORT=8000
# остальные ключи: QWEN_API_KEY, DEEPSEEK_API_KEY, TAVILY_API_KEY, SECRET_KEY, ADMIN_LOGIN, ADMIN_PASSWORD
```

**`frontend/.env.frontend`**:
```dotenv
BACKEND_URL=http://backend:8000
PUBLIC_BACKEND_URL=https://app.yourdomain.com
PORT=3000
FRONTEND_PORT=3000
```

## 3. Получи TLS-сертификат

```bash
sudo certbot certonly --nginx -d app.yourdomain.com --email your@email.com --agree-tos --no-eff-email
```

## 4. Добавь конфиг в системный nginx

Создай файл `/etc/nginx/sites-available/app.yourdomain.com`:

```nginx
server {
    listen 80;
    server_name app.yourdomain.com;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name app.yourdomain.com;

    ssl_certificate     /etc/letsencrypt/live/app.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/app.yourdomain.com/privkey.pem;
    ssl_protocols TLSv1.2 TLSv1.3;

    location ~ ^/(pipeline|users|admin|docs|openapi.json)(/|$) {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 50m;
        proxy_read_timeout 300s;
    }

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Подключи и перезагрузи:
```bash
sudo ln -s /etc/nginx/sites-available/app.yourdomain.com /etc/nginx/sites-enabled/
sudo nginx -t && sudo nginx -s reload
```

## 5. Запусти приложение

```bash
docker compose -f docker-compose.system-nginx.yml up -d --build
```

Проверь:
```bash
docker compose -f docker-compose.system-nginx.yml ps
```

Открой: `https://app.yourdomain.com`

---

## Обновление

```bash
git pull
docker compose -f docker-compose.system-nginx.yml up -d --build
```

## Логи

```bash
docker compose -f docker-compose.system-nginx.yml logs -f backend
docker compose -f docker-compose.system-nginx.yml logs -f frontend
```
