# Используем официальный образ с Python
FROM python:3.12-slim

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Копируем все файлы в контейнер
COPY . /app

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Указываем команду для запуска приложения
CMD ["python", "bot.py"]
