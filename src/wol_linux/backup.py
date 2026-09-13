from __future__ import annotations

import json
import secrets
from base64 import b64decode, b64encode
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from .i18n import install_translation_data, tr as _, user_translations
from .models import Computer
from .settings import ACCENTS, COLUMN_WIDTH_DEFAULTS, HEX_COLOR, PALETTE_KEYS, THEMES, AppSettings

BACKUP_FORMAT = "wake-on-lan-for-linux-backup"
BACKUP_VERSION = 1
ENCRYPTED_BACKUP_FORMAT = "wake-on-lan-for-linux-encrypted-backup"
ENCRYPTED_BACKUP_VERSION = 1
_SALT_LENGTH = 16
_NONCE_LENGTH = 12
_KEY_LENGTH = 32
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1


class BackupPasswordRequired(ValueError):
    """Raised when an encrypted backup needs a password before it can load."""


@dataclass(slots=True)
class BackupData:
    settings: AppSettings
    computers: list[Computer]
    translations: dict[str, bytes]


def _payload(
    settings: AppSettings,
    computers: list[Computer],
    translations: dict[str, bytes] | None = None,
) -> dict[str, object]:
    return {
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
            for code, data in (
                translations if translations is not None else user_translations()
            ).items()
        },
    }


def _write_text(path: str | Path, content: str) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(destination)


def _derive_key(password: str, salt: bytes) -> bytes:
    if not password:
        raise ValueError(_("La password del backup non può essere vuota"))
    return Scrypt(
        salt=salt,
        length=_KEY_LENGTH,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
    ).derive(password.encode("utf-8"))


def export_backup(
    path: str | Path,
    settings: AppSettings,
    computers: list[Computer],
    translations: dict[str, bytes] | None = None,
) -> None:
    _write_text(
        path,
        json.dumps(
            _payload(settings, computers, translations), ensure_ascii=False, indent=2
        )
        + "\n",
    )


def export_encrypted_backup(
    path: str | Path,
    settings: AppSettings,
    computers: list[Computer],
    password: str,
    translations: dict[str, bytes] | None = None,
) -> None:
    """Write a portable password-protected backup envelope.

    The payload remains JSON internally, while the exported file only exposes
    the algorithm parameters and authenticated ciphertext.  The password is
    never stored in the file.
    """
    salt = secrets.token_bytes(_SALT_LENGTH)
    nonce = secrets.token_bytes(_NONCE_LENGTH)
    key = _derive_key(password, salt)
    plaintext = json.dumps(
        _payload(settings, computers, translations),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
    envelope = {
        "format": ENCRYPTED_BACKUP_FORMAT,
        "version": ENCRYPTED_BACKUP_VERSION,
        "cipher": "AES-256-GCM",
        "kdf": "scrypt",
        "scrypt": {"n": _SCRYPT_N, "r": _SCRYPT_R, "p": _SCRYPT_P},
        "salt": b64encode(salt).decode("ascii"),
        "nonce": b64encode(nonce).decode("ascii"),
        "ciphertext": b64encode(ciphertext).decode("ascii"),
    }
    _write_text(path, json.dumps(envelope, ensure_ascii=False, indent=2) + "\n")


def load_backup(path: str | Path, password: str | None = None) -> BackupData:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError) as exc:
        raise ValueError(
            _("Il file di backup non è leggibile o non contiene JSON valido")
        ) from exc
    if not isinstance(payload, dict):
        raise ValueError(_("Il file di backup non contiene un oggetto JSON valido"))
    if payload.get("format") == ENCRYPTED_BACKUP_FORMAT:
        if password is None:
            raise BackupPasswordRequired(_("Questo backup è cifrato e richiede una password"))
        try:
            if payload.get("version") != ENCRYPTED_BACKUP_VERSION:
                raise ValueError
            salt = b64decode(str(payload["salt"]), validate=True)
            nonce = b64decode(str(payload["nonce"]), validate=True)
            ciphertext = b64decode(str(payload["ciphertext"]), validate=True)
            encrypted_payload = AESGCM(_derive_key(password, salt)).decrypt(
                nonce,
                ciphertext,
                None,
            )
            payload = json.loads(encrypted_payload.decode("utf-8"))
        except (
            KeyError,
            TypeError,
            ValueError,
            InvalidTag,
            UnicodeError,
            json.JSONDecodeError,
        ) as exc:
            raise ValueError(_("Password del backup errata o file cifrato non valido")) from exc
    if payload.get("format") != BACKUP_FORMAT or payload.get("version") != BACKUP_VERSION:
        raise ValueError(_("Formato o versione del backup non supportati"))

    raw_settings = payload.get("settings", {})
    if not isinstance(raw_settings, dict):
        raise ValueError(_("Le impostazioni nel backup non sono valide"))
    raw_colors = raw_settings.get("custom_colors", {})
    custom_colors = (
        {
            str(key): str(value).upper()
            for key, value in raw_colors.items()
            if key in PALETTE_KEYS and isinstance(value, str) and HEX_COLOR.fullmatch(value)
        }
        if isinstance(raw_colors, dict)
        else {}
    )
    raw_widths = raw_settings.get("column_widths", {})
    column_widths = dict(COLUMN_WIDTH_DEFAULTS)
    if isinstance(raw_widths, dict):
        for key, value in raw_widths.items():
            if key not in column_widths:
                continue
            try:
                column_widths[key] = max(4, min(60, int(value)))
            except (TypeError, ValueError):
                continue
    try:
        font_size = max(0, min(32, int(raw_settings.get("font_size", 0))))
    except (TypeError, ValueError):
        font_size = 0
    settings = AppSettings(
        theme=raw_settings.get("theme") if raw_settings.get("theme") in THEMES else "system",
        accent=raw_settings.get("accent") if raw_settings.get("accent") in ACCENTS else "ubuntu",
        language=str(raw_settings.get("language", "system")),
        custom_colors=custom_colors,
        font_family=str(raw_settings.get("font_family", "")).strip(),
        font_size=font_size,
        column_widths=column_widths,
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
