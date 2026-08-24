"""Unit tests for the headers/cookies/script scanner in asset_scanner.py."""

from core.models import SecretLocation
from parsers.asset_scanner import scan_cookies, scan_headers, scan_inline_scripts, scan_script

SECRET = "VISUALPING{0123456789abcdef}"


class TestScanHeaders:
    """Success and failure scenarios for scan_headers."""

    def test_finds_secret_in_custom_header_value(self):
        secrets = scan_headers({"X-Debug-Token": SECRET}, url="https://example.com")
        assert len(secrets) == 1
        assert secrets[0].value == SECRET
        assert secrets[0].location == SecretLocation.HTTP_HEADER

    def test_snippet_captures_header_name(self):
        secrets = scan_headers({"X-Debug-Token": SECRET}, url="https://example.com")
        assert "X-Debug-Token" in secrets[0].snippet

    def test_scans_multiple_headers(self):
        second_secret = "VISUALPING{fedcba9876543210}"
        headers = {"X-One": SECRET, "X-Two": second_secret, "Content-Type": "text/html"}
        secrets = scan_headers(headers, url="https://example.com")
        assert {s.value for s in secrets} == {SECRET, second_secret}

    def test_returns_empty_list_when_no_header_has_a_secret(self):
        headers = {"Content-Type": "text/html", "Server": "nginx"}
        secrets = scan_headers(headers, url="https://example.com")
        assert secrets == []

    def test_returns_empty_list_for_empty_headers(self):
        secrets = scan_headers({}, url="https://example.com")
        assert secrets == []


class TestScanCookies:
    """Success and failure scenarios for scan_cookies."""

    def test_finds_secret_in_cookie_value(self):
        secrets = scan_cookies({"debug_token": SECRET}, url="https://example.com")
        assert len(secrets) == 1
        assert secrets[0].value == SECRET
        assert secrets[0].location == SecretLocation.COOKIE

    def test_snippet_captures_cookie_key(self):
        secrets = scan_cookies({"debug_token": SECRET}, url="https://example.com")
        assert "debug_token" in secrets[0].snippet

    def test_scans_multiple_cookies(self):
        second_secret = "VISUALPING{fedcba9876543210}"
        cookies = {"a": SECRET, "b": second_secret, "session": "abc123"}
        secrets = scan_cookies(cookies, url="https://example.com")
        assert {s.value for s in secrets} == {SECRET, second_secret}

    def test_returns_empty_list_when_no_cookie_has_a_secret(self):
        secrets = scan_cookies({"session": "abc123"}, url="https://example.com")
        assert secrets == []

    def test_returns_empty_list_for_empty_cookies(self):
        secrets = scan_cookies({}, url="https://example.com")
        assert secrets == []


class TestScanScript:
    """Success and failure scenarios for scan_script (inline or linked-asset text)."""

    def test_finds_secret_in_script_text(self):
        secrets = scan_script(f'var token = "{SECRET}";', url="https://example.com/app.js")
        assert len(secrets) == 1
        assert secrets[0].value == SECRET
        assert secrets[0].location == SecretLocation.SCRIPT

    def test_attaches_given_url_to_finding(self):
        secrets = scan_script(SECRET, url="https://example.com/vendor.js")
        assert secrets[0].url == "https://example.com/vendor.js"

    def test_returns_empty_list_for_script_without_secret(self):
        secrets = scan_script("console.log('hello');", url="https://example.com/app.js")
        assert secrets == []


class TestScanInlineScripts:
    """Success and failure scenarios for scan_inline_scripts."""

    def test_finds_secret_in_inline_script_tag(self):
        html = f'<body><script>var t = "{SECRET}";</script></body>'
        secrets = scan_inline_scripts(html, url="https://example.com")
        assert len(secrets) == 1
        assert secrets[0].value == SECRET
        assert secrets[0].location == SecretLocation.SCRIPT

    def test_ignores_secret_outside_script_tags(self):
        html = f"<body><p>{SECRET}</p></body>"
        secrets = scan_inline_scripts(html, url="https://example.com")
        assert secrets == []

    def test_scans_multiple_script_tags(self):
        second_secret = "VISUALPING{fedcba9876543210}"
        html = f"<body><script>{SECRET}</script><script>{second_secret}</script></body>"
        secrets = scan_inline_scripts(html, url="https://example.com")
        assert {s.value for s in secrets} == {SECRET, second_secret}

    def test_returns_empty_list_when_no_scripts_present(self):
        html = "<body><p>No scripts here.</p></body>"
        secrets = scan_inline_scripts(html, url="https://example.com")
        assert secrets == []

    def test_returns_empty_list_for_empty_html(self):
        secrets = scan_inline_scripts("", url="https://example.com")
        assert secrets == []
