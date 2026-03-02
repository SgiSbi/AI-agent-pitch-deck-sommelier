Для запуска создаем файл с названием .env.backend в текущей директории, т.е. /backend со следующим содержанием:

APP_ENV=dev

# Qwen
QWEN_API_KEY=*API-ключ*
QWEN_API_BASE=*url api базы*
QWEN_MODEL=qwen/qwen3-vl-32b-instruct 

# DeepSeek
DEEPSEEK_API_KEY=*API-ключ*
DEEPSEEK_API_BASE=*url api базы*
DEEPSEEK_MODEL=deepseek/deepseek-r1-0528

# Tavily (веб-поиск для промптов 2–5)
TAVILY_API_KEY=*API-ключ от tavily.com*