import unittest

from tempfile import TemporaryDirectory

from wol_linux.settings import AppSettings


class SettingsTests(unittest.TestCase):
    def test_settings_round_trip(self) -> None:
        with TemporaryDirectory() as directory:
            path = f"{directory}/settings.json"
            expected = AppSettings(theme="dark", accent="purple", language="en")
            expected.save(path)
            self.assertEqual(AppSettings.load(path), expected)

    def test_invalid_values_fall_back_to_defaults(self) -> None:
        with TemporaryDirectory() as directory:
            path = f"{directory}/settings.json"
            with open(path, "w", encoding="utf-8") as stream:
                stream.write('{"theme":"invalid","accent":"invalid"}')
            self.assertEqual(AppSettings.load(path), AppSettings())

    def test_transparent_legacy_colors_are_discarded(self) -> None:
        with TemporaryDirectory() as directory:
            path = f"{directory}/settings.json"
            with open(path, "w", encoding="utf-8") as stream:
                stream.write(
                    '{"custom_colors": {'
                    '"background_primary":"#00000000", '
                    '"background_secondary":"#00000000"}}'
                )
            self.assertEqual(AppSettings.load(path).custom_colors, {})

    def test_custom_palette_and_font_round_trip(self) -> None:
        with TemporaryDirectory() as directory:
            path = f"{directory}/settings.json"
            expected = AppSettings(
                accent="blue",
                custom_colors={"accent": "#123456", "button": "#ABCDEF"},
                font_family="Atkinson Hyperlegible",
            )
            expected.save(path)
            self.assertEqual(AppSettings.load(path), expected)
