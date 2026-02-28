"""Template rendering for message body."""
from typing import Any, Dict

from jinja2 import Environment, BaseLoader, TemplateNotFound


def render_body(template_key: str, context: Dict[str, Any]) -> str:
    """
    Render message body from template key and context.
    template_key can be a simple template string (e.g. "Hello {{ name }}") or a named key.
    """
    env = Environment(loader=BaseLoader())
    try:
        template = env.from_string(template_key)
    except Exception:
        return template_key  # Not valid Jinja, return as plain text
    return template.render(**context)


def get_body_content(template_key: str, context: Dict[str, Any]) -> str:
    """Alias for render_body for clarity in callers."""
    return render_body(template_key, context or {})
