"""Unit tests for the regex route finder: route_finder.find_routes."""

import pytest

from parsers.route_finder import find_routes


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
