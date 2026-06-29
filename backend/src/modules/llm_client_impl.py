from __future__ import annotations

import os
import base64
import json
import time
import concurrent.futures
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from requests.exceptions import ConnectionError as RequestsConnectionError, Timeout, HTTPError
from dotenv import load_dotenv

from .interfaces import ILLMClient
from .logging_impl import default_logger


class LLMConnectionError(RuntimeError):
    """Ошибка соединения с LLM-провайдером (routerai и т.п.)."""


# .env.backend лежит в директории backend, на уровень выше src
load_dotenv(Path(__file__).resolve().parents[1] / ".env.backend")


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
    deepseek_querygen_model: str = os.getenv("DEEPSEEK_QUERYGEN_MODEL", "")


config = LLMConfig()
QWEN_MAX_RETRIES = 3
QWEN_RETRY_DELAY_SECONDS = 10


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

    url = base_url.rstrip("/") + "/chat/completions"

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=300)
        resp.raise_for_status()
    except (RequestsConnectionError, Timeout) as e:
        raise LLMConnectionError(f"Нет соединения с LLM-провайдером ({url}): {e}") from e
    except HTTPError as e:
        raise LLMConnectionError(f"LLM-провайдер вернул ошибку {e.response.status_code}: {e}") from e

    data = resp.json()

    try:
        return data["choices"][0]["message"]["content"]
    except Exception as e:  # pragma: no cover - защитный код
        raise RuntimeError(f"Unexpected LLM response format: {data}") from e


class DefaultLLMClient(ILLMClient):
    """
    Полная реализация ILLMClient на базе перенесённой логики из llm_clients.py и qwen_image.py.
    """

    def _post_qwen_with_retries(self, payload: dict, timeout: int = 300) -> dict:
        """
        Унифицированный HTTP-вызов Qwen с ретраями:
        до 3 попыток, пауза 10 секунд между попытками.
        """
        headers = {
            "Authorization": f"Bearer {config.qwen_api_key}",
            "Content-Type": "application/json",
        }
        url = config.qwen_api_base.rstrip("/") + "/chat/completions"
        last_err: Exception | None = None

        for attempt in range(1, QWEN_MAX_RETRIES + 1):
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
                resp.raise_for_status()
                return resp.json()
            except Exception as e:
                last_err = e
                default_logger.log(
                    "QWEN",
                    f"Request failed (attempt {attempt}/{QWEN_MAX_RETRIES}): {e}",
                )
                if attempt < QWEN_MAX_RETRIES:
                    time.sleep(QWEN_RETRY_DELAY_SECONDS)

        if isinstance(last_err, (RequestsConnectionError, Timeout)):
            raise LLMConnectionError(
                f"Нет соединения с Qwen-провайдером после {QWEN_MAX_RETRIES} попыток"
            ) from last_err
        if isinstance(last_err, HTTPError):
            status_code = getattr(last_err.response, "status_code", "unknown")
            raise LLMConnectionError(
                f"Qwen-провайдер вернул ошибку {status_code} после {QWEN_MAX_RETRIES} попыток"
            ) from last_err
        raise RuntimeError("Qwen request failed after retries") from last_err

    def call_qwen_with_images(self, prompt: str, image_paths: List[str]) -> str:
        """
        Вызов Qwen для мульти‑модального анализа слайдов.
        """
        system_msg = {
            "role": "system",
            "content": (
                "Ты анализируешь презентацию по изображениям слайдов. "
                "Ниже тебе переданы локальные пути к файлам слайдов. "
                "Ориентируйся на текстовый промпт пользователя."
            ),
        }
        user_msg = {
            "role": "user",
            "content": f"{prompt}\n\nСписок файлов слайдов:\n" + "\n".join(image_paths),
        }

        payload = {
            "model": config.qwen_model,
            "messages": [system_msg, user_msg],
        }
        data = self._post_qwen_with_retries(payload=payload, timeout=300)
        try:
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            raise RuntimeError(f"Unexpected Qwen response format: {data}") from e

    def call_deepseek(self, prompt: str) -> str:
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

    def call_deepseek_querygen(self, prompt: str) -> str:
        """
        Вызов DeepSeek для генерации Tavily‑запросов (может быть отдельной моделью).
        """
        user_msg = {"role": "user", "content": prompt}
        return _post_chat_completion(
            base_url=config.deepseek_api_base,
            api_key=config.deepseek_api_key,
            model=config.deepseek_querygen_model,
            messages=[user_msg],
        )

    def analyze_image(self, image_path: Path, question: str) -> str:
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

        data = self._post_qwen_with_retries(payload=payload, timeout=300)
        try:
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            raise RuntimeError(f"Unexpected Qwen image response format: {data}") from e

    # ------- DeepSeek low-level helper with retries -------

    def post_deepseek_with_retries(
        self,
        payload: dict,
        req_path: Path,
        resp_path: Path,
        prompt_name: str,
        component: str = "DEEPSEEK",
        max_retries: int = 3,
    ) -> dict:
        """
        Унифицированный вызов DeepSeek с ретраями.
        Полный перенос HTTP‑логики из pipeline/_modules.deepeek_common.
        """
        headers = {
            "Authorization": f"Bearer {config.deepseek_api_key}",
            "Content-Type": "application/json",
        }
        url = config.deepseek_api_base.rstrip("/") + "/chat/completions"

        req_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        default_logger.log(component, f"{prompt_name}: request saved to: {req_path}")

        last_err: Exception | None = None

        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=600)
                if not resp.ok:
                    default_logger.log(component, f"{prompt_name}: error status={resp.status_code} body={resp.text}")
                    if resp.status_code in (429,) or 500 <= resp.status_code <= 599:
                        if attempt < max_retries:
                            time.sleep(2 * attempt)
                            continue
                    resp.raise_for_status()

                resp_json = resp.json()
                resp_path.write_text(json.dumps(resp_json, ensure_ascii=False, indent=2), encoding="utf-8")
                default_logger.log(component, f"{prompt_name}: response saved to: {resp_path}")

                try:
                    choice = resp_json["choices"][0]
                    if isinstance(choice, Dict) and choice.get("error"):
                        raise RuntimeError(f"DeepSeek inner error: {choice['error']}")
                    content = choice["message"]["content"]
                    if not isinstance(content, str):
                        raise TypeError(f"DeepSeek content is not a string: {type(content)}")
                except Exception as e:
                    last_err = e
                    default_logger.log(
                        component,
                        f"{prompt_name}: unexpected response format (attempt {attempt}): {resp_json}",
                    )
                    if attempt < max_retries:
                        time.sleep(2 * attempt)
                        continue
                    raise

                return resp_json

            except Exception as e:
                last_err = e
                if attempt < max_retries:
                    time.sleep(2 * attempt)
                    continue
                break

        if isinstance(last_err, (RequestsConnectionError, Timeout)):
            raise LLMConnectionError(
                f"Нет соединения с LLM-провайдером после {max_retries} попыток"
            ) from last_err
        raise RuntimeError(f"DeepSeek request failed for '{prompt_name}' after retries") from last_err



    # ------- Новые методы интерфейса ILLMClient -------

    def extract_information_from_images(
        self, 
        image_paths: List[str], 
        presentation_dir: str,
        stats: Optional[Dict[str, int]] = None,
    ) -> str:
        """
        Извлечение текстовой информации из слайдов презентации через Qwen vision API.
        Каждый слайд отправляется отдельным запросом параллельно.
        """
        from .paths import load_prompt, QWEN_ROOT, TEXT_FROM_SLIDES_ROOT
        
        prompt_text = load_prompt("text_extraction.md")
        
        # Создание директорий для сохранения
        qwen_dir = QWEN_ROOT / presentation_dir
        qwen_dir.mkdir(parents=True, exist_ok=True)
        
        # Создание директории для финального текста
        text_from_slides_dir = TEXT_FROM_SLIDES_ROOT / presentation_dir
        text_from_slides_dir.mkdir(parents=True, exist_ok=True)
        
        default_logger.log("QWEN", f"Starting extraction for '{presentation_dir}' ({len(image_paths)} slides)")
        
        # Функция для обработки одного слайда
        def process_single_slide(img_path_str: str, slide_num: int) -> str:
            img_path = Path(img_path_str)
            if not img_path.exists():
                default_logger.log("QWEN", f"Warning: image not found: {img_path}")
                return f"Слайд #{slide_num}: Изображение не найдено - {img_path}"
            
            default_logger.log("QWEN", f"Processing slide {slide_num}/{len(image_paths)}: {img_path.name}")
            
            # Чтение изображения и конвертация в base64
            with img_path.open("rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            
            data_url = f"data:image/png;base64,{b64}"
            
            # Формирование запроса в соответствии с форматом Qwen
            # Qwen ожидает массив content с объектами type: "text" и type: "image_url"
            messages = [
                {
                    "role": "system",
                    "content": "Ты анализируешь презентацию по изображениям слайдов."
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt_text
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": data_url
                            }
                        }
                    ]
                }
            ]
            
            payload = {
                "model": config.qwen_model,
                "messages": messages,
            }
            
            # Сохранение отдельного запроса для каждого слайда
            req_path = qwen_dir / f"request_slide_{slide_num:03d}.json"
            payload_for_log = {
                "model": config.qwen_model,
                "messages": [
                    {
                        "role": "system",
                        "content": "Ты анализируешь презентацию по изображениям слайдов."
                    },
                    {
                        "role": "user",
                        "content": f"{prompt_text}\n\n[1 image in base64 format: {img_path.name}]"
                    }
                ]
            }
            req_path.write_text(json.dumps(payload_for_log, ensure_ascii=False, indent=2), encoding="utf-8")
            
            try:
                resp_json = self._post_qwen_with_retries(payload=payload, timeout=300)
                
                # Сохранение отдельного ответа для каждого слайда
                resp_path = qwen_dir / f"response_slide_{slide_num:03d}.json"
                resp_path.write_text(json.dumps(resp_json, ensure_ascii=False, indent=2), encoding="utf-8")
                default_logger.log("QWEN", f"Response saved to: {resp_path}")

                # Обновление статистики токенов
                if stats is not None:
                    usage = resp_json.get("usage", {})
                    stats["input_tokens"] = stats.get("input_tokens", 0) + int(usage.get("prompt_tokens", 0))
                    stats["output_tokens"] = stats.get("output_tokens", 0) + int(usage.get("completion_tokens", 0))

                content = resp_json["choices"][0]["message"]["content"]
                if not isinstance(content, str):
                    raise TypeError(f"Qwen content is not a string: {type(content)}")
                
                default_logger.log("QWEN", f"Slide {slide_num} processed ({len(content)} chars)")
                return content.strip()
                
            except Exception as e:
                default_logger.log("QWEN", f"Error processing slide {slide_num}: {e}")
                return f"Слайд #{slide_num}: Ошибка обработки - {str(e)}"
        
        # Параллельная обработка слайдов
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        all_responses = []
        
        with ThreadPoolExecutor(max_workers=max(1, len(image_paths))) as executor:
            # Создаем задачи для каждого слайда
            future_to_slide = {
                executor.submit(process_single_slide, img_path_str, i+1): i+1
                for i, img_path_str in enumerate(image_paths)
            }
            
            # Собираем результаты по мере завершения
            for future in as_completed(future_to_slide):
                slide_num = future_to_slide[future]
                try:
                    result = future.result()
                    all_responses.append((slide_num, result))
                except Exception as e:
                    default_logger.log("QWEN", f"Exception in slide {slide_num}: {e}")
                    all_responses.append((slide_num, f"Слайд #{slide_num}: Исключение - {str(e)}"))
        
        # Сортируем ответы по номеру слайда
        all_responses.sort(key=lambda x: x[0])
        
        # Собираем все ответы в единый текст
        combined_text = "\n\n".join(f"Слайд #{slide_num}:\n{content}" for slide_num, content in all_responses)
        
        # Сохраняем финальный текст в директорию text_from_slides
        final_text_path = text_from_slides_dir / "extracted_text.txt"
        final_text_path.write_text(combined_text, encoding="utf-8")
        default_logger.log("QWEN", f"Final text saved to: {final_text_path}")
        
        # Также сохраняем в qwen_dir для обратной совместимости
        old_resp_path = qwen_dir / "response.json"
        old_resp_path.write_text(json.dumps({
            "choices": [{"message": {"content": combined_text}}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0}
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        
        # Сохраняем отдельные результаты в json формате
        structured_results = {
            "slides": [
                {
                    "slide_number": slide_num,
                    "content": content
                }
                for slide_num, content in all_responses
            ]
        }
        
        structured_json_path = text_from_slides_dir / "structured_results.json"
        structured_json_path.write_text(json.dumps(structured_results, ensure_ascii=False, indent=2), encoding="utf-8")
        
        default_logger.log("QWEN", f"Extraction completed ({len(combined_text)} chars total, {len(image_paths)} slides)")
        return combined_text.strip()

    def generate_tavily_queries(
        self, 
        qwen_text: str, 
        presentation_dir: str,
        stats: Optional[Dict[str, int]] = None
    ) -> Dict[str, List[str]]:
        """
        Генерация поисковых запросов для Tavily по категориям.
        Перенос логики из generate_tavily_queries_stage.
        """
        from .paths import load_prompt, TAVILY_ROOT
        
        default_logger.log("TAVILY_QUERYGEN", f"Starting query generation for '{presentation_dir}'")
        
        try:
            prompt_text = load_prompt("additional_prompt_for_websearch.md")
        except Exception as e:
            default_logger.log("TAVILY_QUERYGEN", f"Failed to load prompt: {e}")
            return {}
        
        full_prompt = f"{prompt_text}\n\n---SLIDES START---\n{qwen_text}\n---SLIDES END---"
        
        # Создание директорий
        query_gen_dir = TAVILY_ROOT / "query_generation" / presentation_dir
        query_gen_dir.mkdir(parents=True, exist_ok=True)
        req_path = query_gen_dir / "request.json"
        resp_path = query_gen_dir / "response.json"
        
        default_logger.log("TAVILY_QUERYGEN", f"Sending request to DeepSeek for '{presentation_dir}'")
        
        payload = {
            "model": config.deepseek_querygen_model or config.deepseek_model,
            "messages": [{"role": "user", "content": full_prompt}],
        }
        
        # Сохранение запроса
        req_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        
        # HTTP вызов
        headers = {
            "Authorization": f"Bearer {config.deepseek_api_key}",
            "Content-Type": "application/json",
        }
        url = config.deepseek_api_base.rstrip("/") + "/chat/completions"
        
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=600)
            resp.raise_for_status()
            
            default_logger.log("TAVILY_QUERYGEN", f"Received response from DeepSeek (status: {resp.status_code})")
            
            resp_json = resp.json()
            
            # Сохранение ответа
            resp_path.write_text(json.dumps(resp_json, ensure_ascii=False, indent=2), encoding="utf-8")
            default_logger.log("TAVILY_QUERYGEN", f"Response saved to: {resp_path}")
            
            # Обновление статистики
            if stats is not None:
                usage = resp_json.get("usage", {})
                stats["input_tokens"] = stats.get("input_tokens", 0) + int(usage.get("prompt_tokens", 0))
                stats["output_tokens"] = stats.get("output_tokens", 0) + int(usage.get("completion_tokens", 0))
            
            content = resp_json["choices"][0]["message"]["content"]
            default_logger.log("TAVILY_QUERYGEN", f"Parsing text response ({len(content)} chars)")
            
            # Сохраним исходный текст для отладки
            debug_path = query_gen_dir / "raw_content.txt"
            debug_path.write_text(content, encoding="utf-8")
            
            # Парсинг текстового ответа в структуру
            queries_by_category = self._parse_tavily_queries_text(content)
            
            # Логирование результата парсинга для отладки
            default_logger.log("TAVILY_QUERYGEN", f"Parsed categories: {list(queries_by_category.keys())}")
            for cat, queries in queries_by_category.items():
                default_logger.log("TAVILY_QUERYGEN", f"  {cat}: {len(queries)} queries")
            
            if queries_by_category:
                default_logger.log("TAVILY_QUERYGEN", f"Generated queries for {len(queries_by_category)} categories")
            else:
                default_logger.log("TAVILY_QUERYGEN", "No queries generated")
            
            return queries_by_category
                
        except Exception as e:
            default_logger.log("TAVILY_QUERYGEN", f"Error generating queries: {e}")
            return {}

    def _normalize_tavily_category(self, raw: str) -> str:
        name = raw.strip()
        lower = name.lower()
        if name in ("Команда", "Team") or lower == "команда":
            return "Команда"
        if name in ("Рынок", "Market") or lower == "рынок":
            return "Рынок"
        if name in ("Конкуренция", "Competition") or lower == "конкуренция":
            return "Конкуренция"
        if name in ("Продукт", "Product") or lower == "продукт":
            return "Продукт"
        if "дополнительно" in lower or "юр" in lower:
            return "Команда (дополнительно)"
        if "редфлаг" in lower or "red flag" in lower:
            return "Редфлаги"
        if "трекшн" in lower or "traction" in lower:
            return "Трекшн"
        return name

    def _parse_tavily_queries_text(self, text: str) -> Dict[str, List[str]]:
        """
        Парсинг текстового ответа от DeepSeek в структуру запросов по категориям.

        Ожидаемый формат:
        Команда:
        - "запрос 1"
        - "запрос 2"

        Рынок:
        - "запрос 1"
        """
        queries_by_category: Dict[str, List[str]] = {}
        current_category: str | None = None

        for raw_line in text.strip().split("\n"):
            line = raw_line.strip()
            if not line:
                continue
            if line.startswith("```"):
                continue

            if line.endswith(":") and not line.startswith("- "):
                current_category = self._normalize_tavily_category(line[:-1])
                queries_by_category.setdefault(current_category, [])
                continue

            if not current_category:
                continue

            query: str | None = None
            if line.startswith("- ") or line.startswith("\\- "):
                query = line[2:].strip() if line.startswith("- ") else line[3:].strip()
            elif len(line) > 2 and line[0].isdigit() and line[1] in ".)":
                query = line[2:].strip()
            elif line.startswith("* "):
                query = line[2:].strip()

            if not query:
                continue

            if query.startswith('"') and query.endswith('"'):
                query = query[1:-1].strip()
            elif query.startswith("'") and query.endswith("'"):
                query = query[1:-1].strip()

            if query and query != "Информация отсутствует.":
                queries_by_category[current_category].append(query)

        return queries_by_category

    def run_section(
        self,
        prompt_filename: str,
        qwen_text: str,
        presentation_dir: str,
        search_results: Optional[str] = None,
        stats: Optional[Dict[str, int]] = None
    ) -> str:
        """
        Отправка одной секции в DeepSeek с опциональными результатами поиска.
        Централизация HTTP логики из send_section_to_deepseek.
        """
        from .paths import load_prompt, DEEPSEEK_ROOT, REPORT_LOG_ROOT
        
        base_prompt = load_prompt(prompt_filename)
        prompt_stem = Path(prompt_filename).stem
        prompt_name = prompt_stem.replace("_prompt", "")
        
        # Формирование полного промпта
        web_search_block = search_results if search_results else ""
        full_prompt = (
            f"{base_prompt.strip()}\n\n"
            f"{web_search_block}"
            f"---SLIDES START---\n{qwen_text.strip()}\n---SLIDES END---"
        )
        
        # Подготовка путей
        base_dir = DEEPSEEK_ROOT / prompt_name
        req_dir = base_dir / "requests"
        resp_dir = base_dir / "responses"
        req_dir.mkdir(parents=True, exist_ok=True)
        resp_dir.mkdir(parents=True, exist_ok=True)
        
        payload = {
            "model": config.deepseek_model,
            "messages": [{"role": "user", "content": full_prompt}],
        }
        
        req_path = req_dir / f"{presentation_dir}.json"
        resp_path = resp_dir / f"{presentation_dir}.json"
        
        # HTTP запрос с ретраями
        resp_json = self.post_deepseek_with_retries(
            payload=payload,
            req_path=req_path,
            resp_path=resp_path,
            prompt_name=prompt_name,
            component="DEEPSEEK"
        )

        # Обновление статистики токенов
        if stats is not None:
            usage = resp_json.get("usage", {})
            stats["input_tokens"] = stats.get("input_tokens", 0) + int(usage.get("prompt_tokens", 0))
            stats["output_tokens"] = stats.get("output_tokens", 0) + int(usage.get("completion_tokens", 0))

        content = resp_json["choices"][0]["message"]["content"]

        # Сохранение лога секции
        self._save_section_log(
            presentation_dir=presentation_dir,
            prompt_name=prompt_name,
            req_path=req_path,
            resp_path=resp_path,
            content_length=len(content),
            search_results_used=bool(search_results)
        )
        
        return content.strip()

    def run_sections(
        self, 
        qwen_text: str,
        presentation_dir: str,
        tavily_queries_by_category: Optional[Dict[str, List[str]]] = None,
        stats: Optional[Dict[str, int]] = None
    ) -> Tuple[List[str], str]:
        """
        Параллельный запуск секций 1-5 в DeepSeek с интеграцией Tavily поиска.
        Перенос логики из run_deepseek_sections.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        section_prompts_files = [
            "1_info_from_pdf_prompt.md",
            "2_market_analyze_prompt.md",
            "3_competitors_analyze_prompt.md",
            "4_product_analyze_prompt.md",
            "5_team_analyze_prompt.md",
        ]
        
        md_parts: List[str] = [""] * len(section_prompts_files)
        
        # Логирование для отладки
        default_logger.log("PIPELINE_DEBUG", f"Starting sections for '{presentation_dir}'")
        default_logger.log("PIPELINE_DEBUG", f"tavily_queries_by_category is None: {tavily_queries_by_category is None}")
        if tavily_queries_by_category:
            default_logger.log("PIPELINE_DEBUG", f"Categories: {list(tavily_queries_by_category.keys())}")
            for cat, queries in tavily_queries_by_category.items():
                default_logger.log("PIPELINE_DEBUG", f"  {cat}: {len(queries)} queries")
        
        with ThreadPoolExecutor(max_workers=len(section_prompts_files)) as executor:
            future_to_idx = {}
            
            for i, prompt_filename in enumerate(section_prompts_files):
                # Интеграция Tavily поиска для каждой секции
                search_results = self._integrate_tavily_search(
                    prompt_filename=prompt_filename,
                    qwen_text=qwen_text,
                    tavily_queries_by_category=tavily_queries_by_category,
                    presentation_dir=presentation_dir,
                    stats=stats
                )
                
                future = executor.submit(
                    self.run_section,
                    prompt_filename,
                    qwen_text,
                    presentation_dir,
                    search_results,
                    stats
                )
                future_to_idx[future] = i
            
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    section_text = future.result()
                    md_parts[idx] = section_text
                    default_logger.log("PIPELINE", f"Section {idx + 1}/5 completed")
                except Exception as e:
                    default_logger.log("PIPELINE", f"Section {idx + 1}/5 failed: {e}")
                    raise
        
        intermediate_md = "\n\n\n".join(md_parts)
        return md_parts, intermediate_md

    def run_final_verdict(
        self, 
        intermediate_md: str, 
        presentation_dir: str,
        stats: Optional[Dict[str, int]] = None
    ) -> str:
        """
        Финальный вердикт (секция 6) на основе всех предыдущих секций.
        Перенос логики из run_final_verdict в deepseek_stages.
        """
        from .paths import load_prompt, DEEPSEEK_ROOT
        
        final_prompt_base = load_prompt("6_final_verdict_prompt.md")
        final_full_prompt = (
            f"{final_prompt_base.strip()}\n\n"
            f"---REPORTS START---\n{intermediate_md}\n---REPORTS END---"
        )
        
        prompt_name = "final_verdict"
        base_dir = DEEPSEEK_ROOT / prompt_name
        req_dir = base_dir / "requests"
        resp_dir = base_dir / "responses"
        req_dir.mkdir(parents=True, exist_ok=True)
        resp_dir.mkdir(parents=True, exist_ok=True)
        
        payload = {
            "model": config.deepseek_model,
            "messages": [{"role": "user", "content": final_full_prompt}],
        }
        
        default_logger.log("PIPELINE", f"Starting final verdict (section 6) for '{presentation_dir}'")
        req_path = req_dir / f"{presentation_dir}.json"
        resp_path = resp_dir / f"{presentation_dir}.json"
        
        resp_json = self.post_deepseek_with_retries(
            payload=payload,
            req_path=req_path,
            resp_path=resp_path,
            prompt_name=prompt_name,
            component="DEEPSEEK"
        )
        
        # Обновление статистики
        if stats is not None:
            usage = resp_json.get("usage", {})
            stats["input_tokens"] = stats.get("input_tokens", 0) + int(usage.get("prompt_tokens", 0))
            stats["output_tokens"] = stats.get("output_tokens", 0) + int(usage.get("completion_tokens", 0))
        
        content = resp_json["choices"][0]["message"]["content"]
        
        default_logger.log("PIPELINE", f"Final verdict generated for '{presentation_dir}' ({len(content)} chars)")
        
        # Сохранение лога
        self._save_section_log(
            presentation_dir=presentation_dir,
            prompt_name=prompt_name,
            req_path=req_path,
            resp_path=resp_path,
            content_length=len(content),
            search_results_used=False
        )
        
        return content.strip()

    # ------- Вспомогательные приватные методы -------

    def _integrate_tavily_search(
        self,
        prompt_filename: str,
        qwen_text: str,
        tavily_queries_by_category: Optional[Dict[str, List[str]]],
        presentation_dir: str,
        stats: Optional[Dict[str, int]] = None
    ) -> Optional[str]:
        """
        Интеграция Tavily поиска для секции.
        Возвращает форматированный блок с результатами поиска или None.
        """
        from .paths import TAVILY_ROOT
        from .search_client_impl import TavilySearchClient
        
        prompt_stem = Path(prompt_filename).stem
        prompt_name = prompt_stem.replace("_prompt", "")
        
        # Маппинг категорий для каждой секции
        category_map: Dict[str, List[str]] = {
            "1_info_from_pdf": ["Команда", "Команда (дополнительно)"],
            "2_market_analyze": ["Рынок", "Конкуренция"],
            "3_competitors_analyze": ["Конкуренция"],
            "4_product_analyze": ["Продукт"],
            "5_team_analyze": ["Команда", "Команда (дополнительно)"],
        }
        
        if prompt_name not in category_map:
            default_logger.log("TAVILY_DEBUG", f"prompt_name '{prompt_name}' not in category_map")
            return None
        
        if not tavily_queries_by_category:
            default_logger.log("TAVILY_DEBUG", f"tavily_queries_by_category is empty or None for '{prompt_name}'")
            return None
        
        selected_categories = category_map[prompt_name][:]
        
        # Добавление глобальных категорий
        for global_cat in ("Редфлаги", "Трекшн"):
            if global_cat in tavily_queries_by_category and global_cat not in selected_categories:
                selected_categories.append(global_cat)
        
        # Логирование выбранных категорий
        default_logger.log("TAVILY_DEBUG", f"selected_categories for '{prompt_name}': {selected_categories}")
        
        # Сбор уникальных запросов
        queries: List[str] = []
        seen: set[str] = set()
        
        for cat in selected_categories:
            cat_queries = tavily_queries_by_category.get(cat, [])
            default_logger.log("TAVILY_DEBUG", f"  category '{cat}' has {len(cat_queries)} queries")
            for q in cat_queries:
                qq = (q or "").strip()
                if qq and qq not in seen:
                    seen.add(qq)
                    queries.append(qq)
        
        # Ограничение до 8 запросов
        queries = queries[:8]
        default_logger.log("TAVILY_DEBUG", f"Collected {len(queries)} unique queries for '{prompt_name}': {queries}")
        
        if not queries:
            default_logger.log("TAVILY_DEBUG", f"No queries collected for '{prompt_name}'")
            return None
        
        # Создание директорий
        tavily_dir = TAVILY_ROOT / prompt_name / presentation_dir
        tavily_dir.mkdir(parents=True, exist_ok=True)
        tavily_queries_path = tavily_dir / "queries.json"
        tavily_results_text_path = tavily_dir / "results_text.txt"
        tavily_results_path = tavily_dir / "results.json"
        
        default_logger.log("PIPELINE", f"Tavily search start for '{presentation_dir}' section '{prompt_name}'")
        tavily_queries_path.write_text(json.dumps(queries, ensure_ascii=False, indent=2), encoding="utf-8")
        
        if stats is not None:
            stats["tavily_requests"] = stats.get("tavily_requests", 0) + len(queries)
        
        # Выполнение поиска
        log_fn = lambda msg: default_logger.log(f"TAVILY:{prompt_name}", msg)
        client = TavilySearchClient()
        search_results, raw_responses = client._search_internal(  # type: ignore[attr-defined]
            queries,
            max_results_per_query=5,
            log_fn=log_fn,
            return_raw=True,
        )
        
        if not search_results:
            default_logger.log(
                f"TAVILY:{prompt_name}",
                "No search results from Tavily (empty response or API error) — aborting pipeline",
            )
            raise RuntimeError(
                f"Tavily search returned no results for '{presentation_dir}' in section '{prompt_name}'"
            )
        
        # Сохранение результатов
        tavily_results_text_path.write_text(search_results, encoding="utf-8")
        results_payload = {
            "queries": queries,
            "results_char_count": len(search_results),
            "results_preview": search_results[:3000] + ("..." if len(search_results) > 3000 else ""),
            "raw_responses_count": len(raw_responses),
        }
        tavily_results_path.write_text(json.dumps(results_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        
        tavily_raw_path = tavily_dir / "tavily_raw.json"
        tavily_raw_path.write_text(json.dumps(raw_responses, ensure_ascii=False, indent=2), encoding="utf-8")
        
        default_logger.log("PIPELINE", f"Tavily search OK for section '{prompt_name}', {len(search_results)} chars")
        
        # Форматирование для промпта
        formatted_results = (
            "\n\n---WEB-SEARCH-INFORMATION START---\n"
            "Ниже приведены результаты независимого веб-поиска (фрагменты + URL источника). Используй их для валидации "
            "утверждений из слайдов. В разделе со ссылками укажи ТОЛЬКО URL, фактически использованные в анализе.\n\n"
            f"{search_results}\n\n"
            "---WEB-SEARCH-INFORMATION END---\n\n"
        )
        
        return formatted_results



    def _save_section_log(
        self,
        presentation_dir: str,
        prompt_name: str,
        req_path: Path,
        resp_path: Path,
        content_length: int,
        search_results_used: bool = False
    ) -> None:
        """Сохранение лога секции."""
        from .paths import REPORT_LOG_ROOT
        
        try:
            section_log_dir = REPORT_LOG_ROOT / presentation_dir / "sections"
            section_log_dir.mkdir(parents=True, exist_ok=True)
            section_log_path = section_log_dir / f"{prompt_name}.json"
            
            payload_log = {
                "presentation_dir": presentation_dir,
                "prompt_name": prompt_name,
                "deepseek": {
                    "request_path": str(req_path),
                    "response_path": str(resp_path),
                    "response_char_count": content_length,
                },
            }
            
            if search_results_used:
                payload_log["tavily_used"] = True
            
            section_log_path.write_text(json.dumps(payload_log, ensure_ascii=False, indent=2), encoding="utf-8")
            default_logger.log("REPORTLOG", f"Section log saved: {section_log_path}")
        except Exception as e:
            default_logger.log("REPORTLOG", f"Failed to write section log for '{prompt_name}': {e}")
