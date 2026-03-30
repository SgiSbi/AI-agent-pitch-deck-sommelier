# Веб-фронтенд — документация

Язык: русский

## Краткое описание
Веб-фронтенд предоставляет простой UI для загрузки PDF-презентаций и получения DOCX-отчёта, взаимодействуя с бекендом через прокси в `frontend/app.js`.

## Ключевые файлы
- Фронт: [frontend/app.js](frontend/app.js)
- Авторизация/whitelist: [frontend/auth.js](frontend/auth.js)
- Публичные файлы UI: [frontend/public/index.html](frontend/public/index.html), [frontend/public/style.css](frontend/public/style.css), [frontend/public/script.js](frontend/public/script.js)
- Список разрешённых пользователей: [frontend/users_whitelist.json](frontend/users_whitelist.json)

## Требования
- Node.js 18+ (или совместимая версия)
- npm (или yarn)
- Бекенд (FastAPI) должен быть доступен по адресу, указанному в переменной `BACKEND_URL` в `.env.frontend`.

## Переменные окружения
Файлы окружения для frontend: `.env.frontend` (в корне `frontend/`). Основные переменные:
- `PORT` — порт веб-сервера (по умолчанию 3000)
- `BACKEND_URL` — URL бекенд-сервиса (пример: `http://backend:8000` или `http://localhost:8000`)
- `BACKEND_TIMEOUT` — таймаут запроса к бекенду в миллисекундах (по умолчанию 120000)

Пример `.env.frontend`:

BACKEND_URL=http://localhost:8000
PORT=3000
BACKEND_TIMEOUT=120000

## Установка и запуск
1. Перейдите в папку `frontend`:

```bash
cd frontend
```

2. Установите зависимости:

```bash
npm install
```

3. Запустите в режиме разработки:

```bash
npm run dev
```

или в продакшен-режиме:

```bash
npm start
```

После старта фронтенд будет доступен по `http://localhost:3000` (если `PORT=3000`).

## Локальная проверка и поток (smoke test)
1. Откройте UI в браузере.
2. Введите username, который есть в `users_whitelist.json`.
3. Загрузите PDF (клиентских ограничений нет — сервер может наложить лимиты).
4. Нажмите `Анализ` и дождитесь завершения — после этого появится кнопка скачивания DOCX.

Если бекенд недоступен, вызов `/api/backend-health` покажет статус `disconnected`.

## Описание взаимодействия с бекендом (эндпоинты)
Фронтенд использует следующие локальные API (реализованы в `frontend/app.js`):

- `GET /api/health` — базовый health-check фронтенда.
- `GET /api/backend-health` — проверяет доступность бекенда (отправляет запрос на BACKEND_URL).
- `POST /api/auth/login` — локальная точка входа для логина; использует `auth.js` для проверки whitelist.
- `POST /api/process-pdf` — основной маршрут: принимает `multipart/form-data` с ключом `file`, проксирует в бекенд `${BACKEND_URL}/process-pdf` и возвращает DOCX (binary). Заголовки статистики токенов/запросов проксируются обратно: `X-Input-Tokens`, `X-Output-Tokens`, `X-Tavily-Requests`.

Примечание: `frontend/app.js` добавляет в форму поля `username` и `user_id` перед отправкой на бекенд.

## Авторизация и whitelist
Авторизация на фронтенде реализована простым механизмом whitelist в `frontend/users_whitelist.json`. Логика проверки находится в `frontend/auth.js`.
- Для входа достаточно указать username, который присутствует в `users_whitelist.json`.


## Отладка
- Логи фронтенда выводятся в консоль, где запущен `node app.js`.
- Если при проксировании на бекенд возникает ошибка, `frontend/app.js` вернёт JSON с полем `details` — см. консоль сервера и ответ бекенда для диагностики.
