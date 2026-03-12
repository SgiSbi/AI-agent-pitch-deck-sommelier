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

Бекенд представляет собой FastAPI-приложение для автоматизированного анализа стартап-презентаций (pitch deck) на предмет венчурной инвестопригодности. Система использует мультимодальные LLM (Qwen для анализа изображений, DeepSeek для текстового анализа) и веб-поиск (Tavily) для поиска и валидации информации.

### Основные возможности
- Конвертация PDF-презентаций в изображения слайдов
- Извлечение текста и визуальной информации с помощью Qwen Vision
- Многоэтапный анализ через DeepSeek (рынок, конкуренты, продукт, команда, финальный вердикт)
- Веб-поиск для верификации фактов через Tavily API
- Генерация структурированных отчетов в формате DOCX
- Управление временными файлами и кэшированием результатов

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
- **Модульность**: каждый этап пайплайна изолирован в отдельной функции
- **Параллелизм**: секции анализа DeepSeek выполняются параллельно через ThreadPoolExecutor
- **Отказоустойчивость**: автоматические ретраи для HTTP-запросов к LLM API
- **Трассируемость**: полное логирование всех запросов/ответов в файловую систему

---

## Технологический стек

### Основные технологии
- **Python 3.12**: язык программирования
- **FastAPI 0.135.1**: веб-фреймворк для REST API
- **Uvicorn 0.41.0**: ASGI-сервер
- **PyMuPDF (fitz) 1.27.1**: конвертация PDF в изображения
- **python-docx 1.2.0**: генерация DOCX-отчетов
- **requests 2.32.5**: HTTP-клиент для LLM API

### Внешние сервисы
- **RouterAI API**: прокси для доступа к Qwen и DeepSeek моделям
- **Qwen3-VL-32B-Instruct**: мультимодальная модель для анализа изображений
- **DeepSeek-R1-0528**: модель для текстового анализа секций
- **DeepSeek-V3.2**: модель для генерации поисковых запросов
- **Tavily API**: веб-поиск для верификации фактов

### Вспомогательные библиотеки
- **python-dotenv 1.2.2**: управление переменными окружения
- **pydantic 2.12.5**: валидация данных
- **python-multipart 0.0.22**: обработка multipart/form-data

---

## Структура проекта

```
backend/
├── src/                          # Исходный код
│   ├── main.py                   # FastAPI приложение и эндпоинты
│   ├── pipeline.py               # Основной пайплайн обработки
│   ├── llm_clients.py            # Клиенты для LLM API
│   ├── pdf_to_images.py          # Конвертация PDF
│   ├── qwen_image.py             # Работа с Qwen Vision
│   ├── tavily_client.py          # Клиент Tavily Search
│   ├── formatting.py             # Конвертация MD в DOCX
│   └── __init__.py
├── promts/                       # Промпты для LLM
│   ├── text_extraction.md        # Извлечение текста из слайдов
│   ├── additional_prompt_for_websearch.md  # Генерация поисковых запросов
│   ├── 1_info_from_pdf_prompt.md # Секция 1: Общая информация
│   ├── 2_market_analyze_prompt.md # Секция 2: Анализ рынка
│   ├── 3_competitors_analyze_prompt.md # Секция 3: Конкуренты
│   ├── 4_product_analyze_prompt.md # Секция 4: Продукт
│   ├── 5_team_analyze_prompt.md  # Секция 5: Команда
│   └── 6_final_verdict_prompt.md # Финальный вердикт
├── tmp/                          # Временные файлы (не в git)
│   ├── raw_presentations/        # Загруженные PDF
│   ├── slides/                   # Изображения слайдов
│   ├── text_from_slides/         # Текст от Qwen
│   ├── qwen/                     # Запросы/ответы Qwen
│   ├── deepseek/                 # Запросы/ответы DeepSeek
│   ├── tavily/                   # Результаты веб-поиска
│   └── report_logs/              # Логи генерации отчетов
├── reports/                      # Готовые DOCX-отчеты
├── requirements.txt              # Python-зависимости
├── Dockerfile                    # Docker-образ
├── .env.backend                  # Переменные окружения
└── env_example.md                # Пример конфигурации
```

---

## Основные компоненты

### 1. main.py - FastAPI приложение

Точка входа приложения, содержит все HTTP-эндпоинты.

**Ключевые функции:**
- `_save_uploaded_pdf()`: сохранение загруженного PDF с генерацией уникального ID
- `process_pdf()`: полный пайплайн обработки (основной эндпоинт)
- Поэтапные эндпоинты для отладки и тестирования
- Утилиты для управления временными файлами

**Особенности:**
- Генерация уникальных идентификаторов презентаций: `{название}_{дата}_{uuid}`
- Возврат статистики использования токенов в HTTP-заголовках
- Валидация типов файлов (PDF, изображения)

### 2. pipeline.py - Основной пайплайн

Содержит всю логику обработки презентаций от PDF до DOCX.

**Основные функции:**

`extract_slides_stage(pdf_path, presentation_dir)` → List[str]
- Конвертирует PDF в изображения слайдов (60 DPI, PNG)
- Возвращает список путей к изображениям

`qwen_from_slides_stage(image_paths, presentation_dir, stats)` → str
- Отправляет изображения в Qwen для извлечения текста
- Обрабатывает слайды чанками по 3 изображения параллельно
- Возвращает объединенный текст всех слайдов

`generate_tavily_queries_stage(qwen_text, presentation_dir, stats)` → Dict[str, List[str]]
- Генерирует поисковые запросы через DeepSeek
- Парсит ответ в структуру {категория: [запросы]}
- Категории: Команда, Рынок, Конкуренция, Продукт, Редфлаги, Трекшн

`send_section_to_deepseek(prompt_filename, qwen_text, presentation_dir, tavily_queries_by_category, stats)` → str
- Отправляет одну секцию анализа в DeepSeek
- Для секций 1-5 выполняет веб-поиск через Tavily (до 8 запросов, 5 результатов на запрос)
- Возвращает markdown-текст секции

`run_deepseek_sections(qwen_text, presentation_dir, tavily_queries_by_category, stats)` → Tuple[List[str], str]
- Параллельно обрабатывает 5 секций анализа через ThreadPoolExecutor
- Возвращает список текстов секций и объединенный markdown

`run_final_verdict(intermediate_md, presentation_dir, stats)` → str
- Генерирует финальный вердикт на основе всех секций
- Использует промпт 6_final_verdict_prompt.md

`build_full_markdown(section_texts, final_text)` → str
- Объединяет все секции в единый markdown-документ

`markdown_to_docx(md_path, docx_path)` → None
- Конвертирует markdown в DOCX через formatting.py

`run_full_pipeline(pdf_path, presentation_dir, user_label)` → Tuple[Path, Dict[str, int]]
- Оркестрирует весь процесс от PDF до DOCX
- Возвращает путь к DOCX и статистику (input_tokens, output_tokens, tavily_requests)

**Механизм ретраев:**
- `_post_deepseek()`: до 3 попыток при HTTP 5xx/429 или некорректном формате ответа
- Экспоненциальная задержка: 2, 4, 6 секунд
- Логирование всех запросов/ответов в JSON

---

### 3. llm_clients.py - Клиенты LLM

Конфигурация и обертки для работы с LLM API.

**Класс LLMConfig:**
- Загружает переменные окружения из `.env.backend`
- Хранит API ключи, базовые URL и названия моделей
- Поддерживает отдельную модель для генерации запросов (DEEPSEEK_QUERYGEN_MODEL)

**Функции:**
- `call_qwen_with_images(prompt, image_paths)`: вызов Qwen с изображениями (устаревший метод)
- `call_deepseek(prompt)`: простой вызов DeepSeek
- `call_deepseek_querygen(prompt)`: вызов модели для генерации запросов
- `_post_chat_completion()`: универсальная функция для OpenAI-совместимых API

### 4. pdf_to_images.py - Конвертация PDF

**Функция `pdf_to_images()`:**
- Использует PyMuPDF (fitz) для рендеринга страниц
- Параметры: DPI (по умолчанию 150), формат (png/jpg)
- Возвращает список путей к созданным изображениям
- Автоматически создает выходную директорию

**Особенности:**
- Zoom-фактор рассчитывается как DPI/72
- Имена файлов: `page_001.png`, `page_002.png`, и т.д.
- Обработка ошибок при отсутствии файла

### 5. qwen_image.py - Анализ изображений

**Функция `analyze_image_with_qwen()`:**
- Кодирует изображение в base64
- Формирует data URL: `data:image/png;base64,{b64}`
- Отправляет в Qwen через OpenAI-совместимый формат messages
- Поддерживает кастомные вопросы для анализа

**Формат запроса:**
```python
messages = [{
    "role": "user",
    "content": [
        {"type": "text", "text": question},
        {"type": "image_url", "image_url": {"url": data_url}}
    ]
}]
```

### 6. tavily_client.py - Веб-поиск

**Функция `search_web()`:**
- Выполняет множественные поисковые запросы через Tavily API
- Параметры: список запросов, max_results_per_query (1-20)
- Режим поиска: "advanced" для более глубокого анализа
- Дедупликация результатов по URL

**Возвращаемые данные:**
- Форматированный текст для промпта (по умолчанию)
- Опционально: кортеж (текст, сырые ответы) при `return_raw=True`

**Формат результатов:**
```
[1] Заголовок страницы
URL: https://example.com
Content: Фрагмент текста (до 800 символов)...
```

**Ограничения:**
- Максимум 12000 символов в итоговом тексте
- Логирование через callback-функцию

### 7. formatting.py - Генерация DOCX

Конвертирует Markdown в форматированный DOCX-документ.

**Основная функция `convert_md_to_docx()`:**
- Парсит Markdown построчно
- Поддерживает заголовки (# - ####)
- Обрабатывает списки (маркированные и нумерованные)
- Конвертирует таблицы в Word Table Grid
- Добавляет горизонтальные линии (---, ***, ___)

**Поддерживаемое форматирование:**
- **Жирный текст**: `**текст**`
- *Курсив*: `*текст*`
- Гиперссылки: `[текст](url)` и голые URL
- Таблицы в Markdown-формате

**Функции обработки:**
- `process_text_with_formatting()`: парсинг inline-форматирования
- `add_formatted_text_to_paragraph()`: применение стилей к параграфу
- `add_hyperlink()`: создание кликабельных ссылок
- `extract_domain()`: извлечение домена из URL (обрезка до 30 символов)

---

## API эндпоинты

### POST /process-pdf
**Основной эндпоинт для полного анализа презентации.**

**Параметры (multipart/form-data):**
- `file`: PDF-файл презентации (обязательный)
- `user_id`: ID пользователя (опциональный)
- `username`: Имя пользователя (опциональный)

**Ответ:**
- Тип: `application/vnd.openxmlformats-officedocument.wordprocessingml.document`
- Файл: DOCX-отчет
- Заголовки:
  - `X-Input-Tokens`: количество входных токенов
  - `X-Output-Tokens`: количество выходных токенов
  - `X-Tavily-Requests`: количество запросов к Tavily

**Процесс:**
1. Сохранение PDF
2. Извлечение слайдов
3. Анализ через Qwen
4. Генерация поисковых запросов
5. Веб-поиск через Tavily
6. Параллельный анализ 5 секций через DeepSeek
7. Финальный вердикт
8. Генерация DOCX

**Пример использования:**
```bash
curl -X POST "http://localhost:8000/process-pdf" \
  -F "file=@presentation.pdf" \
  -F "user_id=12345" \
  -F "username=john_doe" \
  -o report.docx
```

---

### POST /stage/extract-slides
**Этап 1: Извлечение слайдов из PDF.**

**Параметры:**
- `file`: PDF-файл

**Ответ (JSON):**
```json
{
  "presentation_dir": "MyProject_20260312_a1b2c3d4",
  "images": [
    "/path/to/slides/page_001.png",
    "/path/to/slides/page_002.png"
  ]
}
```

---

### POST /stage/qwen-from-pdf
**Этапы 1+2: Извлечение слайдов + анализ через Qwen.**

**Параметры:**
- `file`: PDF-файл

**Ответ (JSON):**
```json
{
  "presentation_dir": "MyProject_20260312_a1b2c3d4",
  "images": ["..."],
  "qwen_text": "Слайд #1:\n— Текст: ...\n— Изображения: ..."
}
```

---

### POST /stage/deepseek-section
**Этап 3: Отправка отдельной секции в DeepSeek.**

**Параметры (JSON):**
```json
{
  "prompt_filename": "2_market_analyze_prompt.md",
  "qwen_text": "текст от Qwen",
  "presentation_dir": "MyProject_20260312_a1b2c3d4"
}
```

**Ответ (JSON):**
```json
{
  "presentation_dir": "MyProject_20260312_a1b2c3d4",
  "prompt_filename": "2_market_analyze_prompt.md",
  "section_text": "## 2. Анализ рынка\n..."
}
```

---

### POST /debug/markdown-from-pdf
**DEBUG: Полный пайплайн без генерации DOCX.**

**Параметры:**
- `file`: PDF-файл

**Ответ (JSON):**
```json
{
  "qwen_text": "...",
  "section_texts": ["секция 1", "секция 2", ...],
  "final_text": "финальный вердикт",
  "markdown": "полный markdown-документ"
}
```

**Использование:** отладка промптов, проверка качества анализа без генерации DOCX.

---

### POST /stage/qwen-image
**Анализ одного изображения через Qwen.**

**Параметры:**
- `file`: изображение (PNG/JPEG)
- `question`: текстовый вопрос (query parameter, по умолчанию: "Что изображено на этой картинке?")

**Ответ (JSON):**
```json
{
  "question": "Опиши этот график",
  "answer": "На графике показан рост выручки...",
  "image_path": "/tmp/abc123_image.png"
}
```

---

### GET /tmp/size
**Получение размера временной директории.**

**Ответ (JSON):**
```json
{
  "size_bytes": 1048576,
  "size_formatted": "1.00 MB",
  "files_count": 42,
  "path": "/backend/tmp"
}
```

---

### DELETE /tmp/cleanup
**Очистка временной директории.**

**Ответ (JSON):**
```json
{
  "success": true,
  "message": "Директория tmp успешно очищена",
  "deleted_items": 42,
  "freed_bytes": 1048576,
  "freed_formatted": "1.00 MB"
}
```

**Примечание:** Сохраняет файл `.gitkeep`.

---

## Пайплайн обработки

### Детальная схема этапов

#### Этап 0: Прием и сохранение PDF
- Валидация типа файла (application/pdf)
- Генерация уникального ID: `{название}_{YYYYMMDD}_{uuid8}`
- Сохранение в `tmp/raw_presentations/`

#### Этап 1: Конвертация PDF → Изображения
**Функция:** `extract_slides_stage()`
- Использует PyMuPDF для рендеринга
- Параметры: 60 DPI, формат PNG
- Сохранение в `tmp/slides/{presentation_dir}/`
- Результат: список путей к изображениям

#### Этап 2: Извлечение текста через Qwen
**Функция:** `qwen_from_slides_stage()`
- Разбивка слайдов на чанки по 3 изображения
- Параллельная обработка чанков через ThreadPoolExecutor
- Кодирование изображений в base64 data URLs
- Промпт: `text_extraction.md`
- Модель: `qwen/qwen3-vl-32b-instruct`
- Сохранение запросов/ответов в `tmp/qwen/`
- Результат: объединенный текст всех слайдов

**Формат вывода Qwen:**
```
Слайд #1:
— Текст: [полный текст]
— Изображения: [описание графиков/диаграмм]
— Примечания: [дополнительная информация]
```

#### Этап 2.5: Генерация поисковых запросов
**Функция:** `generate_tavily_queries_stage()`
- Промпт: `additional_prompt_for_websearch.md`
- Модель: `deepseek/deepseek-v3.2`
- Извлечение сущностей: названия, ФИО, организации, технологии, конкуренты
- Генерация 1-3 запросов на категорию
- Категории: Команда, Рынок, Конкуренция, Продукт, Команда (дополнительно)
- Сохранение в `tmp/tavily/query_generation/{presentation_dir}/`
- Результат: `Dict[str, List[str]]` - категория → список запросов

**Пример структуры запросов:**
```json
{
  "Команда": [
    "\"Иванов Иван\" (МГУ OR Москва) github",
    "\"Петров Петр\" linkedin опыт разработки"
  ],
  "Рынок": [
    "рынок EdTech Россия объем 2025",
    "количество онлайн-школ РФ статистика"
  ],
  "Конкуренция": [
    "\"Конкурент1\" отзывы проблемы Россия",
    "\"Конкурент2\" цена продажи"
  ]
}
```

#### Этап 3: Анализ секций через DeepSeek + Tavily
**Функция:** `run_deepseek_sections()`

**5 параллельных секций:**
1. **Общая информация** (`1_info_from_pdf_prompt.md`)
   - Bullshit Score, проблема, решение, рынок, бизнес-модель, трекшн, команда, запрос
   - Tavily: категории "Команда", "Команда (дополнительно)"
   
2. **Анализ рынка** (`2_market_analyze_prompt.md`)
   - TAM/SAM/SOM, динамика рынка, барьеры входа
   - Tavily: категории "Рынок", "Конкуренция"
   
3. **Анализ конкурентов** (`3_competitors_analyze_prompt.md`)
   - Прямые/косвенные конкуренты, конкурентные преимущества
   - Tavily: категория "Конкуренция"
   
4. **Анализ продукта** (`4_product_analyze_prompt.md`)
   - Технологический стек, уникальность, IP, масштабируемость
   - Tavily: категория "Продукт"
   
5. **Анализ команды** (`5_team_analyze_prompt.md`)
   - Опыт фаундеров, компетенции, пробелы
   - Tavily: категории "Команда", "Команда (дополнительно)"

**Процесс для каждой секции:**
1. Выбор релевантных категорий запросов
2. Выполнение до 8 запросов через Tavily (5 результатов на запрос)
3. Форматирование результатов поиска (до 12000 символов)
4. Формирование промпта: базовый промпт + веб-поиск + текст слайдов
5. Отправка в DeepSeek (`deepseek/deepseek-r1-0528`)
6. Сохранение запросов/ответов в `tmp/deepseek/{section_name}/`
7. Логирование в `tmp/report_logs/{presentation_dir}/sections/{section_name}.json`

**Модель:** `deepseek/deepseek-r1-0528`
**Timeout:** 600 секунд
**Ретраи:** до 3 попыток при ошибках

#### Этап 4: Финальный вердикт
**Функция:** `run_final_verdict()`
- Промпт: `6_final_verdict_prompt.md` + все 5 секций
- Модель: `deepseek/deepseek-r1-0528`
- Синтез итоговой рекомендации на основе всех анализов
- Сохранение в `tmp/deepseek/final_verdict/`

#### Этап 5: Генерация отчета
**Функции:** `build_full_markdown()` + `markdown_to_docx()`
1. Объединение всех секций в единый Markdown
2. Сохранение в `tmp/{presentation_dir}.md`
3. Конвертация Markdown → DOCX через `formatting.py`
4. Сохранение финального отчета в `reports/{presentation_dir}.docx`

**Структура отчета:**
```
# АНАЛИТИЧЕСКИЙ ОТЧЁТ ПО ПРОЕКТУ [Название]
## 1. Информация из презентации
## 2. Анализ рынка
## 3. Анализ конкурентов
## 4. Анализ продукта
## 5. Анализ команды
## 6. Финальный вердикт
```

### Параллелизм и производительность

**Параллельная обработка:**
- Чанки слайдов в Qwen: ThreadPoolExecutor, max_workers = количество чанков
- Секции DeepSeek: ThreadPoolExecutor, max_workers = 5

**Типичное время выполнения:**
- Конвертация PDF (10 слайдов): ~5 секунд
- Qwen анализ (10 слайдов, 4 чанка): ~30-60 секунд
- Генерация запросов: ~10-20 секунд
- Tavily поиск (5 секций × 8 запросов): ~20-40 секунд
- DeepSeek секции (параллельно): ~60-120 секунд
- Финальный вердикт: ~30-60 секунд
- Генерация DOCX: ~2-5 секунд

**Итого:** 3-6 минут на полный анализ презентации.

### Обработка ошибок

**Стратегия ретраев:**
- HTTP 429 (Rate Limit): повтор с задержкой
- HTTP 5xx (Server Error): повтор с задержкой
- Некорректный формат ответа: повтор
- Экспоненциальная задержка: 2s, 4s, 6s
- Максимум попыток: 3

**Логирование ошибок:**
- Все запросы/ответы сохраняются в JSON
- Timestamp в GMT+7
- Компонент и имя промпта в логах

---

## Конфигурация и переменные окружения

### Файл .env.backend

Все конфигурационные параметры хранятся в `.env.backend` в корне директории `backend/`.

**Обязательные переменные:**

```bash
# Qwen API (мультимодальная модель для анализа изображений)
QWEN_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
QWEN_API_BASE=https://routerai.ru/api/v1
QWEN_MODEL=qwen/qwen3-vl-32b-instruct

# DeepSeek API (текстовый анализ)
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
DEEPSEEK_API_BASE=https://routerai.ru/api/v1
DEEPSEEK_MODEL=deepseek/deepseek-r1-0528

# DeepSeek для генерации поисковых запросов (опционально, по умолчанию = DEEPSEEK_MODEL)
DEEPSEEK_QUERYGEN_MODEL=deepseek/deepseek-v3.2

# Tavily Search API (веб-поиск)
TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

**Опциональные переменные (для будущего использования):**

```bash
# База данных PostgreSQL
DBUSER=postgres
DBPASSWORD=postgres
DBHOST=localhost
DBPORT=5432
DBNAME=ai_agent
RESET_DB=True
```

### Пример конфигурации

Файл `env_example.md` содержит шаблон для создания `.env.backend`:

```markdown
QWEN_API_KEY=*API-ключ*
QWEN_API_BASE=*url api базы*
QWEN_MODEL=qwen/qwen3-vl-32b-instruct 
DEEPSEEK_API_KEY=*API-ключ*
DEEPSEEK_API_BASE=*url api базы*
DEEPSEEK_MODEL=deepseek/deepseek-r1-0528
DEEPSEEK_QUERYGEN_MODEL=deepseek/deepseek-v3.2
TAVILY_API_KEY=*API-ключ от tavily.com*
```

### Получение API ключей

**RouterAI (Qwen + DeepSeek):**
1. Регистрация на https://routerai.ru
2. Создание API ключа в личном кабинете
3. Один ключ используется для обеих моделей

**Tavily Search:**
1. Регистрация на https://tavily.com
2. Получение API ключа в dashboard
3. Бесплатный тариф: 1000 запросов/месяц

### Конфигурация моделей

**Qwen3-VL-32B-Instruct:**
- Мультимодальная модель (текст + изображения)
- Контекст: 32K токенов
- Использование: извлечение текста и описание визуальных элементов

**DeepSeek-R1-0528:**
- Текстовая модель с reasoning capabilities
- Контекст: 64K токенов
- Использование: аналитические секции и финальный вердикт

**DeepSeek-V3.2:**
- Более быстрая модель для простых задач
- Использование: генерация поисковых запросов

### Настройка путей

Все пути определяются в `pipeline.py` относительно `BASE_DIR`:

```python
BASE_DIR = Path(__file__).resolve().parents[1]  # backend/
PROMPTS_DIR = BASE_DIR / "promts"
TMP_DIR = BASE_DIR / "tmp"
RESULT_DIR = BASE_DIR / "reports"
```

**Временные директории:**
- `tmp/raw_presentations/` - загруженные PDF
- `tmp/slides/` - изображения слайдов
- `tmp/text_from_slides/` - текст от Qwen
- `tmp/qwen/requests/` и `tmp/qwen/responses/` - логи Qwen
- `tmp/deepseek/{section}/` - логи DeepSeek по секциям
- `tmp/tavily/` - результаты веб-поиска
- `tmp/report_logs/` - метаданные генерации отчетов

**Выходные директории:**
- `reports/` - готовые DOCX-отчеты

---

## Мониторинг и логирование

### Система логирования

**Функция `_log(component, message)`:**
- Формат: `[DD-MM-YYYY HH:MM:SS] [COMPONENT] message`
- Часовой пояс: GMT+7
- Вывод: stdout (перехватывается Docker/systemd)

**Компоненты логирования:**
- `PIPELINE`: основной пайплайн
- `SLIDES`: конвертация PDF
- `REPORTLOG`: сохранение запросов/ответов
- `DEEPSEEK`: запросы к DeepSeek
- `TAVILY`: веб-поиск
- `TAVILY:QUERYGEN`: генерация запросов
- `REPORT`: генерация финального отчета

**Пример логов:**
```
[12-03-2026 14:23:45] [PIPELINE] Start full pipeline for 'MyProject_20260312_a1b2c3d4'
[12-03-2026 14:23:50] [SLIDES] Start processing PDF: /backend/tmp/raw_presentations/MyProject.pdf
[12-03-2026 14:23:55] [SLIDES] slide processing completed successfully
[12-03-2026 14:24:00] [PIPELINE] Starting Qwen for 'MyProject_20260312_a1b2c3d4' (10 slides)
[12-03-2026 14:24:45] [PIPELINE] Qwen finished for 'MyProject_20260312_a1b2c3d4' (15234 chars)
[12-03-2026 14:25:00] [TAVILY:QUERYGEN] Query plan text saved to: /backend/tmp/tavily/query_generation/...
[12-03-2026 14:25:30] [TAVILY:2_market_analyze] Query 1/3: рынок EdTech Россия объем 2025
[12-03-2026 14:26:00] [DEEPSEEK] 2_market_analyze: request saved to: /backend/tmp/deepseek/...
[12-03-2026 14:27:30] [PIPELINE] Section 2/5 completed
[12-03-2026 14:30:00] [PIPELINE] Pipeline completed: report ready at /backend/reports/MyProject_20260312_a1b2c3d4.docx
```

### Структура логов на диске

**Запросы/ответы Qwen:**
```
tmp/qwen/
├── requests/{presentation_dir}/
│   ├── chunk_01_request.json
│   ├── chunk_02_request.json
│   └── ...
└── responses/{presentation_dir}/
    ├── chunk_01_response.json
    ├── chunk_02_response.json
    └── ...
```

**Запросы/ответы DeepSeek:**
```
tmp/deepseek/
├── 1_info_from_pdf/
│   ├── requests/{presentation_dir}.json
│   └── responses/{presentation_dir}.json
├── 2_market_analyze/
├── 3_competitors_analyze/
├── 4_product_analyze/
├── 5_team_analyze/
└── final_verdict/
```

**Результаты Tavily:**
```
tmp/tavily/
├── query_generation/{presentation_dir}/
│   ├── queries_by_category.json
│   ├── query_plan.txt
│   ├── requests/request.json
│   └── responses/response.json
├── 1_info_from_pdf/{presentation_dir}/
│   ├── queries.json
│   ├── results.json
│   ├── results_text.txt
│   └── tavily_raw.json
├── 2_market_analyze/{presentation_dir}/
└── ...
```

**Метаданные отчетов:**
```
tmp/report_logs/{presentation_dir}/
├── sections/
│   ├── 1_info_from_pdf.json
│   ├── 2_market_analyze.json
│   ├── 3_competitors_analyze.json
│   ├── 4_product_analyze.json
│   ├── 5_team_analyze.json
│   └── final_verdict.json
├── query_generation_summary.json
└── report_log.json
```

**Формат section log (пример):**
```json
{
  "presentation_dir": "MyProject_20260312_a1b2c3d4",
  "prompt_filename": "2_market_analyze_prompt.md",
  "prompt_name": "2_market_analyze",
  "tavily": {
    "used": true,
    "used_categories": ["Рынок", "Конкуренция"],
    "queries": ["рынок EdTech Россия объем 2025", "..."],
    "dir": "/backend/tmp/tavily/2_market_analyze/MyProject_20260312_a1b2c3d4",
    "queries_path": "...",
    "results_path": "...",
    "results_text_path": "...",
    "results_char_count": 8543
  },
  "deepseek": {
    "request_path": "/backend/tmp/deepseek/2_market_analyze/requests/MyProject_20260312_a1b2c3d4.json",
    "response_path": "/backend/tmp/deepseek/2_market_analyze/responses/MyProject_20260312_a1b2c3d4.json",
    "response_char_count": 3421
  }
}
```

**Формат report_log.json:**
```json
{
  "presentation_dir": "MyProject_20260312_a1b2c3d4",
  "paths": {
    "pdf_path": "/backend/tmp/raw_presentations/MyProject_20260312_a1b2c3d4.pdf",
    "md_path": "/backend/tmp/MyProject_20260312_a1b2c3d4.md",
    "docx_path": "/backend/reports/MyProject_20260312_a1b2c3d4.docx"
  },
  "sizes": {
    "md_chars": 45678,
    "docx_bytes": 123456
  },
  "tavily": {
    "query_generation_dir": "/backend/tmp/tavily/query_generation/MyProject_20260312_a1b2c3d4",
    "per_section_root": "/backend/tmp/tavily"
  },
  "sections": {
    "1_info_from_pdf": "/backend/tmp/report_logs/MyProject_20260312_a1b2c3d4/sections/1_info_from_pdf.json",
    "2_market_analyze": "...",
    "3_competitors_analyze": "...",
    "4_product_analyze": "...",
    "5_team_analyze": "...",
    "final_verdict": "..."
  }
}
```

### Метрики и статистика

**Возвращаемая статистика:**
```python
{
  "input_tokens": 125000,      # Суммарно по всем запросам
  "output_tokens": 35000,      # Суммарно по всем ответам
  "tavily_requests": 1         # Количество вызовов Tavily API
}
```

**Источники токенов:**
- Qwen: извлечение текста из слайдов
- DeepSeek: генерация поисковых запросов
- DeepSeek: 5 секций анализа
- DeepSeek: финальный вердикт

### Управление временными файлами

**Автоматическая очистка:**
- Эндпоинт `DELETE /tmp/cleanup` для ручной очистки
- Рекомендуется настроить cron-задачу для периодической очистки

**Пример cron-задачи (Linux):**
```bash
# Очистка tmp каждую ночь в 3:00
0 3 * * * curl -X DELETE http://localhost:8000/tmp/cleanup
```

**Мониторинг размера:**
- Эндпоинт `GET /tmp/size` для проверки использования диска
- Настройка алертов при превышении порога (например, 10 GB)



## Контакты и поддержка

**API документация:**
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- OpenAPI схема: `http://localhost:8000/openapi.json`

---