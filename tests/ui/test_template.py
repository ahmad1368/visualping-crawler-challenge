"""Unit tests for the base HTML report template: template.load_template."""

from ui.template import REQUIRED_PLACEHOLDERS, TEMPLATE_PATH, load_template


class TestLoadTemplate:
    """Success and failure scenarios for load_template."""

    def test_loads_the_real_template_file(self):
        content = load_template()
        assert content != ""

    def test_returns_empty_string_for_missing_file(self, tmp_path):
        content = load_template(path=tmp_path / "does_not_exist.html")
        assert content == ""

    def test_returns_empty_string_for_missing_file_default_path_unaffected(self, tmp_path):
        missing = tmp_path / "nested" / "missing.html"
        assert load_template(path=missing) == ""
        assert load_template() != ""


class TestTemplateContract:
    """Structural checks on the real template.html content."""

    def test_defines_every_required_placeholder(self):
        content = load_template()
        for placeholder in REQUIRED_PLACEHOLDERS:
            assert placeholder in content, f"Missing placeholder: {placeholder}"

    def test_references_tailwind_css(self):
        content = load_template()
        assert "tailwindcss" in content.lower()

    def test_references_lucide_icons(self):
        content = load_template()
        assert "lucide" in content.lower()

    def test_references_vis_network(self):
        content = load_template()
        assert "vis-network" in content.lower()

    def test_includes_visualping_branding(self):
        content = load_template()
        assert "Visualping" in content

    def test_defines_kpi_section(self):
        content = load_template()
        assert "Key Metrics" in content

    def test_defines_secrets_table(self):
        content = load_template()
        assert "<table" in content

    def test_template_path_points_to_expected_location(self):
        assert TEMPLATE_PATH.parts[-2:] == ("templates", "template.html")
        assert TEMPLATE_PATH.parent.parent.name == "ui"
