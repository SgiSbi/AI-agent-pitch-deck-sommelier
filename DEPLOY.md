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

**`.env`** — корневой файл, параметры docker-compose:
```bash
cp .env.example .env   # если есть, иначе редактируй напрямую
```
```dotenv
DOMAIN=yourdomain.com
BACKEND_PORT=8000
FRONTEND_PORT=3000

POSTGRES_USER=postgres
POSTGRES_PASSWORD=надёжный_пароль
POSTGRES_DB=ai_agent
```

**`backend/.env.backend`** — скопируй из примера и заполни:
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
PORT=8000    # должен совпадать с BACKEND_PORT в .env
```

**`frontend/.env.frontend`** — скопируй из примера и заполни:
```bash
cp frontend/env_example.md frontend/.env.frontend
```
```dotenv
BACKEND_URL=http://backend:8000       # внутренний адрес, не менять
PUBLIC_BACKEND_URL=https://yourdomain.com
PORT=3000                             # должен совпадать с FRONTEND_PORT в .env
FRONTEND_PORT=3000
```

## 4. Получи TLS-сертификат

Запусти временный nginx для верификации домена:
```bash
docker compose --profile init up -d nginx-init
```

Получи сертификат (замени email):
```bash
docker compose --profile init run --rm certbot-init
```

Останови временный nginx:
```bash
docker compose --profile init down
```

## 5. Запусти прод

```bash
docker compose up -d --build
```

Проверь:
```bash
docker compose ps
```

Все сервисы должны быть `running`:
- `database`
- `backend`
- `frontend`
- `nginx`
- `certbot`

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

Certbot-контейнер обновляет сертификат автоматически каждые 12 часов.  
После обновления нужно перезагрузить nginx. Добавь в cron:

```bash
crontab -e
# добавь строку:
0 3 * * * docker compose -f /path/to/docker-compose.yml exec nginx nginx -s reload
```
