# Техническая документация бекенда

## Оглавление
1. [Обзор системы](#обзор-системы)
2. [Архитектура](#архитектура)
3. [Технологический стек](#технологический-стек)
4. [Структура проекта](#структура-проекта)
5. [Основные компоненты](#основные-компоненты)
6. [API эндпоинты](#api-эндпоинты)
7. [Пайплайн обработки](#пайплайн-обработки)
8. [Конфигурация и переменные окружения](#конфигурация-и-переменные-окружения)
9. [Развертывание](#развертывание)
10. [Мониторинг и логирование](#мониторинг-и-логирование)

---

## Обзор системы

Бекенд — FastAPI-приложение для автоматизированного анализа стартап-презентаций (pitch deck) на предмет венчурной инвестопригодности. Система использует мультимодальные LLM (Qwen для анализа изображений, DeepSeek для текстового анализа) и веб-поиск (Tavily) для поиска и валидации информации.

### Основные возможности
- Конвертация PDF-презентаций в изображения слайдов
- Извлечение текста и визуальной информации с помощью Qwen Vision
- Многоэтапный анализ через DeepSeek (рынок, конкуренты, продукт, команда, финальный вердикт)
- Веб-поиск для верификации фактов через Tavily API
- Генерация структурированных отчётов в формате DOCX
- JWT-авторизация, ролевая система (standard / admin), вайтлист
- Административная панель управления пользователями и очистки tmp

---

## Архитектура

### Общая схема
```
PDF → Конвертация в изображения → Qwen (извлечение текста) →
→ Генерация поисковых запросов → Tavily (веб-поиск) →
→ DeepSeek (5 параллельных секций анализа) → DeepSeek (финальный вердикт) →
→ Markdown → DOCX
```

### Принципы проектирования
- **Модульность**: каждый этап пайплайна изолирован за интерфейсом (Protocol)
- **Dependency Injection**: все зависимости передаются через конструктор `PipelineService`
- **Параллелизм**: секции анализа DeepSeek выполняются параллельно через `ThreadPoolExecutor`
- **Трассируемость**: полное логирование всех запросов/ответов в файловую систему

---

## Технологический стек

### Основные технологии
- **Python 3.12**: язык программирования
- **FastAPI 0.135.1**: веб-фреймворк для REST API
- **Uvicorn 0.41.0**: ASGI-сервер
- **SQLAlchemy 2.0+ (async)**: ORM
- **asyncpg 0.29+**: асинхронный драйвер PostgreSQL
- **PyMuPDF (fitz) 1.27.1**: конвертация PDF в изображения
- **python-docx 1.2.0**: генерация DOCX-отчётов
- **bcrypt 4.0+**: хеширование паролей
- **python-jose 3.3+**: JWT-токены
- **requests 2.32.5**: HTTP-клиент для LLM API

### Внешние сервисы
- **RouterAI API**: прокси для доступа к Qwen и DeepSeek моделям
- **Qwen3-VL-32B-Instruct**: мультимодальная модель для анализа изображений
- **DeepSeek-R1-0528**: модель для текстового анализа секций и финального вердикта
- **DeepSeek-V3.2**: модель для генерации поисковых запросов
- **Tavily API**: веб-поиск для верификации фактов

---

## Структура проекта

```
backend/
├── src/
│   ├── main.py                        # FastAPI app, startup, роутеры
│   ├── db/
│   │   ├── models.py                  # ORM-модели: User, Report
│   │   ├── session.py                 # AsyncEngine, get_db, Base
│   │   └── db_config.py               # DATABASE_URL из env
│   ├── routes/
│   │   ├── users.py                   # /users/*
│   │   ├── pipeline.py                # /pipeline/*
│   │   └── admin.py                   # /admin/*
│   ├── services/
│   │   └── pipeline_service.py        # PipelineService — оркестратор пайплайна
│   ├── modules/
│   │   ├── interfaces.py              # Protocol-интерфейсы всех компонентов
│   │   ├── llm_client_impl.py         # DefaultLLMClient (Qwen + DeepSeek)
│   │   ├── search_client_impl.py      # TavilySearchClient
│   │   ├── slides_extractor_impl.py   # PdfSlidesExtractor (PyMuPDF)
│   │   ├── docx_converter_impl.py     # DocxConverterService (MD → DOCX)
│   │   ├── markdown_builder_impl.py   # MarkdownBuilderService
│   │   ├── security.py                # bcrypt + JWT
│   │   ├── deps.py                    # FastAPI dependencies
│   │   ├── logging_impl.py            # default_logger
│   │   └── paths.py                   # Пути к директориям
│   ├── repositories/
│   │   ├── interfaces.py              # UserRepository, ReportRepository (Protocol)
│   │   └── sqlalchemy_repos.py        # SQLAlchemy-реализации
│   └── schemas/
│       ├── user.py                    # UserRegister, UserRead, UserAdminRead, ...
│       ├── report.py                  # ReportRead
│       └── pipeline.py                # SectionName (enum), SECTION_PROMPT_MAP
├── promts/                            # Промпты для LLM (8 файлов)
├── reports/                           # Готовые DOCX-отчёты
├── tmp/                               # Временные файлы (не в git)
├── requirements.txt
├── Dockerfile
├── .env.backend
└── env_example.md
```

---

## Основные компоненты

### 1. main.py — FastAPI приложение

Точка входа. Регистрирует роутеры, настраивает CORS, инициализирует БД при старте.

**Startup-логика (`on_startup`):**
- `RESET_DB=True` — полный сброс схемы БД
- `ADMIN_LOGIN` + `ADMIN_PASSWORD` — создаёт admin-пользователя при первом запуске, если не существует

**CORS:** настраивается через `CORS_ORIGINS` (comma-separated список origins).

---

### 2. PipelineService — оркестратор пайплайна

`backend/src/services/pipeline_service.py`

Инкапсулирует весь сценарий обработки презентации. Все зависимости (LLM, поиск, конвертер и т.д.) передаются через конструктор — это позволяет подменять реализации в тестах.

**Публичные методы:**
- `run_full_pipeline(pdf_path, presentation_dir, user_label, user_id)` → `(Path, Dict[str, int])` — полный пайплайн, возвращает путь к DOCX и статистику токенов
- `run_single_section(pdf_path, presentation_dir, section, user_label, user_id)` → `(Path, Dict[str, int])` — генерация одной секции
- `get_report_docx(report_id, current_user_id, current_user_role)` → `Path` — получение DOCX по id отчёта

**Внутренняя реализация:**
- `_run_full_pipeline_sync()` — синхронная реализация, запускается через `anyio.to_thread.run_sync`
- Этапы: извлечение слайдов → Qwen → генерация Tavily-запросов → параллельные секции DeepSeek → финальный вердикт → Markdown → DOCX

---

### 3. Интерфейсы модулей

`backend/src/modules/interfaces.py`

Все компоненты определены как `Protocol` (runtime_checkable):

| Интерфейс | Реализация | Назначение |
|---|---|---|
| `ILogger` | `default_logger` | Логирование событий |
| `ISlidesExtractor` | `PdfSlidesExtractor` | PDF → изображения |
| `ILLMClient` | `DefaultLLMClient` | Все вызовы LLM API |
| `ISearchClient` | `TavilySearchClient` | Веб-поиск |
| `IMarkdownBuilder` | `MarkdownBuilderService` | Сборка Markdown |
| `IDocxConverter` | `DocxConverterService` | Markdown → DOCX |

**Методы `ILLMClient`:**
- `extract_information_from_images(image_paths, presentation_dir)` — Qwen Vision
- `generate_tavily_queries(qwen_text, presentation_dir, stats)` — генерация поисковых запросов
- `run_section(prompt_filename, qwen_text, presentation_dir, search_results, stats)` — одна секция DeepSeek
- `run_sections(qwen_text, presentation_dir, tavily_queries_by_category, stats)` — 5 секций параллельно
- `run_final_verdict(intermediate_md, presentation_dir, stats)` — финальный вердикт

---

### 4. DefaultLLMClient

`backend/src/modules/llm_client_impl.py`

Реализует `ILLMClient`. Использует OpenAI-совместимый `/v1/chat/completions` через RouterAI.

**Конфигурация (`LLMConfig`):**
- `QWEN_API_KEY`, `QWEN_API_BASE`, `QWEN_MODEL`
- `DEEPSEEK_API_KEY`, `DEEPSEEK_API_BASE`, `DEEPSEEK_MODEL`
- `DEEPSEEK_QUERYGEN_MODEL` — отдельная модель для генерации запросов

**Методы:**
- `call_qwen_with_images(prompt, image_paths)` — мультимодальный вызов Qwen
- `call_deepseek(prompt)` — текстовый вызов DeepSeek (основная модель)
- `call_deepseek_querygen(prompt)` — вызов модели для генерации запросов
- `analyze_image(image_path, question)` — анализ одного изображения (base64 data URL)

**Обработка ошибок:** `LLMConnectionError` при сетевых ошибках или HTTP 4xx/5xx.

---

### 5. TavilySearchClient

`backend/src/modules/search_client_impl.py`

Реализует `ISearchClient`. Выполняет множественные поисковые запросы через Tavily API.

**Метод `search(queries, max_results)`:**
- Режим поиска: `advanced`
- Дедупликация результатов по URL
- Форматирование: до 12 000 символов итогового текста, до 800 символов на результат

**Формат результатов:**
```
[1] Заголовок страницы
URL: https://example.com
Content: Фрагмент текста...
```

---

### 6. Авторизация и доступ

`backend/src/modules/deps.py`, `backend/src/modules/security.py`

- **`get_current_user`** — декодирует JWT, проверяет активность пользователя
- **`require_admin`** — требует `role = admin`
- **`require_pipeline_access`** — требует `role = admin` или `is_whitelisted = true`
- **`save_uploaded_pdf`** — сохраняет PDF, генерирует `presentation_dir` вида `{stem}_{YYYYMMDD}_{uuid8}`

Пароли хранятся как bcrypt-хеши. JWT подписывается HS256, время жизни — `ACCESS_TOKEN_EXPIRE_MINUTES`.

---

### 7. Модели данных

**User:**

| Поле | Тип | Описание |
|---|---|---|
| `id` | int | PK |
| `login` | string (unique) | Логин |
| `hashed_password` | string | bcrypt-хеш |
| `role` | string | `standard` / `admin` |
| `plan` | string? | Тарифный план (зарезервировано) |
| `is_active` | bool | Активен / заблокирован |
| `is_whitelisted` | bool | Доступ к пайплайну |
| `total_input_tokens` | bigint | Накопленные входные токены |
| `total_output_tokens` | bigint | Накопленные выходные токены |
| `total_tavily_requests` | int | Накопленные Tavily-запросы |
| `created_at` | datetime | Дата регистрации |
| `updated_at` | datetime | Дата обновления |

**Report:**

| Поле | Тип | Описание |
|---|---|---|
| `id` | int | PK |
| `presentation_dir` | string (unique) | Идентификатор запуска |
| `user_id` | int? | FK → users.id (SET NULL при удалении) |
| `pdf_path` | text? | Путь к исходному PDF |
| `docx_path` | text? | Путь к готовому DOCX |
| `report_log_path` | text? | Путь к JSON-логу |
| `input_tokens` | int | Входные токены этого отчёта |
| `output_tokens` | int | Выходные токены этого отчёта |
| `tavily_requests` | int | Tavily-запросы этого отчёта |
| `created_at` | datetime | Дата создания |

---

## API эндпоинты

Все защищённые эндпоинты требуют заголовок `Authorization: Bearer <token>`.

### Пользователи (`/users`)

| Метод | Путь | Доступ | Описание |
|---|---|---|---|
| POST | `/users/register` | Публичный | Регистрация |
| POST | `/users/login` | Публичный | Авторизация (JSON) → JWT |
| POST | `/users/login/form` | Публичный | OAuth2 form-логин (Swagger UI) |
| GET | `/users/me` | 🔒 | Профиль текущего пользователя |
| GET | `/users/me/reports` | 🔒 | Список отчётов пользователя |

### Пайплайн (`/pipeline`)

Доступен только пользователям с `is_whitelisted = true` или `role = admin`.

| Метод | Путь | Описание |
|---|---|---|
| POST | `/pipeline/process-pdf` | Полный пайплайн: PDF → DOCX |
| POST | `/pipeline/process-pdf/section` | Генерация одной секции |
| GET | `/pipeline/reports/{report_id}/download` | Скачать DOCX по id отчёта |

**POST /pipeline/process-pdf** — принимает `multipart/form-data` с полем `file` (PDF). Возвращает DOCX-файл с заголовками:
- `X-Input-Tokens`, `X-Output-Tokens`, `X-Tavily-Requests`

**POST /pipeline/process-pdf/section** — дополнительно принимает поле `section` (enum `SectionName`):

| Значение | Описание |
|---|---|
| `1_info_from_pdf` | Общая информация о стартапе |
| `2_market_analyze` | Анализ рынка (TAM/SAM/SOM) |
| `3_competitors_analyze` | Анализ конкурентов |
| `4_product_analyze` | Анализ продукта |
| `5_team_analyze` | Анализ команды |
| `6_final_verdict` | Итоговый инвестиционный вердикт |

**GET /pipeline/reports/{report_id}/download** — скачать DOCX по id. Пользователь может скачать только свои отчёты; администратор — любые.

### Администрирование (`/admin`)

Доступно только пользователям с `role = admin`.

| Метод | Путь | Описание |
|---|---|---|
| GET | `/admin/users` | Список всех пользователей со статистикой |
| GET | `/admin/users/{user_id}` | Детальная информация о пользователе |
| PATCH | `/admin/users/{user_id}/block` | Заблокировать пользователя |
| PATCH | `/admin/users/{user_id}/unblock` | Разблокировать пользователя |
| PATCH | `/admin/users/{user_id}/whitelist` | Добавить в вайтлист |
| PATCH | `/admin/users/{user_id}/unwhitelist` | Убрать из вайтлиста |
| GET | `/admin/tmp/info` | Размер директории tmp |
| DELETE | `/admin/tmp/clear` | Очистить директорию tmp |

**Ограничения admin-эндпоинтов:** нельзя изменять самого себя и других администраторов.

---

## Пайплайн обработки

### Этапы

#### Этап 0: Приём и сохранение PDF
- Валидация типа файла (`application/pdf`)
- Генерация уникального ID: `{stem}_{YYYYMMDD}_{uuid8}` (часовой пояс GMT+7)
- Сохранение в `tmp/raw_presentations/`

#### Этап 1: PDF → изображения
- `PdfSlidesExtractor.pdf_to_images()` через PyMuPDF
- Сохранение в `tmp/slides/{presentation_dir}/`

#### Этап 2: Извлечение текста через Qwen
- `ILLMClient.extract_information_from_images()`
- Промпт: `text_extraction.md`
- Модель: `qwen/qwen3-vl-32b-instruct`
- Логи: `tmp/qwen/{presentation_dir}/`

#### Этап 3: Генерация поисковых запросов
- `ILLMClient.generate_tavily_queries()`
- Промпт: `additional_prompt_for_websearch.md`
- Модель: `deepseek/deepseek-v3.2` (или `DEEPSEEK_QUERYGEN_MODEL`)
- Результат: `Dict[str, List[str]]` — категория → список запросов

#### Этап 4: Параллельный анализ 5 секций
- `ILLMClient.run_sections()` — `ThreadPoolExecutor(max_workers=5)`
- Для каждой секции: Tavily-поиск → промпт + результаты → DeepSeek R1
- Логи: `tmp/deepseek/{section_name}/`, `tmp/report_logs/{presentation_dir}/sections/`

| Секция | Промпт | Tavily-категории |
|---|---|---|
| 1. Информация | `1_info_from_pdf_prompt.md` | Команда |
| 2. Рынок | `2_market_analyze_prompt.md` | Рынок, Конкуренция |
| 3. Конкуренты | `3_competitors_analyze_prompt.md` | Конкуренция |
| 4. Продукт | `4_product_analyze_prompt.md` | Продукт |
| 5. Команда | `5_team_analyze_prompt.md` | Команда |

#### Этап 5: Финальный вердикт
- `ILLMClient.run_final_verdict()` — промпт `6_final_verdict_prompt.md` + все 5 секций
- Модель: `deepseek/deepseek-r1-0528`

#### Этап 6: Генерация отчёта
- `IMarkdownBuilder.build_full_markdown()` → `tmp/{presentation_dir}.md`
- `IDocxConverter.convert_md_to_docx()` → `reports/{presentation_dir}.docx`

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

### Обработка ошибок

- `LLMConnectionError` при сетевых ошибках → HTTP 503
- Ретраи: до 3 попыток при HTTP 429/5xx, задержка 2/4/6 сек
- Все запросы/ответы сохраняются в JSON для отладки

---

## Конфигурация и переменные окружения

Файл `backend/.env.backend`. Шаблон — `backend/env_example.md`.

```env
# LLM API
QWEN_API_KEY=
QWEN_API_BASE=https://routerai.ru/api/v1
QWEN_MODEL=qwen/qwen3-vl-32b-instruct
DEEPSEEK_API_KEY=
DEEPSEEK_API_BASE=https://routerai.ru/api/v1
DEEPSEEK_MODEL=deepseek/deepseek-r1-0528
DEEPSEEK_QUERYGEN_MODEL=deepseek/deepseek-v3.2

# Tavily
TAVILY_API_KEY=

# База данных
DBUSER=postgres
DBPASSWORD=
DBHOST=database
DBPORT=5432
DBNAME=ai_agent

# Приложение
RESET_DB=False
SECRET_KEY=                          # python -c "import secrets; print(secrets.token_hex(32))"
ACCESS_TOKEN_EXPIRE_MINUTES=60

# CORS (comma-separated)
CORS_ORIGINS=http://localhost:3000

# Первый администратор (создаётся при старте, если не существует)
ADMIN_LOGIN=
ADMIN_PASSWORD=
```

### Пути к директориям (`paths.py`)

```
backend/
├── tmp/
│   ├── raw_presentations/   # Загруженные PDF
│   ├── slides/              # Изображения слайдов
│   ├── text_from_slides/    # Текст от Qwen
│   ├── qwen/                # Запросы/ответы Qwen
│   ├── deepseek/            # Запросы/ответы DeepSeek по секциям
│   ├── tavily/              # Результаты веб-поиска
│   └── report_logs/         # Метаданные генерации отчётов
└── reports/                 # Готовые DOCX-отчёты
```

---

## Развертывание

### Docker Compose

Три сервиса: `database` (PostgreSQL 17), `backend` (FastAPI), `frontend` (Node.js/Express).

```bash
docker compose up -d --build
```

Фронтенд доступен на порту `80`. Бекенд — только внутри Docker-сети (порт 8000 не проброшен наружу).

Volumes:
- `pgdata` — данные PostgreSQL
- `./backend/tmp` → `/backend/tmp`
- `./backend/reports` → `/backend/reports`

### Первый запуск

Если `ADMIN_LOGIN` и `ADMIN_PASSWORD` заданы в `.env.backend`, администратор создаётся автоматически при старте. Иначе — зарегистрируйте пользователя через API и обновите роль в БД:

```sql
UPDATE users SET role = 'admin', is_whitelisted = true WHERE login = 'yourlogin';
```

---

## Мониторинг и логирование

### Формат логов (stdout)

```
[DD-MM-YYYY HH:MM:SS] [COMPONENT] message
```

Часовой пояс: GMT+7.

**Компоненты:** `PIPELINE`, `SLIDES`, `QWEN`, `DEEPSEEK`, `TAVILY`, `TAVILY_QUERYGEN`, `REPORT`, `REPORTLOG`

### JSON-логи на диске

```
tmp/report_logs/{presentation_dir}/
├── sections/
│   ├── 1_info_from_pdf.json
│   ├── 2_market_analyze.json
│   ├── 3_competitors_analyze.json
│   ├── 4_product_analyze.json
│   ├── 5_team_analyze.json
│   └── final_verdict.json
└── report_log.json
```

### Статистика токенов

Возвращается в заголовках ответа и сохраняется в БД (таблица `reports` и накопительно в `users`):

```python
{
  "input_tokens": 125000,
  "output_tokens": 35000,
  "tavily_requests": 24
}
```

### API документация

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI схема: `http://localhost:8000/openapi.json`
