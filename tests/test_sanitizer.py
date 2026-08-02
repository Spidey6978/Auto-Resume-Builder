import pytest
from core.sanitizer import escape_latex, sanitize_data


def test_escape_latex_special_characters():
    raw_text = "Python & C++: 100% of $50 #1 {test_var} ~ ^ \\"
    escaped = escape_latex(raw_text)

    assert r"\&" in escaped
    assert r"\%" in escaped
    assert r"\$" in escaped
    assert r"\#" in escaped
    assert r"\_" in escaped
    assert r"\{" in escaped
    assert r"\}" in escaped
    assert r"\textasciitilde{}" in escaped
    assert r"\textasciicircum{}" in escaped
    assert r"\textbackslash{}" in escaped


def test_sanitize_data_dictionary_preserves_urls():
    input_data = {
        "name": "Veer Gopani & Co.",
        "link": "https://github.com/Spidey6978/test_repo",
        "github": "https://github.com/Spidey6978",
        "nested": {
            "title": "C++ & Rust Developer",
            "email": "veergopani70@gmail.com"
        }
    }

    sanitized = sanitize_data(input_data)

    assert sanitized["name"] == r"Veer Gopani \& Co."
    # Raw URLs must NOT be escaped
    assert sanitized["link"] == "https://github.com/Spidey6978/test_repo"
    assert sanitized["github"] == "https://github.com/Spidey6978"
    assert sanitized["nested"]["title"] == r"C++ \& Rust Developer"
    assert sanitized["nested"]["email"] == "veergopani70@gmail.com"
