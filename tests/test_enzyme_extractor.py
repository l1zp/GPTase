from src.tools.enzyme_extractor import extract_steps, extract_from_html

def test_extract_steps_basic():
    text = (
        "We performed computational design focusing on the active site and molecular dynamics.\n"
        "Library construction with site-directed mutagenesis was used.\n"
        "Expression and purification followed by kinetic assay to determine Km and kcat.\n"
        "Optimization via directed evolution improved activity."
    )
    result = extract_steps(text)
    assert result["status"] == "success"
    cats = {s["category"] for s in result["steps"]}
    assert {"Design", "Construction", "Expression", "Assay", "Optimization"}.issubset(cats)
    assert result["confidence_overall"] > 0.2

def test_extract_from_html():
    html = "<p>computational design</p><p>kinetic assay Km</p>"
    result = extract_from_html(html)
    assert result["status"] == "success"
    assert any(s["category"] == "Design" for s in result["steps"])
