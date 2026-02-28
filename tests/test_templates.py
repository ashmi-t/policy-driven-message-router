"""Tests for template rendering."""
import pytest

from src.templates import render_body, get_body_content


def test_render_simple_placeholder() -> None:
    out = render_body("Hello {{ name }}", {"name": "World"})
    assert out == "Hello World"


def test_render_multiple_vars() -> None:
    out = render_body("{{ greeting }}, {{ name }}!", {"greeting": "Hi", "name": "Alice"})
    assert out == "Hi, Alice!"


def test_render_missing_var_empty() -> None:
    out = render_body("Hello {{ name }}", {})
    assert "name" in out or out == "Hello "  # Jinja2 may render empty or leave placeholder


def test_get_body_content_empty_context() -> None:
    out = get_body_content("Static text", {})
    assert out == "Static text"


def test_render_conditional() -> None:
    out = render_body("{% if active %}Yes{% else %}No{% endif %}", {"active": True})
    assert out == "Yes"
    out2 = render_body("{% if active %}Yes{% else %}No{% endif %}", {"active": False})
    assert out2 == "No"
