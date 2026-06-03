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


def test_extractor_preserves_code_blocks_as_markdown_fences() -> None:
    html = """
    <html><head><title>Fibonacci</title></head>
    <body><main>
      <h1>Generate Fibonacci in Python</h1>
      <p>Use this implementation:</p>
      <pre><code class="language-python">def fibonacci(n):
    sequence = [0, 1]
    for _ in range(2, n):
        sequence.append(sequence[-1] + sequence[-2])
    return sequence[:n]</code></pre>
    </main></body></html>
    """

    doc = HtmlExtractor().extract("https://example.com/fibonacci", html)

    assert "```python" in doc.text
    assert "def fibonacci(n):" in doc.text
    assert "sequence.append(sequence[-1] + sequence[-2])" in doc.text
    assert doc.text.count("```") == 2

