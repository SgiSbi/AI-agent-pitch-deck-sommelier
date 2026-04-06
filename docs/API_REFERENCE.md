# API Reference

Базовый URL: `http://localhost:8000`  
Swagger UI: `http://localhost:8000/docs`

Все защищённые эндпоинты требуют заголовок:
```
Authorization: Bearer <access_token>
```

---

## Авторизация

### POST /users/register

Регистрация нового пользователя.

**Тело запроса:**
```json
{
  "login": "mylogin",
  "password": "mypassword"
}
```

Ограничения: логин не может быть пустым, пароль — минимум 6 символов.

**Ответ `201`:**
```json
{
  "id": 1,
  "login": "mylogin",
  "role": "standard",
  "plan": null,
  "is_active": true,
  "is_whitelisted": false,
  "created_at": "2026-03-26T10:00:00Z",
  "updated_at": "2026-03-26T10:00:00Z"
}
```

**Ошибки:** `400` — логин уже занят; `422` — невалидные данные.

---

### POST /users/login

Авторизация, возвращает JWT access token.

**Тело запроса:**
```json
{
  "login": "mylogin",
  "password": "mypassword"
}
```

**Ответ `200`:**
```json
{
  "access_token": "<jwt>",
  "token_type": "bearer"
}
```

**Ошибки:** `401` — неверный логин или пароль.

---

### GET /users/me

Информация о текущем авторизованном пользователе. 🔒

**Ответ `200`:**
```json
{
  "id": 1,
  "login": "mylogin",
  "role": "standard",
  "plan": null,
  "is_active": true,
  "is_whitelisted": true,
  "created_at": "2026-03-26T10:00:00Z",
  "updated_at": "2026-03-26T10:00:00Z"
}
```

---

### GET /users/me/reports

Список всех отчётов текущего пользователя. 🔒

**Ответ `200`:**
```json
[
  {
    "id": 1,
    "presentation_dir": "MyStartup_20260326_a1b2c3d4",
    "user_id": 1,
    "pdf_path": "/app/tmp/raw_presentations/MyStartup_20260326_a1b2c3d4.pdf",
    "docx_path": "/app/reports/MyStartup_20260326_a1b2c3d4.docx",
    "report_log_path": "/app/tmp/report_logs/MyStartup_20260326_a1b2c3d4/report_log.json",
    "input_tokens": 45000,
    "output_tokens": 12000,
    "tavily_requests": 24,
    "created_at": "2026-03-26T10:05:00Z"
  }
]
```

---

## Пайплайн

Доступен только пользователям с `is_whitelisted = true` или `role = admin`. 🔒

### POST /pipeline/process-pdf

Полный пайплайн: PDF → DOCX-отчёт по всем 6 секциям.

**Content-Type:** `multipart/form-data`

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `file` | File (PDF) | Да | Презентация в формате PDF |

**Ответ `200`:** файл DOCX

**Заголовки ответа:**

| Заголовок | Описание |
|---|---|
| `X-Input-Tokens` | Суммарные входные токены LLM |
| `X-Output-Tokens` | Суммарные выходные токены LLM |
| `X-Tavily-Requests` | Количество запросов к Tavily |

**Ошибки:** `400` — файл не PDF; `403` — нет доступа; `500` — ошибка генерации; `503` — нет соединения с LLM-провайдером.

```bash
curl -X POST http://localhost:8000/pipeline/process-pdf \
  -H "Authorization: Bearer <token>" \
  -F "file=@presentation.pdf" \
  -o report.docx
```

---

### POST /pipeline/process-pdf/section

Генерация одной выбранной секции отчёта.

**Content-Type:** `multipart/form-data`

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `file` | File (PDF) | Да | Презентация в формате PDF |
| `section` | string (enum) | Да | Название секции (см. ниже) |

**Допустимые значения `section`:**

| Значение | Описание |
|---|---|
| `1_info_from_pdf` | Общая информация о стартапе |
| `2_market_analyze` | Анализ рынка (TAM/SAM/SOM) |
| `3_competitors_analyze` | Анализ конкурентов |
| `4_product_analyze` | Анализ продукта |
| `5_team_analyze` | Анализ команды |
| `6_final_verdict` | Итоговый инвестиционный вердикт |

**Ответ `200`:** файл DOCX

**Заголовки ответа:** `X-Section`, `X-Input-Tokens`, `X-Output-Tokens`, `X-Tavily-Requests`

**Ошибки:** `400`, `403`, `500`, `503`

---

### GET /pipeline/reports/{report_id}/download

Скачать DOCX-отчёт по id. 🔒

Пользователь может скачать только свои отчёты. Администратор — любые.

**Параметры пути:** `report_id` — id отчёта из `GET /users/me/reports`.

**Ответ `200`:** файл DOCX

**Ошибки:** `403` — чужой отчёт; `404` — отчёт не найден или файл отсутствует.

---

## Администрирование

Все эндпоинты доступны только пользователям с `role = admin`. 🔒

### GET /admin/users

Список всех пользователей со статистикой.

**Ответ `200`:**
```json
[
  {
    "id": 1,
    "login": "admin",
    "role": "admin",
    "plan": null,
    "is_active": true,
    "is_whitelisted": false,
    "total_input_tokens": 120000,
    "total_output_tokens": 35000,
    "total_tavily_requests": 96,
    "reports_count": 4,
    "created_at": "2026-03-26T10:00:00Z",
    "updated_at": "2026-03-26T10:00:00Z"
  }
]
```

---

### GET /admin/users/{user_id}

Детальная информация о конкретном пользователе.

**Ответ `200`:** аналогично элементу из `GET /admin/users`

**Ошибки:** `404` — пользователь не найден.

---

### PATCH /admin/users/{user_id}/block

Заблокировать пользователя (`is_active = false`). Заблокированный пользователь получает `403` при любом запросе.

**Ошибки:** `400` — нельзя заблокировать самого себя; `404`.

---

### PATCH /admin/users/{user_id}/unblock

Разблокировать пользователя (`is_active = true`).

**Ошибки:** `404`.

---

### PATCH /admin/users/{user_id}/whitelist

Добавить пользователя в вайтлист (`is_whitelisted = true`). Даёт доступ к пайплайну.

**Ошибки:** `404`.

---

### PATCH /admin/users/{user_id}/unwhitelist

Убрать пользователя из вайтлиста (`is_whitelisted = false`).

**Ошибки:** `404`.

---

### GET /admin/tmp/info

Размер директории `tmp`.

**Ответ `200`:**
```json
{
  "path": "/app/tmp",
  "size_bytes": 524288000,
  "size_mb": 500.0
}
```

---

### DELETE /admin/tmp/clear

Очистить директорию `tmp`. Удаляет всё содержимое и пересоздаёт необходимые поддиректории.

**Ответ `200`:**
```json
{
  "detail": "Директория tmp успешно очищена"
}
```

При частичных ошибках:
```json
{
  "detail": "Очищено с ошибками",
  "errors": ["slides: Permission denied"]
}
```
