from shorts.sources import extract_from_html

HTML = """<html><head><title>Coffee study</title></head><body>
<nav>Home | About</nav>
<article><h1>Coffee study</h1>
<p>Researchers found that morning coffee changes how memory consolidates. The effect was measured in 200 adults over six weeks and held across age groups.</p>
<p>The team cautions that more work is needed before making recommendations.</p></article>
<footer>© 2026</footer></body></html>"""


def test_extract_main_text():
    doc = extract_from_html(HTML, "https://example.com/coffee")
    assert "morning coffee" in doc.text
    assert "About" not in doc.text
    assert doc.title == "Coffee study"
