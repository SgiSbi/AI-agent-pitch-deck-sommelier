# Техническая документация: AI-ассистент для анализа стартап-презентаций

## Навигация

- [Локальный запуск](LOCAL_SETUP.md)
- [Запуск через Docker](DOCKER_SETUP.md)
- [API Reference](API_REFERENCE.md)

---

## 1. Обзор проекта

Система автоматизированного анализа венчурной инвестопригодности стартапов на основе pitch-deck презентаций. Пользователь загружает PDF через веб-интерфейс или REST API, система анализирует его с помощью мультимодальных LLM и веб-поиска, после чего возвращает структурированный отчёт в формате DOCX.

Ключевые возможности:
- Веб-интерфейс (Node.js/Express + vanilla JS) с авторизацией, загрузкой файлов и скачиванием отчётов
- Конвертация PDF-слайдов в изображения для визуального анализа
- Извлечение информации через мультимодальную модель Qwen Vision
- Генерация поисковых запросов и обогащение данных через Tavily Web Search
- Параллельный анализ по 5 направлениям через DeepSeek
- Итоговый инвестиционный вердикт
- Генерация отчёта в формате DOCX
- JWT-авторизация, ролевая система (standard / admin), вайтлист
- Административная панель: управление пользователями, очистка tmp

---

## 2. Архитектура системы

```
┌─────────────────────────────────────────────────────────────┐
│              Браузер (vanilla JS SPA)                       │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP (порт 80)
┌──────────────────────────▼──────────────────────────────────┐
│           Frontend (Node.js / Express)                      │
│  Express · multer · axios · JWT-сессии                      │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP (внутренняя сеть Docker)
┌──────────────────────────▼──────────────────────────────────┐
│                  Backend (FastAPI REST API)                  │
│  FastAPI 0.135 · Uvicorn 0.41 · Python 3.12                 │
│  routes: users · pipeline · admin                           │
└──────────────────────────┬──────────────────────────────────┘
          ┌────────────────┼────────────────┐
          │                │                │
┌─────────▼──────┐ ┌───────▼──────┐ ┌───────▼─────────┐
│  Qwen VL API   │ │ DeepSeek API │ │  Tavily Search  │
│  (RouterAI)    │ │  (RouterAI)  │ │      API        │
└────────────────┘ └──────────────┘ └─────────────────┘
          │
┌─────────▼──────┐
│  PostgreSQL 17 │
└────────────────┘
```

---

## 3. Структура проекта

```
Ai-agent/
├── backend/
│   ├── src/
│   │   ├── main.py
│   │   ├── db/
│   │   │   ├── models.py        # User, Report (SQLAlchemy ORM)
│   │   │   ├── session.py       # AsyncEngine, get_db
│   │   │   └── db_config.py     # URL из env
│   │   ├── routes/
│   │   │   ├── users.py         # /users/*
│   │   │   ├── pipeline.py      # /pipeline/*
│   │   │   └── admin.py         # /admin/*
│   │   ├── services/
│   │   │   └── pipeline_service.py
│   │   ├── modules/
│   │   │   ├── interfaces.py    # Protocol-интерфейсы
│   │   │   ├── llm_client_impl.py
│   │   │   ├── search_client_impl.py
│   │   │   ├── slides_extractor_impl.py
│   │   │   ├── docx_converter_impl.py
│   │   │   ├── markdown_builder_impl.py
│   │   │   ├── security.py      # bcrypt + JWT
│   │   │   ├── deps.py          # FastAPI dependencies
│   │   │   ├── logging_impl.py
│   │   │   └── paths.py         # Пути к директориям
│   │   ├── repositories/
│   │   │   ├── interfaces.py
│   │   │   └── sqlalchemy_repos.py
│   │   └── schemas/
│   │       ├── user.py
│   │       ├── report.py
│   │       └── pipeline.py      # SectionName enum
│   ├── promts/                  # Промпты для LLM (8 файлов)
│   ├── reports/                 # Готовые DOCX-отчёты
│   ├── tmp/                     # Временные файлы (не в git)
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env.backend
├── frontend/
│   ├── app.js                   # Express-сервер, прокси к backend
│   ├── auth.js                  # JWT-middleware фронтенда
│   ├── public/
│   │   ├── index.html           # SPA (login, main, profile, admin)
│   │   ├── script.js            # Клиентская логика
│   │   └── style.css
│   ├── Dockerfile
│   └── .env.frontend
├── docs/
│   ├── TECHNICAL_DOCUMENTATION.md  # этот файл
│   ├── LOCAL_SETUP.md
│   ├── DOCKER_SETUP.md
│   └── API_REFERENCE.md
├── docker-compose.yml
└── DEPLOY.md
```

---

## 4. Технологический стек

### Backend

| Компонент | Технология | Версия |
|---|---|---|
| Web-фреймворк | FastAPI | 0.135.1 |
| ASGI-сервер | Uvicorn | 0.41.0 |
| ORM | SQLAlchemy (async) | 2.0+ |
| БД-драйвер | asyncpg | 0.29+ |
| PDF → изображения | PyMuPDF (fitz) | 1.27.1 |
| Генерация DOCX | python-docx | 1.2.0 |
| Веб-поиск | tavily-python | 1.1.0 |
| HTTP-клиент | requests | 2.32.5 |
| Валидация | pydantic | 2.12.5 |
| Хеширование паролей | bcrypt | 4.0+ |
| JWT | python-jose | 3.3+ |

### Внешние API

| Сервис | Назначение | Модель |
|---|---|---|
| RouterAI / Qwen | Мультимодальный анализ слайдов | qwen/qwen3-vl-32b-instruct |
| RouterAI / DeepSeek | Текстовый анализ по секциям + финальный вердикт | deepseek/deepseek-r1-0528 |
| RouterAI / DeepSeek | Генерация поисковых запросов | deepseek/deepseek-v3.2 |
| Tavily | Веб-поиск для обогащения данных | — |

---

## 5. Модели данных

### User

| Поле | Тип | Описание |
|---|---|---|
| `id` | int | PK |
| `login` | string (unique) | Логин пользователя |
| `hashed_password` | string | bcrypt-хеш пароля |
| `role` | string | `standard` или `admin` |
| `plan` | string? | Тарифный план (зарезервировано) |
| `is_active` | bool | Активен / заблокирован |
| `is_whitelisted` | bool | Доступ к пайплайну |
| `total_input_tokens` | int | Накопленные входные токены |
| `total_output_tokens` | int | Накопленные выходные токены |
| `total_tavily_requests` | int | Накопленные Tavily-запросы |
| `created_at` | datetime | Дата регистрации |
| `updated_at` | datetime | Дата последнего обновления |

### Report

| Поле | Тип | Описание |
|---|---|---|
| `id` | int | PK |
| `presentation_dir` | string (unique) | Идентификатор запуска |
| `user_id` | int? | FK → users.id |
| `pdf_path` | string? | Путь к исходному PDF |
| `docx_path` | string? | Путь к готовому DOCX |
| `report_log_path` | string? | Путь к JSON-логу |
| `input_tokens` | int | Входные токены этого отчёта |
| `output_tokens` | int | Выходные токены этого отчёта |
| `tavily_requests` | int | Tavily-запросы этого отчёта |
| `created_at` | datetime | Дата создания |

---

## 6. Пайплайн анализа

```
PDF-файл
    │
    ▼ Этап 1: pdf_to_images()
Изображения слайдов (PNG)
    │
    ▼ Этап 2: extract_information_from_images()
Qwen VL → текстовое описание всех слайдов
    │
    ▼ Этап 3: generate_tavily_queries()
DeepSeek v3.2 → поисковые запросы по категориям
    │
    ▼ Этап 4: run_sections() — 5 секций параллельно
    ├── Секция 1: Информация из презентации  (Tavily: Команда)
    ├── Секция 2: Анализ рынка               (Tavily: Рынок, Конкуренция)
    ├── Секция 3: Анализ конкурентов         (Tavily: Конкуренция)
    ├── Секция 4: Анализ продукта            (Tavily: Продукт)
    └── Секция 5: Анализ команды             (Tavily: Команда)
    │
    ▼ Этап 5: run_final_verdict()
DeepSeek R1 → Секция 6: Итоговый инвестиционный вердикт
    │
    ▼ Этап 6: build_full_markdown() + convert_md_to_docx()
DOCX-отчёт
```

### Промпты (`backend/promts/`)

| Файл | Назначение |
|---|---|
| `text_extraction.md` | Извлечение текста из слайдов (Qwen) |
| `additional_prompt_for_websearch.md` | Генерация Tavily-запросов |
| `1_info_from_pdf_prompt.md` | Секция 1: общая информация |
| `2_market_analyze_prompt.md` | Секция 2: анализ рынка |
| `3_competitors_analyze_prompt.md` | Секция 3: конкуренты |
| `4_product_analyze_prompt.md` | Секция 4: продукт |
| `5_team_analyze_prompt.md` | Секция 5: команда |
| `6_final_verdict_prompt.md` | Секция 6: вердикт |

### Идентификация запуска

```
<имя_файла>_<YYYYMMDD>_<uuid8>
```
Пример: `MyStartup_20260326_a1b2c3d4`

### Производительность

| Этап | Параллелизм | Типичное время |
|---|---|---|
| PDF → PNG | — | ~5 сек |
| Qwen | — | ~30–60 сек |
| Генерация Tavily-запросов | — | ~10–20 сек |
| Tavily поиск | последовательно | ~20–40 сек |
| DeepSeek секции 1–5 | ThreadPoolExecutor (5) | ~60–120 сек |
| Финальный вердикт | — | ~30–60 сек |
| Генерация DOCX | — | ~2–5 сек |

Итого: **3–6 минут** на полный анализ.

---

## 7. Безопасность

- Пароли хранятся в виде bcrypt-хешей
- Аутентификация через JWT (HS256), время жизни токена настраивается через `ACCESS_TOKEN_EXPIRE_MINUTES`
- Заблокированные пользователи (`is_active = false`) получают `403` на любой запрос
- Пайплайн доступен только пользователям из вайтлиста или администраторам
- Административные эндпоинты доступны только пользователям с `role = admin`

---

## 8. Обработка ошибок

| Ситуация | HTTP-код |
|---|---|
| Файл не является PDF | 400 |
| Невалидные данные запроса | 422 |
| Неверный логин / пароль | 401 |
| Нет токена или токен истёк | 401 |
| Аккаунт заблокирован | 403 |
| Нет доступа к пайплайну | 403 |
| Нет прав администратора | 403 |
| Ресурс не найден | 404 |
| Ошибка соединения с LLM | 503 |
| Ошибка генерации DOCX | 500 |

LLM-запросы: до 3 ретраев при HTTP 429 / 5xx, задержка 2/4/6 сек.

---

## 9. Логирование

Формат (stdout):
```
[DD-MM-YYYY HH:MM:SS] [COMPONENT] message
```

Компоненты: `PIPELINE`, `SLIDES`, `QWEN`, `DEEPSEEK`, `TAVILY`, `TAVILY_QUERYGEN`, `REPORT`, `REPORTLOG`

JSON-логи сохраняются в `tmp/report_logs/<presentation_dir>/sections/`.
