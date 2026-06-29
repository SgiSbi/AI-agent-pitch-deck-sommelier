from __future__ import annotations

from pathlib import Path

# BASE_DIR указывает на корень проекта (Ai-agent)
BASE_DIR = Path(__file__).resolve().parents[2]
PROMPTS_DIR = BASE_DIR / "promts"
TMP_DIR = BASE_DIR / "tmp"
RESULT_DIR = BASE_DIR / "reports"

RAW_PRESENTATIONS_ROOT = TMP_DIR / "raw_presentations"
SLIDES_ROOT = TMP_DIR / "slides"
TEXT_FROM_SLIDES_ROOT = TMP_DIR / "text_from_slides"
QWEN_ROOT = TMP_DIR / "qwen"
QWEN_REQUESTS_DIR = TMP_DIR / "qwen" / "requests"
QWEN_RESPONSES_DIR = TMP_DIR / "qwen" / "responses"
DEEPSEEK_ROOT = TMP_DIR / "deepseek"
TAVILY_ROOT = TMP_DIR / "tavily"
REPORT_LOG_ROOT = TMP_DIR / "report_logs"


def ensure_dirs() -> None:
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    RAW_PRESENTATIONS_ROOT.mkdir(parents=True, exist_ok=True)
    SLIDES_ROOT.mkdir(parents=True, exist_ok=True)
    TEXT_FROM_SLIDES_ROOT.mkdir(parents=True, exist_ok=True)
    QWEN_ROOT.mkdir(parents=True, exist_ok=True)
    QWEN_REQUESTS_DIR.mkdir(parents=True, exist_ok=True)
    QWEN_RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    DEEPSEEK_ROOT.mkdir(parents=True, exist_ok=True)
    TAVILY_ROOT.mkdir(parents=True, exist_ok=True)
    (TAVILY_ROOT / "query_generation").mkdir(parents=True, exist_ok=True)
    REPORT_LOG_ROOT.mkdir(parents=True, exist_ok=True)


_PROMPT_NO_SHARED = frozenset({
    "_shared_output_rules.md",
    "additional_prompt_for_websearch.md",
    "text_extraction.md",
})


def load_prompt(filename: str) -> str:
    path = PROMPTS_DIR / filename
    body = path.read_text(encoding="utf-8")
    if filename in _PROMPT_NO_SHARED or filename.startswith("_"):
        return body
    shared_path = PROMPTS_DIR / "_shared_output_rules.md"
    if not shared_path.exists():
        return body
    shared = shared_path.read_text(encoding="utf-8").strip()
    return f"{shared}\n\n---\n\n{body}"

