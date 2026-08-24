"""Unit tests for the HTML link extractor: link_extractor.extract_links."""

import pytest

from parsers.link_extractor import extract_links


class TestExtractLinks:
    """Success and failure scenarios for extract_links."""

    def test_extracts_absolute_links_unchanged(self):
        html = '<a href="https://example.com/other">link</a>'
        links = extract_links(html, base_url="https://example.com/page")
        assert links == ["https://example.com/other"]

    def test_normalizes_relative_links_to_absolute(self):
        html = '<a href="/relative/path">link</a>'
        links = extract_links(html, base_url="https://example.com/page")
        assert links == ["https://example.com/relative/path"]

    def test_normalizes_relative_links_against_directory(self):
        html = '<a href="child">link</a>'
        links = extract_links(html, base_url="https://example.com/dir/page")
        assert links == ["https://example.com/dir/child"]

    def test_strips_url_fragment(self):
        html = '<a href="/page#section-2">link</a>'
        links = extract_links(html, base_url="https://example.com")
        assert links == ["https://example.com/page"]

    def test_skips_fragment_only_links(self):
        html = '<a href="#top">back to top</a>'
        links = extract_links(html, base_url="https://example.com")
        assert links == []

    def test_skips_anchors_without_href(self):
        html = '<a name="anchor">no href</a>'
        links = extract_links(html, base_url="https://example.com")
        assert links == []

    def test_skips_anchors_with_blank_href(self):
        html = '<a href="   ">blank</a>'
        links = extract_links(html, base_url="https://example.com")
        assert links == []

    def test_deduplicates_links_preserving_first_seen_order(self):
        html = """
            <a href="/a">first</a>
            <a href="/b">second</a>
            <a href="/a">duplicate</a>
        """
        links = extract_links(html, base_url="https://example.com")
        assert links == ["https://example.com/a", "https://example.com/b"]

    def test_deduplicates_links_that_only_differ_by_fragment(self):
        html = """
            <a href="/page#one">first</a>
            <a href="/page#two">second</a>
        """
        links = extract_links(html, base_url="https://example.com")
        assert links == ["https://example.com/page"]

    def test_ignores_non_anchor_tags(self):
        html = '<link rel="stylesheet" href="/style.css"><script src="/app.js"></script>'
        links = extract_links(html, base_url="https://example.com")
        assert links == []

    def test_only_scans_body_when_full_document_provided(self):
        html = """
            <html>
              <head><a href="/head-link">should be ignored</a></head>
              <body><a href="/body-link">should be extracted</a></body>
            </html>
        """
        links = extract_links(html, base_url="https://example.com")
        assert links == ["https://example.com/body-link"]

    def test_extracts_from_bare_fragment_without_body_tag(self):
        html = '<div><a href="/x">x</a></div>'
        links = extract_links(html, base_url="https://example.com")
        assert links == ["https://example.com/x"]

    def test_returns_empty_list_for_html_with_no_links(self):
        html = "<p>No links here.</p>"
        links = extract_links(html, base_url="https://example.com")
        assert links == []

    def test_returns_empty_list_for_empty_html_body(self):
        links = extract_links("", base_url="https://example.com")
        assert links == []

    def test_raises_on_blank_base_url(self):
        with pytest.raises(ValueError):
            extract_links("<a href='/x'>x</a>", base_url="   ")
