"""认知主题与产业链映射库：从 JSON 配置文件加载主题定义。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def default_themes_path() -> Path:
    return Path(__file__).resolve().parents[3] / "config" / "cognition_themes.json"


def load_themes(path: str | Path | None = None) -> dict[str, dict[str, Any]]:
    """加载认知主题配置，返回 theme_key -> theme dict 的映射。"""
    config_path = Path(path) if path is not None else default_themes_path()
    return json.loads(config_path.read_text(encoding="utf-8"))
