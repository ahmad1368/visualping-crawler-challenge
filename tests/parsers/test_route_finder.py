"""Unit tests for the regex route finder: route_finder.find_routes."""

import pytest

from parsers.route_finder import find_routes, find_routes_in_html


class TestFindRoutes:
    """Success and failure scenarios for find_routes."""

    def test_extracts_route_from_plain_text(self):
        text = "See the docs at /api/v1/docs for details."
        routes = find_routes(text, base_url="https://example.com")
        assert routes == ["https://example.com/api/v1/docs"]

    def test_extracts_route_embedded_in_js_string_literal(self):
        text = 'fetch("/api/v1/secret-token").then(handleResponse);'
        routes = find_routes(text, base_url="https://example.com")
        assert routes == ["https://example.com/api/v1/secret-token"]

    def test_extracts_route_from_html_comment_text(self):
        text = "<!-- TODO: remove debug endpoint /internal/debug before launch -->"
        routes = find_routes(text, base_url="https://example.com")
        assert routes == ["https://example.com/internal/debug"]

    def test_normalizes_relative_route_against_base_path(self):
        text = "endpoint: /users/42"
        routes = find_routes(text, base_url="https://example.com/app/")
        assert routes == ["https://example.com/users/42"]

    def test_deduplicates_repeated_routes_preserving_order(self):
        text = "call /api/one then /api/two then /api/one again"
        routes = find_routes(text, base_url="https://example.com")
        assert routes == ["https://example.com/api/one", "https://example.com/api/two"]

    def test_ignores_absolute_urls_entirely(self):
        text = "Visit http://example.com/dashboard for the overview."
        routes = find_routes(text, base_url="https://example.com")
        assert routes == []

    def test_filters_out_protocol_relative_urls(self):
        text = "load script from //cdn.example.com/lib.js"
        routes = find_routes(text, base_url="https://example.com")
        assert routes == []

    def test_filters_out_bare_slash(self):
        text = "the root path is / and nothing else"
        routes = find_routes(text, base_url="https://example.com")
        assert routes == []

    def test_returns_empty_list_when_no_routes_present(self):
        text = "Just some plain text with no paths at all."
        routes = find_routes(text, base_url="https://example.com")
        assert routes == []

    def test_returns_empty_list_for_empty_text(self):
        routes = find_routes("", base_url="https://example.com")
        assert routes == []

    def test_ignores_slashes_inside_words(self):
        text = "the speed limit is 100km/h in this zone"
        routes = find_routes(text, base_url="https://example.com")
        assert routes == []

    def test_raises_on_blank_base_url(self):
        with pytest.raises(ValueError):
            find_routes("/api/v1/route", base_url="   ")


class TestFindRoutesInHtml:
    """Success and failure scenarios for find_routes_in_html."""

    def test_does_not_mistake_closing_tags_for_routes(self):
        # Regression test: applying find_routes directly to raw HTML
        # markup (rather than extracted text) previously matched a
        # closing tag like "</a>" as the route "/a", since the regex
        # has no notion of markup vs. plain text. A normal <a href>
        # link is not a "hidden" route (extract_links already finds
        # it), so nothing should be found here -- least of all a
        # spurious "/a" from the closing tag.
        html = '<a href="/child">child</a>'
        routes = find_routes_in_html(html, base_url="https://example.com")
        assert routes == []

    def test_finds_route_in_inline_script(self):
        html = '<body><script>fetch("/api/hidden-route");</script></body>'
        routes = find_routes_in_html(html, base_url="https://example.com")
        assert routes == ["https://example.com/api/hidden-route"]

    def test_finds_route_in_html_comment(self):
        html = "<body><!-- debug endpoint: /internal/debug --></body>"
        routes = find_routes_in_html(html, base_url="https://example.com")
        assert routes == ["https://example.com/internal/debug"]

    def test_finds_route_in_visible_body_text(self):
        html = "<body><p>See /docs/getting-started for details.</p></body>"
        routes = find_routes_in_html(html, base_url="https://example.com")
        assert routes == ["https://example.com/docs/getting-started"]

    def test_ignores_route_like_text_inside_style_tag(self):
        html = '<body><style>/* not a route: /fake/path */</style></body>'
        routes = find_routes_in_html(html, base_url="https://example.com")
        assert routes == []

    def test_returns_empty_list_for_html_with_no_routes(self):
        html = "<body><p>Nothing here.</p></body>"
        routes = find_routes_in_html(html, base_url="https://example.com")
        assert routes == []

    def test_returns_empty_list_for_empty_html(self):
        routes = find_routes_in_html("", base_url="https://example.com")
        assert routes == []
