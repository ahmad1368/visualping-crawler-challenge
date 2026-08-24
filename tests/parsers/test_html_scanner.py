"""Unit tests for the HTML body/comments scanner: html_scanner.scan_html."""

from core.models import SecretLocation
from parsers.html_scanner import scan_html

BODY_SECRET = "VISUALPING{0123456789abcdef}"
COMMENT_SECRET = "VISUALPING{fedcba9876543210}"


class TestScanHtml:
    """Success and failure scenarios for scan_html."""

    def test_finds_secret_in_visible_body_text(self):
        html = f"<body><p>Config value: {BODY_SECRET}</p></body>"
        secrets = scan_html(html, url="https://example.com")
        assert len(secrets) == 1
        assert secrets[0].value == BODY_SECRET
        assert secrets[0].location == SecretLocation.HTML_BODY

    def test_finds_secret_in_html_comment(self):
        html = f"<body><!-- debug: {COMMENT_SECRET} --></body>"
        secrets = scan_html(html, url="https://example.com")
        assert len(secrets) == 1
        assert secrets[0].value == COMMENT_SECRET
        assert secrets[0].location == SecretLocation.HTML_COMMENT

    def test_finds_secrets_in_both_body_and_comments(self):
        html = f"<body><p>{BODY_SECRET}</p><!-- {COMMENT_SECRET} --></body>"
        secrets = scan_html(html, url="https://example.com")
        found = {(s.value, s.location) for s in secrets}
        assert found == {
            (BODY_SECRET, SecretLocation.HTML_BODY),
            (COMMENT_SECRET, SecretLocation.HTML_COMMENT),
        }

    def test_ignores_secret_inside_script_tag(self):
        html = f'<body><script>var t = "{BODY_SECRET}";</script></body>'
        secrets = scan_html(html, url="https://example.com")
        assert secrets == []

    def test_ignores_secret_inside_style_tag(self):
        html = f"<body><style>/* {BODY_SECRET} */</style></body>"
        secrets = scan_html(html, url="https://example.com")
        assert secrets == []

    def test_attaches_url_to_every_finding(self):
        html = f"<body>{BODY_SECRET}</body>"
        secrets = scan_html(html, url="https://example.com/page")
        assert secrets[0].url == "https://example.com/page"

    def test_finds_multiple_secrets_in_separate_comments(self):
        second = "VISUALPING{1111111111111111}"
        html = f"<body><!-- {COMMENT_SECRET} --><!-- {second} --></body>"
        secrets = scan_html(html, url="https://example.com")
        assert {s.value for s in secrets} == {COMMENT_SECRET, second}

    def test_returns_empty_list_when_no_secrets_present(self):
        html = "<body><p>Nothing sensitive here.</p></body>"
        secrets = scan_html(html, url="https://example.com")
        assert secrets == []

    def test_returns_empty_list_for_empty_html(self):
        secrets = scan_html("", url="https://example.com")
        assert secrets == []
