Для запуска создаем файл с названием .env.frontend в текущей директории, т.е. /frontend со следующим содержанием:

# Telegram
TELEGRAM_BOT_TOKEN=*токен телеграмм бота*

# Адрес backend‑сервиса
BACKEND_URL=*URL бэкенда, по умолчанию http://localhost:8000/process-pdf*

MAX_FILE_SIZE=20971520
BACKEND_TIMEOUT=120