from __future__ import annotations

import gettext
import io
import locale
import os
import re
import struct
from pathlib import Path

DOMAIN = "wol-linux"
_LANGUAGE_CODE = re.compile(r"^[a-z]{2,3}(?:_[A-Z]{2})?$")
_translation: gettext.NullTranslations = gettext.NullTranslations()


def bundled_locale_dir() -> Path:
    return Path(__file__).resolve().parent / "locale"


def user_locale_dir() -> Path:
    data_home = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return data_home / "wake-on-lan-for-linux" / "locale"


def effective_language(language: str) -> str:
    if language != "system":
        return language
    system_language = locale.getlocale()[0] or os.environ.get("LANG", "it")
    return system_language.split(".", maxsplit=1)[0] or "it"


def configure(language: str) -> None:
    global _translation
    code = effective_language(language)
    if code.startswith("it"):
        _translation = gettext.NullTranslations()
        return
    for locale_dir in (user_locale_dir(), bundled_locale_dir()):
        try:
            _translation = gettext.translation(DOMAIN, locale_dir, languages=[code])
            return
        except OSError:
            continue
    _translation = gettext.NullTranslations()


def tr(message: str) -> str:
    return _translation.gettext(message)


def available_languages() -> list[tuple[str, str]]:
    languages = [("system", tr("Lingua del sistema")), ("it", "Italiano"), ("en", "English")]
    known = {code for code, _label in languages}
    for locale_dir in (bundled_locale_dir(), user_locale_dir()):
        if not locale_dir.exists():
            continue
        for child in sorted(locale_dir.iterdir()):
            catalog = child / "LC_MESSAGES" / f"{DOMAIN}.mo"
            if child.name not in known and catalog.is_file():
                languages.append((child.name, child.name))
                known.add(child.name)
    return languages


def install_translation(source: str | Path, language_code: str | None = None) -> str:
    source_path = Path(source)
    code = language_code or source_path.stem
    try:
        data = source_path.read_bytes()
    except OSError as exc:
        raise ValueError(tr("Il catalogo di traduzione .mo non è valido")) from exc
    install_translation_data(data, code)
    return code


def install_translation_data(data: bytes, language_code: str) -> None:
    code = language_code
    if not _LANGUAGE_CODE.fullmatch(code):
        raise ValueError(tr("Rinomina il file con il codice lingua, per esempio fr.mo o de_DE.mo"))
    try:
        gettext.GNUTranslations(io.BytesIO(data))
    except (OSError, EOFError, UnicodeError, struct.error) as exc:
        raise ValueError(tr("Il catalogo di traduzione .mo non è valido")) from exc
    destination = user_locale_dir() / code / "LC_MESSAGES" / f"{DOMAIN}.mo"
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(".tmp")
    temporary.write_bytes(data)
    temporary.replace(destination)


def user_translations() -> dict[str, bytes]:
    catalogs: dict[str, bytes] = {}
    locale_dir = user_locale_dir()
    if not locale_dir.exists():
        return catalogs
    for child in locale_dir.iterdir():
        catalog = child / "LC_MESSAGES" / f"{DOMAIN}.mo"
        if _LANGUAGE_CODE.fullmatch(child.name) and catalog.is_file():
            try:
                catalogs[child.name] = catalog.read_bytes()
            except OSError:
                continue
    return catalogs
