from __future__ import annotations

import os
import base64
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

from .interfaces import ILLMClient
from .logging_impl import default_logger


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

    resp = requests.post(url, json=payload, headers=headers, timeout=300)
    resp.raise_for_status()
    data = resp.json()

    try:
        return data["choices"][0]["message"]["content"]
    except Exception as e:  # pragma: no cover - защитный код
        raise RuntimeError(f"Unexpected LLM response format: {data}") from e


class DefaultLLMClient(ILLMClient):
    """
    Полная реализация ILLMClient на базе перенесённой логики из llm_clients.py и qwen_image.py.
    """

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

        return _post_chat_completion(
            base_url=config.qwen_api_base,
            api_key=config.qwen_api_key,
            model=config.qwen_model,
            messages=[system_msg, user_msg],
        )

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

        raise RuntimeError(f"DeepSeek request failed for '{prompt_name}' after retries") from last_err



    # ------- Новые методы интерфейса ILLMClient -------

    def extract_information_from_images(
        self, 
        image_paths: List[str], 
        presentation_dir: str
    ) -> str:
        """
        Извлечение текстовой информации из слайдов презентации через Qwen vision API.
        Перенос логики из qwen_from_slides_stage.
        """
        from .paths import load_prompt, QWEN_ROOT
        
        prompt_text = load_prompt("text_extraction.md")
        
        # Создание директорий для сохранения
        qwen_dir = QWEN_ROOT / presentation_dir
        qwen_dir.mkdir(parents=True, exist_ok=True)
        req_path = qwen_dir / "request.json"
        resp_path = qwen_dir / "response.json"
        
        default_logger.log("QWEN", f"Starting extraction for '{presentation_dir}' ({len(image_paths)} slides)")
        
        # Формирование content с изображениями в base64
        content_parts = [{"type": "text", "text": prompt_text}]
        
        for img_path_str in image_paths:
            img_path = Path(img_path_str)
            if not img_path.exists():
                default_logger.log("QWEN", f"Warning: image not found: {img_path}")
                continue
            
            with img_path.open("rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            
            data_url = f"data:image/png;base64,{b64}"
            content_parts.append({
                "type": "image_url",
                "image_url": {"url": data_url}
            })
        
        messages = [
            {
                "role": "system",
                "content": "Ты анализируешь презентацию по изображениям слайдов."
            },
            {
                "role": "user",
                "content": content_parts
            }
        ]
        
        payload = {
            "model": config.qwen_model,
            "messages": messages,
        }
        
        # Сохранение запроса (без base64 для читаемости)
        payload_for_log = {
            "model": config.qwen_model,
            "messages": [
                {
                    "role": "system",
                    "content": "Ты анализируешь презентацию по изображениям слайдов."
                },
                {
                    "role": "user",
                    "content": f"{prompt_text}\n\n[{len(image_paths)} images in base64 format]"
                }
            ]
        }
        req_path.write_text(json.dumps(payload_for_log, ensure_ascii=False, indent=2), encoding="utf-8")
        default_logger.log("QWEN", f"Request saved to: {req_path}")
        
        # HTTP вызов
        headers = {
            "Authorization": f"Bearer {config.qwen_api_key}",
            "Content-Type": "application/json",
        }
        url = config.qwen_api_base.rstrip("/") + "/chat/completions"
        
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=600)
            resp.raise_for_status()
            resp_json = resp.json()
            
            # Сохранение ответа
            resp_path.write_text(json.dumps(resp_json, ensure_ascii=False, indent=2), encoding="utf-8")
            default_logger.log("QWEN", f"Response saved to: {resp_path}")
            
            content = resp_json["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise TypeError(f"Qwen content is not a string: {type(content)}")
            
            default_logger.log("QWEN", f"Extraction completed ({len(content)} chars)")
            return content.strip()
            
        except Exception as e:
            default_logger.log("QWEN", f"Error during extraction: {e}")
            raise RuntimeError(f"Failed to extract information from images: {e}") from e

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
            
            # Парсинг текстового ответа в структуру
            queries_by_category = self._parse_tavily_queries_text(content)
            
            if queries_by_category:
                default_logger.log("TAVILY_QUERYGEN", f"Generated queries for {len(queries_by_category)} categories")
            else:
                default_logger.log("TAVILY_QUERYGEN", "No queries generated")
            
            return queries_by_category
                
        except Exception as e:
            default_logger.log("TAVILY_QUERYGEN", f"Error generating queries: {e}")
            return {}

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
        current_category = None
        
        lines = text.strip().split('\n')
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Проверка на категорию (заканчивается на ':')
            if line.endswith(':'):
                category_name = line[:-1].strip()
                # Нормализация названий категорий
                if category_name in ("Команда", "Team"):
                    current_category = "Команда"
                elif category_name in ("Рынок", "Market"):
                    current_category = "Рынок"
                elif category_name in ("Конкуренция", "Competition"):
                    current_category = "Конкуренция"
                elif category_name in ("Продукт", "Product"):
                    current_category = "Продукт"
                elif category_name in ("Команда (дополнительно)", "Team (additional)"):
                    current_category = "Команда (дополнительно)"
                elif "Редфлаг" in category_name or "Red flag" in category_name:
                    current_category = "Редфлаги"
                elif "Трекшн" in category_name or "Traction" in category_name:
                    current_category = "Трекшн"
                else:
                    current_category = category_name
                
                if current_category not in queries_by_category:
                    queries_by_category[current_category] = []
            
            # Проверка на запрос (начинается с '- ')
            elif line.startswith('- ') and current_category:
                query = line[2:].strip()
                # Убираем кавычки если есть
                if query.startswith('"') and query.endswith('"'):
                    query = query[1:-1]
                elif query.startswith("'") and query.endswith("'"):
                    query = query[1:-1]
                
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
            return None
        
        if not tavily_queries_by_category:
            return None
        
        selected_categories = category_map[prompt_name][:]
        
        # Добавление глобальных категорий
        for global_cat in ("Редфлаги", "Трекшн"):
            if global_cat in tavily_queries_by_category and global_cat not in selected_categories:
                selected_categories.append(global_cat)
        
        # Сбор уникальных запросов
        queries: List[str] = []
        seen: set[str] = set()
        
        for cat in selected_categories:
            for q in tavily_queries_by_category.get(cat, []):
                qq = (q or "").strip()
                if qq and qq not in seen:
                    seen.add(qq)
                    queries.append(qq)
        
        # Ограничение до 8 запросов
        queries = queries[:8]
        
        if not queries:
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
            stats["tavily_requests"] = stats.get("tavily_requests", 0) + 1
        
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
