import json
import os
from dataclasses import dataclass
from typing import Any, Dict, Tuple, Optional

@dataclass
class EnvConfig:
    token: str
    raw: Dict[str, Any]

def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def _extract_token(text: str) -> str:
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("TOKEN="):
            return s.split("=", 1)[1].strip()
    return ""

def _extract_json_block(text: str) -> Dict[str, Any]:
    idx = text.find("{")
    if idx == -1:
        return {}
    j = text[idx:].strip()
    try:
        return json.loads(j)
    except Exception:
        return {}

def read_env_with_json(env_path: str) -> EnvConfig:
    if not os.path.exists(env_path):
        raise FileNotFoundError(env_path)
    text = _read_text(env_path)
    token = _extract_token(text)
    raw = _extract_json_block(text)
    return EnvConfig(token=token, raw=raw)

class I18n:
    def __init__(self, raw: Dict[str, Any]):
        self.raw = raw
        app = raw.get("app") or {}
        self.lang = (app.get("default_language") or "ru").strip()
        self.languages = raw.get("languages") or {}

    def set_lang(self, lang: str) -> None:
        if lang in self.languages:
            self.lang = lang

    def available_langs(self) -> Tuple[str, ...]:
        return tuple(self.languages.keys())

    def t(self, path: str, **fmt: Any) -> str:
        lang_pack = self.languages.get(self.lang) or {}
        cur: Any = lang_pack
        for part in path.split("."):
            if isinstance(cur, dict) and part in cur:
                cur = cur[part]
            else:
                cur = None
                break
        if cur is None:
            cur = path
        if isinstance(cur, str):
            try:
                return cur.format(**fmt)
            except Exception:
                return cur
        return str(cur)

def get_app_meta(raw: Dict[str, Any]) -> Dict[str, Any]:
    return raw.get("app") or {}
