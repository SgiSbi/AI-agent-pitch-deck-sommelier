import os
from typing import List, Optional

import requests
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent / ".env.backend")

class LLMConfig:
    """
    Конфигурация для вызова моделей Qwen и DeepSeek через RouterAI
    (OpenAI‑совместимый /v1/chat/completions).

    Ожидаемые переменные:
    - QWEN_API_KEY
    - QWEN_API_BASE  (например: https://routerai.ru/api/v1)
    - QWEN_MODEL     (например: 'qwen/qwen3-vl-32b-instruct')
    - DEEPSEEK_API_KEY
    - DEEPSEEK_API_BASE
    - DEEPSEEK_MODEL (например: 'deepseek/deepseek-r1-0528')
    - DEEPSEEK_QUERYGEN_MODEL (опционально, отдельная модель для генерации поисковых запросов)
    """

    qwen_api_key: str = os.getenv("QWEN_API_KEY", "")
    qwen_api_base: str = os.getenv("QWEN_API_BASE", "https://routerai.ru/api/v1")
    qwen_model: str = os.getenv("QWEN_MODEL", "qwen/qwen3-vl-32b-instruct")

    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_api_base: str = os.getenv("DEEPSEEK_API_BASE", "https://routerai.ru/api/v1")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek/deepseek-r1-0528")
    deepseek_querygen_model: str = os.getenv("DEEPSEEK_QUERYGEN_MODEL", "") or os.getenv("DEEPSEEK_MODEL", "deepseek/deepseek-r1-0528")


config = LLMConfig()


def _post_chat_completion(
    base_url: str,
    api_key: str,
    model: str,
    messages: list,
    extra: Optional[dict] = None,
) -> str:
    if not api_key:
        raise RuntimeError("API key not configured for LLM client.")

    payload = {
        "model": model,
        "messages": messages,
    }
    if extra:
        payload.update(extra)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    # RouterAI (и прочие OpenAI‑совместимые сервисы) используют endpoint
    # вида: <base_url>/chat/completions
    url = base_url.rstrip("/") + "/chat/completions"

    resp = requests.post(url, json=payload, headers=headers, timeout=300)
    resp.raise_for_status()
    data = resp.json()

    # OpenAI-совместимый формат
    try:
        return data["choices"][0]["message"]["content"]
    except Exception as e:  # pragma: no cover - защитный код
        raise RuntimeError(f"Unexpected LLM response format: {data}") from e


def call_qwen_with_images(prompt: str, image_paths: List[str]) -> str:
    """
    Вызов Qwen для мульти-модального анализа слайдов.

    ВНИМАНИЕ: конкретный формат передачи изображений (base64 / URL / form-data)
    зависит от выбранного API. Здесь используется упрощённый вариант:
    мы передаём список локальных путей в system-сообщении. Вам нужно
    адаптировать реализацию под ваш реальный endpoint.
    """
    system_msg = {
        "role": "system",
        "content": "Ты анализируешь презентацию по изображениям слайдов. "
                   "Ниже тебе переданы локальные пути к файлам слайдов. "
                   "Ориентируйся на текстовый промпт пользователя.",
    }
    user_msg = {
        "role": "user",
        "content": f"{prompt}\n\nСписок файлов слайдов:\n" + "\n".join(image_paths),
    }

    return _post_chat_completion(
        base_url=config.qwen_api_base,
        api_key=config.qwen_api_key,
        model=config.qwen_model,
        messages=[system_msg, user_msg],
    )


def call_deepseek(prompt: str) -> str:
    """
    Вызов DeepSeek по текстовому промпту.
    """
    user_msg = {"role": "user", "content": prompt}
    return _post_chat_completion(
        base_url=config.deepseek_api_base,
        api_key=config.deepseek_api_key,
        model=config.deepseek_model,
        messages=[user_msg],
    )


def call_deepseek_querygen(prompt: str) -> str:
    """
    Вызов DeepSeek для генерации Tavily-запросов (по умолчанию может быть другой моделью).
    """
    user_msg = {"role": "user", "content": prompt}
    return _post_chat_completion(
        base_url=config.deepseek_api_base,
        api_key=config.deepseek_api_key,
        model=config.deepseek_querygen_model,
        messages=[user_msg],
    )