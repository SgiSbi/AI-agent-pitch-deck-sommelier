import base64
import json
import uuid
from pathlib import Path
from typing import List, Tuple

import requests

from .llm_clients import config, call_deepseek
from .test import pdf_to_images
from .formatting import convert_md_to_docx, format_docx_file


BASE_DIR = Path(__file__).resolve().parents[1]
PROMPTS_DIR = BASE_DIR / "promts"
TMP_DIR = BASE_DIR/ "backend" / "tmp"
RESULT_DIR = BASE_DIR / "backend" / "result"

SLIDES_ROOT = TMP_DIR / "slides"
TEXT_FROM_SLIDES_ROOT = TMP_DIR / "text_from_slides"
QWEN_REQUESTS_DIR = TMP_DIR / "qwen_requests"
QWEN_RESPONSES_DIR = TMP_DIR / "qwen_responses"
DEEPSEEK_ROOT = TMP_DIR / "deepseek"


def _load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    return path.read_text(encoding="utf-8")


def _ensure_dirs() -> None:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    SLIDES_ROOT.mkdir(parents=True, exist_ok=True)
    TEXT_FROM_SLIDES_ROOT.mkdir(parents=True, exist_ok=True)
    QWEN_REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    QWEN_RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    DEEPSEEK_ROOT.mkdir(parents=True, exist_ok=True)


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

    print(f"[SLIDES] Start processing PDF: {pdf_path}")
    print(f"[SLIDES] Target directory: {slides_dir}")

    try:
        image_paths = pdf_to_slide_images(pdf_path=pdf_path, slides_dir=slides_dir)
    except Exception as e:
        print(f"[SLIDES] Error while processing slides for '{pdf_path}': {e}")
        raise

    print("slide processing completed successfully")
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

    # Первый элемент content — текст промпта
    content_items: list[dict] = [
        {
            "type": "text",
            "text": text_extraction_prompt.strip(),
        }
    ]

    # Кодируем каждый слайд в base64 и добавляем по одному блоку image_url
    for img_path in image_paths:
        try:
            with open(img_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            data_url = f"data:image/png;base64,{b64}"
            content_items.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": data_url,
                    },
                }
            )
        except Exception as e:
            print(f"[QWEN] Failed to read/encode image '{img_path}': {e}")

    messages = [
        {
            "role": "user",
            "content": content_items,
        }
    ]

    payload = {
        "model": config.qwen_model,
        "messages": messages,
    }

    req_dir = QWEN_REQUESTS_DIR
    resp_dir = QWEN_RESPONSES_DIR
    req_dir.mkdir(parents=True, exist_ok=True)
    resp_dir.mkdir(parents=True, exist_ok=True)

    req_path = req_dir / f"{presentation_dir}.json"
    resp_path = resp_dir / f"{presentation_dir}.json"

    # Сохраняем структуру запроса в файл (image_url сокращаем, чтобы не писать base64)
    content_for_log = []
    for c in content_items:
        if c["type"] == "text":
            content_for_log.append({"type": "text", "text": (c["text"][:500] + "...") if len(c["text"]) > 500 else c["text"]})
        else:
            content_for_log.append({"type": "image_url", "image_url": {"url": "<data:image/png;base64,...>"}})
    payload_for_log = {"model": payload["model"], "messages": [{"role": "user", "content": content_for_log}]}
    req_path.write_text(json.dumps(payload_for_log, ensure_ascii=False, indent=2), encoding="utf-8")

    headers = {
        "Authorization": f"Bearer {config.qwen_api_key}",
        "Content-Type": "application/json",
    }
    url = config.qwen_api_base.rstrip("/") + "/chat/completions"

    print(f"[QWEN] Sending request for '{presentation_dir}' ({len(image_paths)} slides) to {url}")
    print(f"[QWEN] Request metadata saved to: {req_path}")

    resp = requests.post(url, json=payload, headers=headers, timeout=600)
    if not resp.ok:
        print(f"[QWEN] Error response status={resp.status_code} body={resp.text}")
        resp.raise_for_status()

    resp_json = resp.json()
    resp_path.write_text(json.dumps(resp_json, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[QWEN] Response saved to: {resp_path}")

    try:
        full_content = resp_json["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[QWEN] Unexpected response format: {resp_json}")
        raise RuntimeError("Unexpected Qwen response format") from e

    text_dir = TEXT_FROM_SLIDES_ROOT / presentation_dir
    text_dir.mkdir(parents=True, exist_ok=True)
    text_file = text_dir / "text_from_slides.txt"
    text_file.write_text(full_content, encoding="utf-8")
    print(f"[QWEN] Extracted text saved to: {text_file}")

    return full_content


# === ЭТАП 3: DeepSeek по отдельным модулям ===

def send_section_to_deepseek(prompt_filename: str, qwen_text: str, presentation_dir: str) -> str:
    """
    Этап 3. Отправка одной секции в DeepSeek:
    - читает базовый промпт из файла
    - добавляет блок SLIDES с текстом от Qwen
    - сохраняет запрос и ответ в TMP_DIR/deepseek/<name_prompt>/{requests,responses}
    - возвращает текст ответа DeepSeek.
    """
    base_prompt = _load_prompt(prompt_filename)
    full_prompt = (
        f"{base_prompt.strip()}\n\n"
        f"---SLIDES START---\n{qwen_text.strip()}\n---SLIDES END---"
    )

    prompt_name = Path(prompt_filename).stem
    base_dir = DEEPSEEK_ROOT / prompt_name
    req_dir = base_dir / "requests"
    resp_dir = base_dir / "responses"
    req_dir.mkdir(parents=True, exist_ok=True)
    resp_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "model": config.deepseek_model,
        "messages": [{"role": "user", "content": full_prompt}],
    }
    headers = {
        "Authorization": f"Bearer {config.deepseek_api_key}",
        "Content-Type": "application/json",
    }

    req_path = req_dir / f"{presentation_dir}.json"
    resp_path = resp_dir / f"{presentation_dir}.json"

    req_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    url = config.deepseek_api_base.rstrip("/") + "/chat/completions"
    print(f"[DEEPSEEK:{prompt_name}] Sending request for '{presentation_dir}' to {url}")
    print(f"[DEEPSEEK:{prompt_name}] Request saved to: {req_path}")

    resp = requests.post(url, json=payload, headers=headers, timeout=600)
    resp.raise_for_status()
    resp_json = resp.json()
    resp_path.write_text(json.dumps(resp_json, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[DEEPSEEK:{prompt_name}] Response saved to: {resp_path}")

    try:
        content = resp_json["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[DEEPSEEK:{prompt_name}] Unexpected response format: {resp_json}")
        raise RuntimeError("Unexpected DeepSeek response format") from e

    return content.strip()


def run_deepseek_sections(qwen_text: str, presentation_dir: str) -> Tuple[List[str], str]:
    """
    Шаг 3. Пять запросов в DeepSeek по промптам 1-5.

    Возвращает кортеж:
    - список текстов по каждому разделу,
    - общий markdown по разделам 1-5 (intermediate_md).
    """
    section_prompts_files = [
        "1_info_from_pdf_prompt.md",
        "2_market_analyze_prompt.md",
        "3_competitors_analyze_prompt.md",
        "4_product_analyze_prompt.md",
        "5_team_analyze_prompt.md",
    ]

    md_parts: List[str] = []

    for filename in section_prompts_files:
        section_text = send_section_to_deepseek(
            prompt_filename=filename,
            qwen_text=qwen_text,
            presentation_dir=presentation_dir,
        )
        md_parts.append(section_text)

    intermediate_md = "\n\n\n".join(md_parts)
    return md_parts, intermediate_md


def run_final_verdict(intermediate_md: str) -> str:
    """
    Шаг 4. Финальный запрос в DeepSeek по промпту 6 с добавлением всего markdown.
    """
    final_prompt_base = _load_prompt("6_final_verdict_prompt.md")
    final_full_prompt = (
        f"{final_prompt_base.strip()}\n\n"
        f"---REPORTS START---\n{intermediate_md}\n---REPORTS END---"
    )
    return call_deepseek(final_full_prompt).strip()


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
    format_docx_file(docx_path, docx_path)


def run_full_pipeline(pdf_path: Path) -> Path:
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

    run_id = uuid.uuid4().hex
    presentation_dir = f"{pdf_path.stem}_{run_id}"
    md_path = TMP_DIR / f"report_{run_id}.md"
    docx_path = RESULT_DIR / f"report_{run_id}.docx"

    # 1) PDF -> изображения
    image_paths = extract_slides_stage(pdf_path=pdf_path, presentation_dir=presentation_dir)

    # 2) Qwen: извлечение текста со слайдов
    qwen_text = qwen_from_slides_stage(image_paths=image_paths, presentation_dir=presentation_dir)

    # 3) DeepSeek: секции 1-5
    section_texts, intermediate_md = run_deepseek_sections(
        qwen_text=qwen_text,
        presentation_dir=presentation_dir,
    )

    # 4) Финальный вердикт (секция 6)
    final_text = run_final_verdict(intermediate_md=intermediate_md)

    # 5) Сборка markdown и конвертация в DOCX
    full_md = build_full_markdown(section_texts=section_texts, final_text=final_text)
    md_path.write_text(full_md, encoding="utf-8")
    markdown_to_docx(md_path=md_path, docx_path=docx_path)

    return docx_path
