"""Unit tests for the secret snippet extractor: secret_finder.find_secrets."""

from core.models import SecretLocation
from parsers.secret_finder import find_secrets

VALID_SECRET = "VISUALPING{0123456789abcdef}"


class TestFindSecrets:
    """Success and failure scenarios for find_secrets."""

    def test_finds_secret_value(self):
        text = f"config token: {VALID_SECRET} loaded"
        secrets = find_secrets(text, url="https://example.com", location=SecretLocation.HTML_BODY)
        assert len(secrets) == 1
        assert secrets[0].value == VALID_SECRET

    def test_attaches_url_and_location(self):
        text = VALID_SECRET
        secrets = find_secrets(text, url="https://example.com/page", location=SecretLocation.COOKIE)
        assert secrets[0].url == "https://example.com/page"
        assert secrets[0].location == SecretLocation.COOKIE

    def test_captures_context_before_and_after(self):
        text = f"the leaked value is {VALID_SECRET} inside this response body"
        secrets = find_secrets(text, url="https://example.com", location=SecretLocation.HTML_BODY)
        snippet = secrets[0].snippet
        assert "leaked value is" in snippet
        assert "inside this response" in snippet

    def test_clamps_context_at_start_of_text(self):
        text = f"{VALID_SECRET} trailing context only, no room before the match"
        secrets = find_secrets(text, url="https://example.com", location=SecretLocation.HTML_BODY)
        assert secrets[0].snippet.startswith(VALID_SECRET)

    def test_clamps_context_at_end_of_text(self):
        text = f"leading context only, no room after the match {VALID_SECRET}"
        secrets = find_secrets(text, url="https://example.com", location=SecretLocation.HTML_BODY)
        assert secrets[0].snippet.endswith(VALID_SECRET)

    def test_finds_multiple_distinct_secrets(self):
        second_secret = "VISUALPING{fedcba9876543210}"
        text = f"{VALID_SECRET} some text between {second_secret}"
        secrets = find_secrets(text, url="https://example.com", location=SecretLocation.SCRIPT)
        assert {s.value for s in secrets} == {VALID_SECRET, second_secret}

    def test_sanitizes_newlines_and_tabs_in_snippet(self):
        text = f"before\n\t{VALID_SECRET}\t\nafter"
        secrets = find_secrets(text, url="https://example.com", location=SecretLocation.HTML_BODY)
        assert "\n" not in secrets[0].snippet
        assert "\t" not in secrets[0].snippet

    def test_sanitizes_non_breaking_space_in_snippet(self):
        text = f"before {VALID_SECRET} after"
        secrets = find_secrets(text, url="https://example.com", location=SecretLocation.HTML_BODY)
        assert " " not in secrets[0].snippet

    def test_collapses_repeated_whitespace_in_snippet(self):
        text = f"before      {VALID_SECRET}      after"
        secrets = find_secrets(text, url="https://example.com", location=SecretLocation.HTML_BODY)
        assert "      " not in secrets[0].snippet

    def test_rejects_lowercase_prefix(self):
        text = "visualping{0123456789abcdef}"
        secrets = find_secrets(text, url="https://example.com", location=SecretLocation.HTML_BODY)
        assert secrets == []

    def test_rejects_token_with_too_few_hex_characters(self):
        text = "VISUALPING{0123456789abcd}"
        secrets = find_secrets(text, url="https://example.com", location=SecretLocation.HTML_BODY)
        assert secrets == []

    def test_rejects_token_with_non_hex_characters(self):
        text = "VISUALPING{0123456789abcdzz}"
        secrets = find_secrets(text, url="https://example.com", location=SecretLocation.HTML_BODY)
        assert secrets == []

    def test_returns_empty_list_when_no_match(self):
        secrets = find_secrets(
            "nothing sensitive here", url="https://example.com", location=SecretLocation.HTML_BODY
        )
        assert secrets == []

    def test_returns_empty_list_for_empty_text(self):
        secrets = find_secrets("", url="https://example.com", location=SecretLocation.HTML_BODY)
        assert secrets == []
