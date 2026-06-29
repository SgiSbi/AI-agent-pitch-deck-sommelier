# Деплой с системным nginx

Используй этот вариант, если на сервере уже есть nginx, который обслуживает другие сайты.  
Приложение запускается в Docker; системный nginx проксирует HTTPS-трафик на контейнер **frontend**.

```
браузер
  → системный nginx (80/443)
      → localhost:3000  frontend (SPA + /api/*)
            → backend:8000  (внутри Docker-сети, с хоста — 127.0.0.1:8000)
      → localhost:8000  backend (только /docs, /openapi.json — опционально)
```

**Важно:** браузер обращается только к frontend. Маршруты `/api/auth/*`, `/api/process-pdf/*` и т.д. обслуживает Node.js (Express), который сам проксирует запросы на FastAPI. Не направляй `/api` напрямую на backend — там другие пути (`/users`, `/pipeline`).

Страницы приложения: `/`, `/login`, `/generate`, `/reports`, `/profile`, `/admin`, `/change-password`.

---

## Требования

- Docker >= 24, Docker Compose >= 2.20
- nginx и certbot на хосте
- DNS A-запись домена указывает на IP сервера
- Порты `3000` и `8000` на `127.0.0.1` свободны (или задайте другие в `.env`)

---

## 1. Клонируй репозиторий

```bash
git clone <repo_url>
cd <project_folder>
mkdir -p backend/tmp backend/reports
```

---

## 2. Переменные окружения

### Корневой `.env`

```dotenv
BACKEND_PORT=8000
FRONTEND_PORT=3000

POSTGRES_USER=postgres
POSTGRES_PASSWORD=надёжный_пароль
POSTGRES_DB=ai_agent
```

### `backend/.env.backend`

Скопируй шаблон и заполни значения:

```bash
cp backend/env_example.md backend/.env.backend
```

Обязательные поля:

```dotenv
QWEN_API_KEY=...
DEEPSEEK_API_KEY=...
TAVILY_API_KEY=...

DBUSER=postgres
DBPASSWORD=тот_же_пароль_что_в_корневом_.env
DBHOST=database
DBPORT=5432
DBNAME=ai_agent

SECRET_KEY=          # python -c "import secrets; print(secrets.token_hex(32))"
CORS_ORIGINS=https://app.yourdomain.com

ADMIN_LOGIN=admin
ADMIN_PASSWORD=надёжный_пароль

PORT=8000
RESET_DB=False
```

### `frontend/.env.frontend`

```bash
cp frontend/env_example.md frontend/.env.frontend
```

```dotenv
# Внутренний адрес backend в Docker-сети (не менять при system-nginx)
BACKEND_URL=http://backend:8000

PORT=3000
FRONTEND_PORT=3000

# Таймаут ожидания backend при генерации отчёта (10 минут)
BACKEND_TIMEOUT=600000
```

`PUBLIC_BACKEND_URL` в текущей архитектуре браузером не используется — все запросы идут на `/api/*` того же домена.

---

## 3. TLS-сертификат

```bash
sudo certbot certonly --nginx -d app.yourdomain.com --email your@email.com --agree-tos --no-eff-email
```

---

## 4. Конфиг системного nginx

Создай `/etc/nginx/sites-available/app.yourdomain.com`:

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

    client_max_body_size 50m;

    # Swagger FastAPI (опционально)
    location ~ ^/(docs|openapi\.json|redoc)(/|$) {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # SPA и /api/* → frontend
    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        proxy_connect_timeout 60s;
        proxy_send_timeout 600s;
        proxy_read_timeout 600s;
    }
}
```

Подключи сайт и перезагрузи nginx:

```bash
sudo ln -s /etc/nginx/sites-available/app.yourdomain.com /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

Конфиг для Docker-nginx (`docker-compose.own-nginx.yml`) лежит в `nginx/nginx.conf.template` и использует ту же схему маршрутизации.

---

## 5. Запуск приложения

```bash
docker compose -f docker-compose.system-nginx.yml up -d --build
```

Проверка:

```bash
docker compose -f docker-compose.system-nginx.yml ps
curl -s http://127.0.0.1:3000/api/health
curl -s http://127.0.0.1:8000/docs -o /dev/null -w "%{http_code}\n"
```

Открой в браузере: `https://app.yourdomain.com`

---

## 6. Проверка после деплоя

| URL | Ожидание |
|-----|----------|
| `https://app.yourdomain.com/` | Главная страница |
| `https://app.yourdomain.com/login` | Форма входа |
| `https://app.yourdomain.com/api/health` | `{"status":"ok"}` |
| `https://app.yourdomain.com/docs` | Swagger UI (если включён location выше) |

Генерация отчёта: на странице `/generate` — полный или частичный отчёт; статус — на `/reports`.

---

## Обновление

```bash
git pull
docker compose -f docker-compose.system-nginx.yml up -d --build
```

---

## Логи

```bash
docker compose -f docker-compose.system-nginx.yml logs -f backend
docker compose -f docker-compose.system-nginx.yml logs -f frontend
sudo tail -f /var/log/nginx/error.log
```

---

## Обновление сертификата

```bash
sudo certbot renew
sudo systemctl reload nginx
```

---

## Типичные проблемы

**502 Bad Gateway на `/api/*`**  
Контейнер frontend не запущен или слушает не тот порт. Проверь `docker compose ps` и `curl http://127.0.0.1:3000/api/health`.

**404 на `/api/auth/login` при проксировании на backend**  
Неверная схема: `/api` должен идти на **frontend** (порт 3000), не на backend.

**504 при генерации отчёта**  
Увеличь `proxy_read_timeout` в nginx (до `600s`) и `BACKEND_TIMEOUT` во `frontend/.env.frontend`.

**413 Request Entity Too Large**  
Увеличь `client_max_body_size` (PDF до 50 МБ уже задано в примере).

**CORS-ошибки**  
В `backend/.env.backend` укажи точный origin: `CORS_ORIGINS=https://app.yourdomain.com` (без слэша в конце).

---

## Безопасность

- В `docker-compose.system-nginx.yml` порты `3000` и `8000` привязаны к `127.0.0.1` — снаружи доступен только nginx на 443.
- Не публикуй backend напрямую в интернет, если не нужен внешний API.
- Задай сильные `SECRET_KEY`, `POSTGRES_PASSWORD`, `ADMIN_PASSWORD`.
