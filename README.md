# ИИ-ассистент для автоматизированного анализа стартапа на венчурную инвестопригодность на основе презентации проекта

---

## Инструкция по запуску 

Для запуска проекта убедитесь, что у вас установлены **Git**, **Docker** и **Docker Compose**.

### 1. Клонирование репозитория
Склонируйте проект на локальную машину:
```bash
git clone https://github.com/Wizz4769/Ai-agent.git
cd Ai-agent
```

### 2. Настройка Backend
Перейдите в папку бэкенда и создайте файл переменных окружения:
```bash
cd backend
cp .env_example.md .env.backend  # Если есть шаблон, иначе создайте вручную
```
> Необходимо заполнить `.env.backend` необходимыми данными (api-ключи допступа к LLM, url api-базы, используемые модели, ключ доступа к Tavily).
> ```env_example.md
># Для запуска создаем файл с названием .env.backend в текущей директории, т.е. /backend со следующим содержанием:
>
># Qwen
>QWEN_API_KEY=*API-ключ*
>QWEN_API_BASE=*url api базы*
>QWEN_MODEL=qwen/qwen3-vl-32b-instruct 
>
># DeepSeek
>DEEPSEEK_API_KEY=*API-ключ*
>DEEPSEEK_API_BASE=*url api базы*
>DEEPSEEK_MODEL=deepseek/deepseek-r1-0528
>DEEPSEEK_QUERYGEN_MODEL=deepseek/deepseek-v3.2
>
># Tavily (веб-поиск для промптов 2–5)
>TAVILY_API_KEY=*API-ключ от tavily.com*
> ```

### 3. Настройка Frontend
Перейдите в папку фронтенда. Здесь необходимо создать два файла:
```bash
cd ../frontend
```

1.  **Создайте `.env.frontend`**:
    ```bash
    cp env_example.md .env.frontend
    ```
  > Необходимо заполнить `.env.frontend` необходимыми данными (telegram_bot_token, получить у t.me/@BotFather, backend_url можно использовать по умолчанию, в зависимости от порта на котором запущен
  > сервер).
  > ```env_example.md
  ># Для запуска создаем файл с названием .env.frontend в текущей директории, т.е. /frontend со следующим содержанием:
  >
  ># Telegram
  >TELEGRAM_BOT_TOKEN=*токен телеграмм бота*
  >
  ># Адрес backend‑сервиса
  >BACKEND_URL=*URL бэкенда, по умолчанию http://backend:8000/process-pdf*
  >
  >MAX_FILE_SIZE=20971520
  >BACKEND_TIMEOUT=720
  > ```

2.  **Создайте `users_whitelist.json`**:
    Этот файл необходим для управления доступом пользователей.
    ```bash
    touch users_whitelist.json
    ```
    *Пример структуры файла (вместо name вставить Telegram Username без @, вместо role admin/standard):*
    ```json
    {
      "users": {
        "name": "role"
      }
    }
    ```

### 4. Запуск через Docker Compose
Вернитесь в корневую директорию проекта и запустите контейнеры:
```bash
cd ..
docker compose up --build -d
```

После запуска приложение будет доступно в вашем телеграмм боте

---
