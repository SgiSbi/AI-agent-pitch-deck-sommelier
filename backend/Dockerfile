# Используем официальный образ с Python
FROM python:3.12-slim

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /backend

# Копируем все файлы в контейнер
COPY . /backend

# Устанавливаем зависимости
RUN pip install --default-timeout=100 -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt

EXPOSE 8000

# Указываем команду для запуска приложения
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
