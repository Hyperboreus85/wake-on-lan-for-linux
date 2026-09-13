from __future__ import annotations

import json
from base64 import b64decode, b64encode
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from .i18n import install_translation_data, tr as _, user_translations
from .models import Computer
from .settings import ACCENTS, THEMES, AppSettings

BACKUP_FORMAT = "wake-on-lan-for-linux-backup"
BACKUP_VERSION = 1


@dataclass(slots=True)
class BackupData:
    settings: AppSettings
    computers: list[Computer]
    translations: dict[str, bytes]


def export_backup(
    path: str | Path,
    settings: AppSettings,
    computers: list[Computer],
    translations: dict[str, bytes] | None = None,
) -> None:
    destination = Path(path)
    payload = {
        "format": BACKUP_FORMAT,
        "version": BACKUP_VERSION,
        "exported_at": datetime.now(UTC).isoformat(),
        "settings": asdict(settings),
        "computers": [
            {key: value for key, value in asdict(computer).items() if key != "id"}
            for computer in computers
        ],
        "translations": {
            code: b64encode(data).decode("ascii")
            for code, data in (translations if translations is not None else user_translations()).items()
        },
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)


def load_backup(path: str | Path) -> BackupData:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError(_("Il file di backup non è leggibile o non contiene JSON valido")) from exc
    if not isinstance(payload, dict):
        raise ValueError(_("Il file di backup non contiene un oggetto JSON valido"))
    if payload.get("format") != BACKUP_FORMAT or payload.get("version") != BACKUP_VERSION:
        raise ValueError(_("Formato o versione del backup non supportati"))

    raw_settings = payload.get("settings", {})
    if not isinstance(raw_settings, dict):
        raise ValueError(_("Le impostazioni nel backup non sono valide"))
    settings = AppSettings(
        theme=raw_settings.get("theme") if raw_settings.get("theme") in THEMES else "system",
        accent=raw_settings.get("accent") if raw_settings.get("accent") in ACCENTS else "ubuntu",
        language=str(raw_settings.get("language", "system")),
    )

    allowed_fields = set(Computer.__dataclass_fields__) - {"id"}
    computers: list[Computer] = []
    try:
        raw_computers = payload.get("computers", [])
        if not isinstance(raw_computers, list):
            raise TypeError
        for item in raw_computers:
            values = {key: value for key, value in item.items() if key in allowed_fields}
            values["wol_port"] = int(values.get("wol_port", 9))
            computers.append(Computer(**values))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError(_("Il backup contiene una macchina non valida")) from exc

    translations: dict[str, bytes] = {}
    try:
        raw_translations = payload.get("translations", {})
        if not isinstance(raw_translations, dict):
            raise TypeError
        translations = {
            str(code): b64decode(str(data), validate=True)
            for code, data in raw_translations.items()
        }
    except (TypeError, ValueError) as exc:
        raise ValueError(_("Il backup contiene traduzioni non valide")) from exc
    return BackupData(settings=settings, computers=computers, translations=translations)


def restore_translations(translations: dict[str, bytes]) -> int:
    for code, data in translations.items():
        install_translation_data(data, code)
    return len(translations)
