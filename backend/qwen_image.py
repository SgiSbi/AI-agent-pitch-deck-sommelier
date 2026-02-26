import base64
from pathlib import Path

import requests

from .llm_clients import config


def analyze_image_with_qwen(image_path: Path, question: str = "Что изображено на этой картинке?") -> str:
    """
    Отправляет одно изображение в Qwen (через RouterAI), используя формат messages
    с типами content: text + image_url (data URL).
    """
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    with image_path.open("rb") as f:
        b64 = base64.b64encode(f.read()).decode("ascii")

    data_url = f"data:image/png;base64,{b64}"

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": question,
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": data_url,
                    },
                },
            ],
        }
    ]

    payload = {
        "model": config.qwen_model,
        "messages": messages,
    }

    headers = {
        "Authorization": f"Bearer {config.qwen_api_key}",
        "Content-Type": "application/json",
    }

    url = config.qwen_api_base.rstrip("/") + "/chat/completions"
    resp = requests.post(url, json=payload, headers=headers, timeout=300)
    resp.raise_for_status()

    data = resp.json()
    try:
        return data["choices"][0]["message"]["content"]
    except Exception as e:
        raise RuntimeError(f"Unexpected Qwen image response format: {data}") from e

