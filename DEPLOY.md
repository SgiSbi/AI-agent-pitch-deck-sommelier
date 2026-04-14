# Деплой на прод с TLS

## Требования
- Docker >= 24, Docker Compose >= 2.20
- Порты 80 и 443 открыты на сервере
- DNS A-запись домена указывает на IP сервера

---

## 1. Клонируй репозиторий

```bash
git clone <repo_url>
cd <project_folder>
```

## 2. Создай директории

```bash
mkdir -p backend/tmp backend/reports certbot/www certbot/conf
```

## 3. Настрой переменные окружения

**`.env`** — домен, порты, email для сертификата:
```dotenv
DOMAIN=yourdomain.com
CERTBOT_EMAIL=your@email.com
BACKEND_PORT=8000
FRONTEND_PORT=3000

POSTGRES_USER=postgres
POSTGRES_PASSWORD=надёжный_пароль
POSTGRES_DB=ai_agent
```

**`backend/.env.backend`**:
```bash
cp backend/env_example.md backend/.env.backend
```
Обязательные поля:
```dotenv
QWEN_API_KEY=...
DEEPSEEK_API_KEY=...
TAVILY_API_KEY=...
DBPASSWORD=тот_же_пароль_что_в_.env
SECRET_KEY=  # python -c "import secrets; print(secrets.token_hex(32))"
CORS_ORIGINS=https://yourdomain.com
ADMIN_LOGIN=admin
ADMIN_PASSWORD=надёжный_пароль
PORT=8000
```

**`frontend/.env.frontend`**:
```bash
cp frontend/env_example.md frontend/.env.frontend
```
```dotenv
BACKEND_URL=http://backend:8000
PUBLIC_BACKEND_URL=https://yourdomain.com
PORT=3000
FRONTEND_PORT=3000
```

---

## 4. Получи TLS-сертификат

```bash
sudo apt install certbot
sudo certbot certonly --standalone -d yourdomain.com --email your@email.com --agree-tos --no-eff-email
```

Сертификат ляжет в `/etc/letsencrypt/live/yourdomain.com/` — nginx подхватит его автоматически.

## 5. Запусти сервер

```bash
docker compose up -d --build
```

Проверь:
```bash
docker compose ps
```

Открой в браузере: `https://yourdomain.com`  
Swagger UI: `https://yourdomain.com/docs`

---

## Обновление приложения

```bash
git pull
docker compose up -d --build
```

## Остановка

```bash
docker compose down
```

## Логи

```bash
docker compose logs -f nginx
docker compose logs -f backend
docker compose logs -f frontend
```

---

## Обновление TLS-сертификата

`certbot-renew` обновляет сертификат автоматически каждые 12 часов.  
После обновления перезагрузи nginx:

```bash
docker compose exec nginx nginx -s reload
```

Или в cron:
```bash
0 3 * * * docker compose -f /path/to/docker-compose.yml exec nginx nginx -s reload
```
