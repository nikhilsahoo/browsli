from browsli.extractor import HtmlExtractor


def test_extractor_resolves_relative_links() -> None:
    html = """
    <html><head><title>Example</title></head>
    <body><main><h1>Hello</h1><p>Read <a href="/docs">docs</a>.</p></main></body></html>
    """

    doc = HtmlExtractor().extract("https://example.com/start", html)

    assert doc.title == "Example"
    assert "Hello" in doc.text
    assert doc.links[0].text == "docs"
    assert doc.links[0].url == "https://example.com/docs"


def test_extractor_marks_js_dependent_empty_page() -> None:
    html = '<html><body><div id="root"></div><script src="/app.js"></script></body></html>'

    doc = HtmlExtractor().extract("https://example.com/app", html)

    assert doc.js_dependent is True
    assert doc.text == ""

