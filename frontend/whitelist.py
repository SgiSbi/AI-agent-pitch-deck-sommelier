"""Модуль управления вайтлистом пользователей Telegram-бота."""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

WHITELIST_PATH = Path(__file__).resolve().parent / "users_whitelist.json"

# Ключи статистики в JSON: "stats" -> { "username": { "input_tokens", "output_tokens", "tavily_requests" } }
STATS_KEYS = ("input_tokens", "output_tokens", "tavily_requests")


def load_whitelist(path: Path | None = None) -> dict:
    """Загружает вайтлист из JSON. Структура: {"users": {"username": "standard"|"admin"}, "stats": {...}}"""
    p = path or WHITELIST_PATH
    if not p.exists():
        return {"users": {}, "stats": {}}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return {"users": {}, "stats": {}}
        if "users" not in data or not isinstance(data["users"], dict):
            data["users"] = {}
        if "stats" not in data or not isinstance(data["stats"], dict):
            data["stats"] = {}
        return data
    except Exception as e:
        logger.error(f"Failed to load whitelist: {e}")
        return {"users": {}, "stats": {}}


def save_whitelist(data: dict, path: Path | None = None) -> None:
    """Сохраняет вайтлист в JSON."""
    p = path or WHITELIST_PATH
    try:
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        logger.error(f"Failed to save whitelist: {e}")


def get_user_role(username: str | None, path: Path | None = None) -> str | None:
    """Возвращает роль пользователя по username или None, если не в вайтлисте."""
    if not username:
        return None
    wl = load_whitelist(path)
    users = wl.get("users", {})
    lower_map = {k.lower(): v for k, v in users.items()}
    return lower_map.get(username.lower())


def get_user_stats(username: str | None, path: Path | None = None) -> dict:
    """Возвращает статистику по пользователю: input_tokens, output_tokens, tavily_requests."""
    if not username:
        return {k: 0 for k in STATS_KEYS}
    wl = load_whitelist(path)
    stats = wl.get("stats", {}).get(username, {})
    return {k: int(stats.get(k, 0)) for k in STATS_KEYS}


def get_all_stats(path: Path | None = None) -> dict:
    """Возвращает словарь { username: { input_tokens, output_tokens, tavily_requests } } для всех пользователей из users."""
    wl = load_whitelist(path)
    result = {}
    for u in wl.get("users", {}).keys():
        result[u] = get_user_stats(u, path)
    return result


def update_user_stats(
    username: str | None,
    delta: dict,
    path: Path | None = None,
) -> None:
    """
    Добавляет к статистике пользователя значения из delta.
    delta: {"input_tokens": int, "output_tokens": int, "tavily_requests": int}
    """
    if not username:
        return
    p = path or WHITELIST_PATH
    wl = load_whitelist(p)
    if "stats" not in wl or not isinstance(wl["stats"], dict):
        wl["stats"] = {}
    current = dict(get_user_stats(username, p))
    for k in STATS_KEYS:
        current[k] = current.get(k, 0) + int(delta.get(k, 0))
    wl["stats"][username] = current
    save_whitelist(wl, p)
