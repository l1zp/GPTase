"Tests for enzyme extraction tools."

import pytest

from src.tools.enzyme_extractor import extract_from_html
from src.tools.enzyme_extractor import extract_steps


@pytest.fixture
def sample_steps_text():
    return (
        "We performed computational design focusing on the active site and molecular dynamics.\n"
        "Library construction with site-directed mutagenesis was used.\n"
        "Expression and purification followed by kinetic assay to determine Km and kcat.\n"
        "Optimization via directed evolution improved activity.")


@pytest.fixture
def sample_html_content():
    return "<p>computational design</p><p>kinetic assay Km</p>"


def test_extract_steps_basic(sample_steps_text):
    result = extract_steps(sample_steps_text)
    assert result["status"] == "success"
    cats = {s["category"] for s in result["steps"]}
    assert {"Design", "Construction", "Expression", "Assay",
            "Optimization"}.issubset(cats)
    assert result["confidence_overall"] > 0.2


def test_extract_from_html(sample_html_content):
    result = extract_from_html(sample_html_content)
    assert result["status"] == "success"
    assert any(s["category"] == "Design" for s in result["steps"])
