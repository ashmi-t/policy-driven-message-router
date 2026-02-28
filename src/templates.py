"""Jinja2 rendering for message bodies. Supports inline templates like 'Hello {{ name }}'."""
from typing import Any, Dict

from jinja2 import Environment, BaseLoader


def render_body(template_key: str, context: Dict[str, Any]) -> str:
    env = Environment(loader=BaseLoader())
    try:
        template = env.from_string(template_key)
    except Exception:
        return template_key
    return template.render(**context)


def get_body_content(template_key: str, context: Dict[str, Any]) -> str:
    return render_body(template_key, context or {})
