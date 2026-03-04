import base64
import json
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Tuple
import time

import requests

from .llm_clients import config
from .tavily_client import search_web
from .test import pdf_to_images
from .formatting import convert_md_to_docx


BASE_DIR = Path(__file__).resolve().parents[1]
PROMPTS_DIR = BASE_DIR / "promts"
TMP_DIR = BASE_DIR / "tmp"
RESULT_DIR = BASE_DIR / "reports"

RAW_PRESENTATIONS_ROOT = TMP_DIR / "raw_presentations"
SLIDES_ROOT = TMP_DIR / "slides"
TEXT_FROM_SLIDES_ROOT = TMP_DIR / "text_from_slides"
QWEN_REQUESTS_DIR = TMP_DIR / "qwen" / "requests"
QWEN_RESPONSES_DIR = TMP_DIR / "qwen" / "responses"
DEEPSEEK_ROOT = TMP_DIR / "deepseek"
TAVILY_ROOT = TMP_DIR / "tavily"
REPORT_LOG_ROOT = TMP_DIR / "report_logs"


def _ts() -> str:
    """Текущее время в GMT+7 в удобном формате."""
    return datetime.now(timezone(timedelta(hours=7))).strftime("%d-%m-%Y %H:%M:%S")


def _log(component: str, message: str) -> None:
    print(f"[{_ts()}] [{component}] {message}")


def _load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8")


def _ensure_dirs() -> None:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_PRESENTATIONS_ROOT.mkdir(parents=True, exist_ok=True)
    SLIDES_ROOT.mkdir(parents=True, exist_ok=True)
    TEXT_FROM_SLIDES_ROOT.mkdir(parents=True, exist_ok=True)
    QWEN_REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    QWEN_RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    DEEPSEEK_ROOT.mkdir(parents=True, exist_ok=True)
    TAVILY_ROOT.mkdir(parents=True, exist_ok=True)
    (TAVILY_ROOT / "query_generation").mkdir(parents=True, exist_ok=True)
    REPORT_LOG_ROOT.mkdir(parents=True, exist_ok=True)


def _post_deepseek(
    payload: dict,
    req_path: Path,
    resp_path: Path,
    prompt_name: str,
    component: str = "DEEPSEEK",
    max_retries: int = 3,
) -> dict:
    """
    Унифицированный вызов DeepSeek с ретраями:
    - повторяет запрос при HTTP 5xx/429;
    - повторяет при формате ответа с error или content=None.
    """
    headers = {
        "Authorization": f"Bearer {config.deepseek_api_key}",
        "Content-Type": "application/json",
    }
    url = config.deepseek_api_base.rstrip("/") + "/chat/completions"

    # Сохраняем запрос (один раз, до ретраев)
    req_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(component, f"{prompt_name}: request saved to: {req_path}")

    last_err: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=600)
            if not resp.ok:
                _log(component, f"{prompt_name}: error status={resp.status_code} body={resp.text}")
                if resp.status_code in (429,) or 500 <= resp.status_code <= 599:
                    if attempt < max_retries:
                        time.sleep(2 * attempt)
                        continue
                resp.raise_for_status()

            resp_json = resp.json()
            resp_path.write_text(json.dumps(resp_json, ensure_ascii=False, indent=2), encoding="utf-8")
            _log(component, f"{prompt_name}: response saved to: {resp_path}")

            # Проверяем формат: отсутствие error и строковый content
            try:
                choice = resp_json["choices"][0]
                # Если провайдер вернул ошибку внутри choices
                if isinstance(choice, dict) and choice.get("error"):
                    raise RuntimeError(f"DeepSeek inner error: {choice['error']}")
                content = choice["message"]["content"]
                if not isinstance(content, str):
                    raise TypeError(f"DeepSeek content is not a string: {type(content)}")
            except Exception as e:
                last_err = e
                _log(component, f"{prompt_name}: unexpected response format (attempt {attempt}): {resp_json}")
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


def _parse_tavily_query_plan(text: str) -> Dict[str, List[str]]:
    """
    Парсит вывод `additional_prompt_for_websearch.md` в структуру:
      { "<Категория>": ["запрос 1", "запрос 2", ...], ... }

    Ожидаемый формат:
    Категория:
    - "запрос 1"
    - "запрос 2"
    """
    result: Dict[str, List[str]] = {}
    current: str | None = None

    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue

        # Категория: "Команда:" / "Рынок:" и т.п.
        if line.endswith(":") and not line.startswith("-") and not line.startswith("\\-"):
            current = line[:-1].strip()
            if current:
                result.setdefault(current, [])
            continue

        if current is None:
            continue

        if line == "Информация отсутствует.":
            # Явно обозначенная пустота — оставляем категорию пустой
            result[current] = []
            continue

        # Буллеты могут приходить как "- " или "\- " (markdown-escape).
        if line.startswith("\\-"):
            line = line[1:].lstrip()

        if line.startswith("-"):
            q = line.lstrip("-").strip()
            # Обычно запрос в кавычках: "...."
            if len(q) >= 2 and q[0] == '"' and q[-1] == '"':
                q = q[1:-1].strip()
            if q:
                result.setdefault(current, []).append(q)
            continue

        # Спец-строка из Appendix: URL для ручной проверки: ...
        if line.lower().startswith("url для ручной проверки:"):
            urls = line.split(":", 1)[-1].strip()
            if urls:
                result.setdefault("Appendix_urls", []).append(urls)

    return result


def generate_tavily_queries_stage(qwen_text: str, presentation_dir: str) -> Dict[str, List[str]]:
    """
    Этап 2.5. Генерация поисковых запросов для Tavily через LLM.

    Использует промпт `additional_prompt_for_websearch.md` и текст со слайдов.
    Сохраняет запрос/ответ и распарсенные категории в `backend/tmp/tavily/query_generation/...`.
    """
    base_prompt = _load_prompt("additional_prompt_for_websearch.md")
    full_prompt = (
        f"{base_prompt.strip()}\n\n"
        f"---SLIDES START---\n{qwen_text.strip()}\n---SLIDES END---"
    )

    gen_dir = TAVILY_ROOT / "query_generation" / presentation_dir
    req_dir = gen_dir / "requests"
    resp_dir = gen_dir / "responses"
    req_dir.mkdir(parents=True, exist_ok=True)
    resp_dir.mkdir(parents=True, exist_ok=True)

    req_path = req_dir / "request.json"
    resp_path = resp_dir / "response.json"
    parsed_path = gen_dir / "queries_by_category.json"
    raw_text_path = gen_dir / "query_plan.txt"

    payload = {
        "model": config.deepseek_querygen_model,
        "messages": [{"role": "user", "content": full_prompt}],
    }

    _log(
        "PIPELINE",
        f"Generating Tavily query plan for '{presentation_dir}' (model={config.deepseek_querygen_model})",
    )
    resp_json = _post_deepseek(
        payload=payload,
        req_path=req_path,
        resp_path=resp_path,
        prompt_name="tavily_query_plan",
        component="TAVILY:QUERYGEN",
    )

    try:
        content = resp_json["choices"][0]["message"]["content"]
    except Exception as e:
        _log("TAVILY:QUERYGEN", f"Unexpected response format: {resp_json}")
        raise RuntimeError("Unexpected query generation response format") from e

    raw_text_path.write_text(content, encoding="utf-8")
    _log("TAVILY:QUERYGEN", f"Query plan text saved to: {raw_text_path} ({len(content)} chars)")

    parsed = _parse_tavily_query_plan(content)
    parsed_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
    _log("TAVILY:QUERYGEN", f"Parsed categories saved to: {parsed_path} ({len(parsed)} categories)")

    return parsed


# === ЭТАП 1: извлечение слайдов ===

def pdf_to_slide_images(pdf_path: Path, slides_dir: Path) -> List[str]:
    """
    Низкоуровневая функция: конвертация PDF в изображения слайдов.
    """
    return pdf_to_images(
        pdf_path=str(pdf_path),
        output_folder=str(slides_dir),
        dpi=60,
        image_format="png",
    )


def extract_slides_stage(pdf_path: Path, presentation_dir: str) -> List[str]:
    """
    Этап 1. Извлечение изображений из PDF.

    - сохраняет слайды в TMP_DIR/slides/<presentation_dir>
    - пишет логи в консоль
    """
    slides_dir = SLIDES_ROOT / presentation_dir
    slides_dir.mkdir(parents=True, exist_ok=True)

    _log("SLIDES", f"Start processing PDF: {pdf_path}")
    _log("SLIDES", f"Target directory: {slides_dir}")

    try:
        image_paths = pdf_to_slide_images(pdf_path=pdf_path, slides_dir=slides_dir)
    except Exception as e:
        _log("SLIDES", f"Error while processing slides for '{pdf_path}': {e}")
        raise

    _log("SLIDES", "slide processing completed successfully")
    return image_paths


# === ЭТАП 2: Qwen по слайдам ===

def qwen_from_slides_stage(image_paths: List[str], presentation_dir: str) -> str:
    """
    Этап 2. Один запрос в Qwen: текст из text_extraction.md + по одному блоку image_url на каждый слайд.

    Структура запроса:
    messages = [
      {
        "role": "user",
        "content": [
          { "type": "text", "text": "<содержимое text_extraction.md>" },
          { "type": "image_url", "image_url": { "url": "data:image/png;base64,..." } },  # слайд 1
          { "type": "image_url", "image_url": { "url": "..." } },  # слайд 2
          ...
        ]
      }
    ]

    Сохраняет запрос/ответ в TMP_DIR/qwen_requests/<presentation_dir>.json и .../qwen_responses/...
    Текст ответа — в TMP_DIR/text_from_slides/<presentation_dir>/text_from_slides.txt
    """
    text_extraction_prompt = _load_prompt("text_extraction.md")

    def _post_qwen(payload: dict, req_path: Path, resp_path: Path) -> dict:
        """
        Выполняет запрос в Qwen с ретраями на 5xx/429.
        """
        headers = {
            "Authorization": f"Bearer {config.qwen_api_key}",
            "Content-Type": "application/json",
        }
        url = config.qwen_api_base.rstrip("/") + "/chat/completions"

        # сохраняем метаданные запроса (без base64)
        req_path.write_text(
            json.dumps(payload.get("_payload_for_log", payload), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        _log("REPORTLOG", f"Qwen request saved: {req_path}")

        last_err: Exception | None = None
        for attempt in range(1, 4):
            try:
                resp = requests.post(url, json=payload["_payload"], headers=headers, timeout=600)
                if resp.ok:
                    data = resp.json()
                    resp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                    _log("REPORTLOG", f"Qwen response saved: {resp_path}")
                    return data

                _log("REPORTLOG", f"Qwen error status={resp.status_code} body={resp.text}")
                # ретрай только для 429/5xx, иначе сразу падаем
                if resp.status_code in (429,) or 500 <= resp.status_code <= 599:
                    time.sleep(2 * attempt)
                    continue
                resp.raise_for_status()
            except Exception as e:
                last_err = e
                time.sleep(2 * attempt)

        raise RuntimeError("Qwen request failed after retries") from last_err

    req_dir = QWEN_REQUESTS_DIR / presentation_dir
    resp_dir = QWEN_RESPONSES_DIR / presentation_dir
    req_dir.mkdir(parents=True, exist_ok=True)
    resp_dir.mkdir(parents=True, exist_ok=True)

    # Если слайдов много — бьём на чанки, чтобы уменьшить payload
    chunk_size = 3 if len(image_paths) > 3 else len(image_paths)
    chunks: List[List[str]] = [image_paths[i : i + chunk_size] for i in range(0, len(image_paths), chunk_size)]

    chunk_texts_by_idx: Dict[int, str] = {}

    def _process_chunk(idx: int, chunk_paths: List[str]) -> None:
        # Первый элемент content — текст промпта
        content_items: list[dict] = [{"type": "text", "text": text_extraction_prompt.strip()}]

        # Кодируем каждый слайд в base64 и добавляем image_url
        for img_path in chunk_paths:
            try:
                with open(img_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode("ascii")
                data_url = f"data:image/png;base64,{b64}"
                content_items.append({"type": "image_url", "image_url": {"url": data_url}})
            except Exception as e:
                _log("REPORTLOG", f"Qwen: failed to encode image '{img_path}': {e}")

        # payload for API + payload for log (без base64)
        content_for_log: list[dict] = []
        for c in content_items:
            if c["type"] == "text":
                t = c["text"]
                content_for_log.append({"type": "text", "text": (t[:500] + "...") if len(t) > 500 else t})
            else:
                content_for_log.append({"type": "image_url", "image_url": {"url": "<data:image/png;base64,...>"}})

        payload_api = {"model": config.qwen_model, "messages": [{"role": "user", "content": content_items}]}
        payload_log = {"model": config.qwen_model, "messages": [{"role": "user", "content": content_for_log}]}
        payload_wrapper = {"_payload": payload_api, "_payload_for_log": payload_log}

        req_path = req_dir / f"chunk_{idx:02d}_request.json"
        resp_path = resp_dir / f"chunk_{idx:02d}_response.json"

        resp_json = _post_qwen(payload_wrapper, req_path=req_path, resp_path=resp_path)

        try:
            chunk_content = resp_json["choices"][0]["message"]["content"]
        except Exception as e:
            _log("REPORTLOG", f"Qwen: unexpected response format in chunk {idx}: {resp_json}")
            raise RuntimeError("Unexpected Qwen response format") from e

        chunk_texts_by_idx[idx] = chunk_content.strip()

    # Отправляем чанки параллельно
    with ThreadPoolExecutor(max_workers=len(chunks)) as executor:
        futures = [
            executor.submit(_process_chunk, idx, chunk_paths)
            for idx, chunk_paths in enumerate(chunks, 1)
        ]
        # Блокируемся до завершения всех, исключения поднимутся наружу
        for f in futures:
            f.result()

    chunk_texts: List[str] = [chunk_texts_by_idx[i] for i in sorted(chunk_texts_by_idx.keys())]

    full_content = "\n\n".join(chunk_texts).strip()

    text_dir = TEXT_FROM_SLIDES_ROOT / presentation_dir
    text_dir.mkdir(parents=True, exist_ok=True)
    text_file = text_dir / "text_from_slides.txt"
    text_file.write_text(full_content, encoding="utf-8")
    _log("REPORTLOG", f"Qwen text saved to: {text_file}")

    return full_content


# === ЭТАП 3: DeepSeek по отдельным модулям ===

def send_section_to_deepseek(
    prompt_filename: str,
    qwen_text: str,
    presentation_dir: str,
    tavily_queries_by_category: Dict[str, List[str]] | None = None,
) -> str:
    """
    Этап 3. Отправка одной секции в DeepSeek:
    - читает базовый промпт из файла
    - для промптов 1–5: выполняет веб-поиск через Tavily и добавляет блок WEB-SEARCH-INFORMATION
    - добавляет блок SLIDES с текстом от Qwen
    - сохраняет запрос и ответ в TMP_DIR/deepseek/<name_prompt>/{requests,responses}
    - возвращает текст ответа DeepSeek.
    """
    base_prompt = _load_prompt(prompt_filename)
    prompt_stem = Path(prompt_filename).stem  # например: "2_market_analyze_prompt"
    # Базовое имя без "_prompt" для маппинга категорий Tavily: "2_market_analyze"
    prompt_base = prompt_stem[:-7] if prompt_stem.endswith("_prompt") else prompt_stem
    prompt_name = prompt_base

    web_search_block = ""
    tavily_used = False
    tavily_queries: List[str] = []
    tavily_dir: Path | None = None
    tavily_queries_path: Path | None = None
    tavily_results_path: Path | None = None
    tavily_results_text_path: Path | None = None
    tavily_results_char_count = 0
    used_categories: List[str] = []

    if prompt_name in (
        "1_info_from_pdf",
        "2_market_analyze",
        "3_competitors_analyze",
        "4_product_analyze",
        "5_team_analyze",
    ):
        category_map: Dict[str, List[str]] = {
            # Актуальный промпт `additional_prompt_for_websearch.md` даёт категории:
            # Команда, Рынок, Конкуренция, Продукт, Команда (дополнительно)
            # Если в будущем промпт снова будет содержать "Редфлаги"/"Трекшн" — они будут подмешаны автоматически (см. ниже).
            "1_info_from_pdf": ["Команда", "Команда (дополнительно)"],
            "2_market_analyze": ["Рынок", "Конкуренция"],
            "3_competitors_analyze": ["Конкуренция"],
            "4_product_analyze": ["Продукт"],
            "5_team_analyze": ["Команда", "Команда (дополнительно)"],
        }

        selected_categories = category_map.get(prompt_name, [])
        # Глобальные категории, если они присутствуют в генерации запросов, прокидываем во ВСЕ промпты
        # (частый запрос: редфлаги/трекшн как общий контекст).
        if tavily_queries_by_category:
            for global_cat in ("Редфлаги", "Трекшн"):
                if global_cat in tavily_queries_by_category and global_cat not in selected_categories:
                    selected_categories.append(global_cat)
        used_categories = selected_categories[:]
        queries: List[str] = []
        if tavily_queries_by_category and selected_categories:
            seen: set[str] = set()
            for cat in selected_categories:
                for q in tavily_queries_by_category.get(cat, []):
                    qq = (q or "").strip()
                    if qq and qq not in seen:
                        seen.add(qq)
                        queries.append(qq)

        # Ограничим количество запросов, чтобы не сжигать кредиты Tavily
        queries = queries[:8]

        if queries:
            tavily_used = True
            tavily_queries = queries[:]
            # Для директорий используем базовое имя промпта (без "_prompt")
            tavily_dir = TAVILY_ROOT / prompt_name / presentation_dir
            tavily_dir.mkdir(parents=True, exist_ok=True)
            tavily_queries_path = tavily_dir / "queries.json"
            tavily_results_path = tavily_dir / "results.json"
            tavily_results_text_path = tavily_dir / "results_text.txt"

            _log("PIPELINE", f"Tavily search start for '{presentation_dir}' section '{prompt_name}'")
            tavily_queries_path.write_text(json.dumps(queries, ensure_ascii=False, indent=2), encoding="utf-8")

            log_fn = lambda msg: _log(f"TAVILY:{prompt_name}", msg)
            search_results, raw_responses = search_web(
                queries,
                max_results_per_query=5,
                log_fn=log_fn,
                return_raw=True,
            )

            if search_results:
                tavily_results_char_count = len(search_results)
                results_payload = {
                    "queries": queries,
                    "results_char_count": len(search_results),
                    "results_preview": search_results[:3000] + ("..." if len(search_results) > 3000 else ""),
                    "raw_responses_count": len(raw_responses),
                }
                tavily_results_path.write_text(json.dumps(results_payload, ensure_ascii=False, indent=2), encoding="utf-8")
                tavily_results_text_path.write_text(search_results, encoding="utf-8")
                # Полный сырой ответ Tavily (все запросы) для детального разбора
                tavily_raw_path = tavily_dir / "tavily_raw.json"
                tavily_raw_path.write_text(json.dumps(raw_responses, ensure_ascii=False, indent=2), encoding="utf-8")
                web_search_block = (
                    "\n\n---WEB-SEARCH-INFORMATION START---\n"
                    "Ниже приведены результаты независимого веб-поиска (фрагменты + URL источника). Используй их для валидации "
                    "утверждений из слайдов. В разделе со ссылками укажи ТОЛЬКО URL, фактически использованные в анализе.\n\n"
                    f"{search_results}\n\n"
                    "---WEB-SEARCH-INFORMATION END---\n\n"
                )
                _log("PIPELINE", f"Tavily search OK for section '{prompt_name}', {len(search_results)} chars")
            else:
                # Жёсткий режим: без данных от Tavily останавливаем весь пайплайн
                _log(
                    f"TAVILY:{prompt_name}",
                    "No search results from Tavily (empty response or API error) — aborting pipeline",
                )
                raise RuntimeError(
                    f"Tavily search returned no results for '{presentation_dir}' in section '{prompt_name}'"
                )

    full_prompt = (
        f"{base_prompt.strip()}\n\n"
        f"{web_search_block}"
        f"---SLIDES START---\n{qwen_text.strip()}\n---SLIDES END---"
    )

    base_dir = DEEPSEEK_ROOT / prompt_name
    req_dir = base_dir / "requests"
    resp_dir = base_dir / "responses"
    req_dir.mkdir(parents=True, exist_ok=True)
    resp_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "model": config.deepseek_model,
        "messages": [{"role": "user", "content": full_prompt}],
    }

    resp_json = _post_deepseek(
        payload=payload,
        req_path=req_dir / f"{presentation_dir}.json",
        resp_path=resp_dir / f"{presentation_dir}.json",
        prompt_name=prompt_name,
        component="DEEPSEEK",
    )

    try:
        content = resp_json["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            raise TypeError(f"DeepSeek content is not a string: {type(content)}")
    except Exception as e:
        _log("DEEPSEEK", f"{prompt_name}: unexpected response format: {resp_json}")
        raise RuntimeError("Unexpected DeepSeek response format") from e

    # Секционный лог (один файл на секцию, потокобезопасно)
    try:
        section_log_dir = REPORT_LOG_ROOT / presentation_dir / "sections"
        section_log_dir.mkdir(parents=True, exist_ok=True)
        section_log_path = section_log_dir / f"{prompt_name}.json"
        section_log_payload = {
            "presentation_dir": presentation_dir,
            "prompt_filename": prompt_filename,
            "prompt_name": prompt_name,
            "tavily": {
                "used": tavily_used,
                "used_categories": used_categories,
                "queries": tavily_queries,
                "dir": str(tavily_dir) if tavily_dir else None,
                "queries_path": str(tavily_queries_path) if tavily_queries_path else None,
                "results_path": str(tavily_results_path) if tavily_results_path else None,
                "results_text_path": str(tavily_results_text_path) if tavily_results_text_path else None,
                "results_char_count": tavily_results_char_count,
            },
            "deepseek": {
                "request_path": str(req_path),
                "response_path": str(resp_path),
                "response_char_count": len(content),
            },
        }
        section_log_path.write_text(json.dumps(section_log_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        _log("REPORTLOG", f"Section log saved: {section_log_path}")
    except Exception as e:
        _log("REPORTLOG", f"Failed to write section log for {prompt_name}: {e}")

    return content.strip()


def run_deepseek_sections(
    qwen_text: str,
    presentation_dir: str,
    tavily_queries_by_category: Dict[str, List[str]] | None = None,
) -> Tuple[List[str], str]:
    """
    Шаг 3. Пять запросов в DeepSeek по промптам 1-5 (параллельно).

    Возвращает кортеж:
    - список текстов по каждому разделу (порядок 1..5),
    - общий markdown по разделам 1-5 (intermediate_md).
    """
    section_prompts_files = [
        "1_info_from_pdf_prompt.md",
        "2_market_analyze_prompt.md",
        "3_competitors_analyze_prompt.md",
        "4_product_analyze_prompt.md",
        "5_team_analyze_prompt.md",
    ]

    md_parts: List[str] = [""] * len(section_prompts_files)

    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_idx = {
            executor.submit(
                send_section_to_deepseek,
                prompt_filename=filename,
                qwen_text=qwen_text,
                presentation_dir=presentation_dir,
                tavily_queries_by_category=tavily_queries_by_category,
            ): i
            for i, filename in enumerate(section_prompts_files)
        }
        for future in as_completed(future_to_idx):
            idx = future_to_idx[future]
            try:
                section_text = future.result()
                md_parts[idx] = section_text
                _log("PIPELINE", f"Section {idx + 1}/5 completed")
            except Exception as e:
                _log("PIPELINE", f"Section {idx + 1}/5 failed: {e}")
                raise

    intermediate_md = "\n\n\n".join(md_parts)
    return md_parts, intermediate_md


def run_final_verdict(intermediate_md: str, presentation_dir: str) -> str:
    """
    Шаг 4. Финальный запрос в DeepSeek по промпту 6 с добавлением всего markdown.
    """
    final_prompt_base = _load_prompt("6_final_verdict_prompt.md")
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

    _log("PIPELINE", f"Starting final verdict (section 6) for '{presentation_dir}'")
    resp_json = _post_deepseek(
        payload=payload,
        req_path=req_dir / f"{presentation_dir}.json",
        resp_path=resp_dir / f"{presentation_dir}.json",
        prompt_name=prompt_name,
        component="DEEPSEEK",
    )

    try:
        content = resp_json["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            raise TypeError(f"DeepSeek content is not a string: {type(content)}")
    except Exception as e:
        _log("DEEPSEEK", f"{prompt_name}: unexpected response format: {resp_json}")
        raise RuntimeError("Unexpected DeepSeek final verdict format") from e

    _log("PIPELINE", f"Final verdict generated for '{presentation_dir}' ({len(content)} chars)")

    # Лог финального вердикта
    try:
        section_log_dir = REPORT_LOG_ROOT / presentation_dir / "sections"
        section_log_dir.mkdir(parents=True, exist_ok=True)
        section_log_path = section_log_dir / f"{prompt_name}.json"
        payload = {
            "presentation_dir": presentation_dir,
            "prompt_name": prompt_name,
            "deepseek": {
                "request_path": str(req_path),
                "response_path": str(resp_path),
                "response_char_count": len(content),
            },
        }
        section_log_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        _log("REPORTLOG", f"Final verdict log saved: {section_log_path}")
    except Exception as e:
        _log("REPORTLOG", f"Failed to write final verdict log: {e}")

    return content.strip()


def build_full_markdown(section_texts: List[str], final_text: str) -> str:
    """
    Сборка финального markdown из разделов 1-5 и итогового вердикта.
    """
    intermediate_md = "\n\n\n".join(s.strip() for s in section_texts)
    full_md = intermediate_md + "\n\n\n" + final_text.strip() + "\n"
    return full_md


def markdown_to_docx(md_path: Path, docx_path: Path) -> None:
    """
    Шаг 5. Конвертация markdown в DOCX и применение форматирования.
    """
    convert_md_to_docx(md_path, docx_path)


def run_full_pipeline(pdf_path: Path, presentation_dir: str) -> Path:
    """
    Полный пайплайн end-to-end:
    1) PDF -> PNG слайды
    2) Qwen по промпту text_extraction.md
    3) 5 запросов в DeepSeek по промптам 1-5 (с добавлением текста Qwen)
    4) Финальный запрос в DeepSeek по промпту 6 (с добавлением всего MD)
    5) Конвертация MD -> DOCX + форматирование

    Возвращает путь к готовому DOCX файлу.
    """
    _ensure_dirs()

    md_path = TMP_DIR / f"{presentation_dir}.md"
    docx_path = RESULT_DIR / f"{presentation_dir}.docx"

    _log("PIPELINE", f"Start full pipeline for '{presentation_dir}'")

    # Базовый лог по презентации
    report_dir = REPORT_LOG_ROOT / presentation_dir
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "sections").mkdir(parents=True, exist_ok=True)
    _log("REPORTLOG", f"Report log directory: {report_dir}")

    # 1) PDF -> изображения
    image_paths = extract_slides_stage(pdf_path=pdf_path, presentation_dir=presentation_dir)

    # 2) Qwen: извлечение текста со слайдов
    _log("PIPELINE", f"Starting Qwen for '{presentation_dir}' ({len(image_paths)} slides)")
    qwen_text = qwen_from_slides_stage(image_paths=image_paths, presentation_dir=presentation_dir)
    _log("PIPELINE", f"Qwen finished for '{presentation_dir}' ({len(qwen_text)} chars)")

    # 2.5) Генерация поисковых запросов для Tavily
    tavily_queries_by_category = generate_tavily_queries_stage(qwen_text=qwen_text, presentation_dir=presentation_dir)
    try:
        (report_dir / "query_generation_summary.json").write_text(
            json.dumps(
                {
                    "presentation_dir": presentation_dir,
                    "query_generation_dir": str(TAVILY_ROOT / "query_generation" / presentation_dir),
                    "categories": list(tavily_queries_by_category.keys()),
                    "total_queries": sum(len(v) for v in tavily_queries_by_category.values()),
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        _log("REPORTLOG", f"Query generation summary saved: {report_dir / 'query_generation_summary.json'}")
    except Exception as e:
        _log("REPORTLOG", f"Failed to write query generation summary: {e}")

    # 3) DeepSeek: секции 1-5
    _log("PIPELINE", "Starting DeepSeek sections 1-5")
    section_texts, intermediate_md = run_deepseek_sections(
        qwen_text=qwen_text,
        presentation_dir=presentation_dir,
        tavily_queries_by_category=tavily_queries_by_category,
    )

    # 4) Финальный вердикт (секция 6)
    _log("PIPELINE", "Starting final verdict (section 6)")
    final_text = run_final_verdict(intermediate_md=intermediate_md, presentation_dir=presentation_dir)

    # 5) Сборка markdown и конвертация в DOCX
    full_md = build_full_markdown(section_texts=section_texts, final_text=final_text)
    md_path.write_text(full_md, encoding="utf-8")
    _log("REPORT", f"Markdown saved to: {md_path} ({len(full_md)} chars)")

    _log("REPORT", f"Converting MD to DOCX: {md_path} -> {docx_path}")
    markdown_to_docx(md_path=md_path, docx_path=docx_path)
    docx_size = docx_path.stat().st_size if docx_path.exists() else 0
    _log("REPORT", f"DOCX saved to: {docx_path} ({docx_size} bytes)")
    _log("REPORT", f"Pipeline completed: report ready at {docx_path}")

    # Финальный единый лог (сводка)
    try:
        section_names = [
            "1_info_from_pdf",
            "2_market_analyze",
            "3_competitors_analyze",
            "4_product_analyze",
            "5_team_analyze",
            "final_verdict",
        ]
        report_log_path = report_dir / "report_log.json"
        summary = {
            "presentation_dir": presentation_dir,
            "paths": {
                "pdf_path": str(pdf_path),
                "md_path": str(md_path),
                "docx_path": str(docx_path),
            },
            "sizes": {
                "md_chars": len(full_md),
                "docx_bytes": docx_path.stat().st_size if docx_path.exists() else 0,
            },
            "tavily": {
                "query_generation_dir": str(TAVILY_ROOT / "query_generation" / presentation_dir),
                "per_section_root": str(TAVILY_ROOT),
            },
            "sections": {
                name: str((report_dir / "sections" / f"{name}.json"))
                for name in section_names
            },
        }
        report_log_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        _log("REPORTLOG", f"Unified report log saved: {report_log_path}")
    except Exception as e:
        _log("REPORTLOG", f"Failed to write unified report log: {e}")

    return docx_path
