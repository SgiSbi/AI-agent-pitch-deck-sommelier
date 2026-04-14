FROM python:3.12-slim

WORKDIR /backend

# Install dependencies first (cached layer)
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . /backend

EXPOSE ${PORT:-8000}

CMD uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}
