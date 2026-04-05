"""Tests that verify the aeolus package ships all required data files.

These catch missing package-data declarations in pyproject.toml — the kind
of bug where tests pass against the source tree but the installed wheel is
broken because non-Python files were excluded from the build.

Run against an installed wheel (not the source tree) for the strongest
guarantee. See scripts/test_wheel.sh for the full workflow.
"""

from pathlib import Path

import aeolus
import aeolus.sources.sos as sos_module
import aeolus.viz.theme as theme_module


def _package_root() -> Path:
    """Return the installed package root directory."""
    return Path(aeolus.__file__).parent


class TestPackageDataFiles:
    """Verify that non-Python data files are present in the installed package."""

    def test_sos_mapping_json_exists(self):
        mapping_file = Path(sos_module.__file__).parent / "_sos_mapping.json"
        assert mapping_file.exists(), (
            f"_sos_mapping.json not found at {mapping_file}. "
            "Check [tool.setuptools.package-data] in pyproject.toml."
        )

    def test_sos_mapping_json_is_valid(self):
        import json

        mapping_file = Path(sos_module.__file__).parent / "_sos_mapping.json"
        if not mapping_file.exists():
            pytest.skip("mapping file missing (caught by test_sos_mapping_json_exists)")

        with open(mapping_file) as f:
            data = json.load(f)

        assert "_generated" in data, "mapping should have a _generated timestamp"
        # Should have at least the core UK networks
        for network in ("aurn", "saqn", "waqn", "ni", "aqe"):
            assert network in data, f"missing network '{network}' in SOS mapping"
            assert len(data[network]) > 0, f"network '{network}' has no station mappings"

    def test_font_files_exist(self):
        fonts_dir = Path(theme_module.__file__).parent / "fonts"
        expected_fonts = [
            "IBMPlexSans-Regular.ttf",
            "IBMPlexSans-Medium.ttf",
            "IBMPlexSans-SemiBold.ttf",
            "IBMPlexSans-Bold.ttf",
        ]
        for font in expected_fonts:
            font_path = fonts_dir / font
            assert font_path.exists(), (
                f"Font {font} not found at {font_path}. "
                "Check [tool.setuptools.package-data] in pyproject.toml."
            )

    def test_font_licence_exists(self):
        fonts_dir = Path(theme_module.__file__).parent / "fonts"
        ofl = fonts_dir / "OFL.txt"
        assert ofl.exists(), (
            f"Font licence OFL.txt not found at {ofl}. "
            "Check [tool.setuptools.package-data] in pyproject.toml."
        )


class TestNoStaleFiles:
    """Verify the package doesn't contain files removed in previous releases."""

    # Modules removed in v0.4.0
    REMOVED_MODULES = [
        "database_operations",
        "meteorology",
    ]

    def test_no_removed_modules(self):
        """Stale build/ dirs can leak deleted modules back into the wheel."""
        pkg_dir = _package_root()
        stale = []
        for name in self.REMOVED_MODULES:
            if (pkg_dir / f"{name}.py").exists():
                stale.append(name)
        assert stale == [], (
            f"Stale modules found in installed package: {stale}. "
            "Run `rm -rf build/ dist/` before rebuilding."
        )


class TestPackageCompleteness:
    """Verify that key modules are importable and functional."""

    def test_sos_module_loads_static_mapping(self):
        """SOS module should be able to load the static mapping (not fall back to API)."""
        mapping = sos_module._load_static_mapping()
        assert mapping is not None, (
            "_load_static_mapping() returned None — the JSON file is missing or corrupt. "
            "This means get_current() will fall back to slow live API matching."
        )

    def test_all_source_modules_importable(self):
        """All source modules should import without error."""
        from aeolus.sources import (
            airnow,
            airqo,
            breathe_london,
            regulatory,
            sensor_community,
            sos,
        )

    def test_list_sources_includes_sos_backends(self):
        """SOS backends should appear when include_all=True."""
        import importlib

        import aeolus.sources.sos

        # Re-trigger registration in case an earlier test cleared the registry
        importlib.reload(aeolus.sources.sos)

        all_sources = aeolus.list_sources(include_all=True)
        sos_sources = [s for s in all_sources if s.endswith("-SOS")]
        assert len(sos_sources) >= 5, (
            f"Expected at least 5 SOS backends, got {len(sos_sources)}: {sos_sources}"
        )
