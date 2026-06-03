from browsli.links import LinkRegistry, unknown_link_tokens
from browsli.models import Link


def test_link_registry_numbers_links_stably() -> None:
    registry = LinkRegistry.from_raw_links(
        [
            ("Docs", "https://example.com/docs"),
            ("Download", "https://example.com/download"),
        ]
    )

    assert registry.links == (
        Link(1, "Docs", "https://example.com/docs"),
        Link(2, "Download", "https://example.com/download"),
    )
    assert registry.resolve(2).url == "https://example.com/download"


def test_unknown_link_tokens_are_detected() -> None:
    links = (Link(1, "One", "https://example.com/one"),)

    assert unknown_link_tokens("Open [1] and [2]", links) == {2}

