import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# struct codes for each field type; every field is little-endian.
FIELD_TYPES = {"u8": "B", "i8": "b", "u16": "H", "i16": "h", "u32": "I", "i32": "i", "f32": "f"}


class SchemaError(ValueError):
    """A schema file that can't be read or doesn't describe valid messages."""


@dataclass(frozen=True)
class Field:
    name: str
    type: str
    scale: float = 1.0  # shown value = raw value * scale
    unit: str = ""


@dataclass(frozen=True)
class Message:
    id: int
    name: str
    fields: tuple[Field, ...]

    @property
    def payload_format(self) -> str:
        """struct format of the payload: the fields, little-endian, in schema order."""
        return "<" + "".join(FIELD_TYPES[field.type] for field in self.fields)


def load_schema(path: Path) -> dict[int, Message]:
    """Reads and validates a schema file; returns its messages by ID."""
    try:
        # tomllib only reads binary files, so it can check the encoding is UTF-8 itself.
        with path.open("rb") as file:
            document = tomllib.load(file)
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise SchemaError(f"{path}: {error}") from error

    # Each [[message]] table arrives as one dict in this list.
    entries = document.get("message")
    if not isinstance(entries, list) or not entries:
        raise SchemaError(f"{path}: no [[message]] tables")

    messages: dict[int, Message] = {}
    for number, entry in enumerate(entries, start=1):
        message = _parse_message(entry, f"{path}: message {number}")
        if message.id in messages:
            raise SchemaError(f"{path}: duplicate message ID {message.id:#04x}")
        messages[message.id] = message
    return messages


def _parse_message(entry: object, where: str) -> Message:
    table = _table(entry, where, required={"id", "name", "fields"})
    name = _string(table, "name", where)
    where = f"{where} ({name})"  # later errors name the message too
    message_id = table["id"]
    # type() rather than isinstance(): bool is an int subclass, so `id = true` would pass as 1.
    if type(message_id) is not int or not 0 <= message_id <= 255:
        raise SchemaError(f"{where}: id must be an integer from 0 to 255")
    if not isinstance(table["fields"], list):
        raise SchemaError(f"{where}: fields must be a list")

    fields = tuple(_parse_field(field, where) for field in table["fields"])
    names = [field.name for field in fields]
    if len(set(names)) != len(names):
        raise SchemaError(f"{where}: duplicate field names")
    return Message(message_id, name, fields)


def _parse_field(entry: object, where: str) -> Field:
    table = _table(entry, where, required={"name", "type"}, optional={"scale", "unit"})
    name = _string(table, "name", where)
    field_type = _string(table, "type", where)
    if field_type not in FIELD_TYPES:
        expected = ", ".join(FIELD_TYPES)
        raise SchemaError(f"{where}: field {name!r} has unknown type {field_type!r} ({expected})")
    scale = table.get("scale", 1.0)
    # TOML integers are fine as a scale; type() again keeps booleans out.
    if type(scale) not in (int, float):
        raise SchemaError(f"{where}: field {name!r} scale must be a number")
    unit = table.get("unit", "")
    if not isinstance(unit, str):
        raise SchemaError(f"{where}: field {name!r} unit must be a string")
    return Field(name, field_type, float(scale), unit)


def _table(
    entry: object, where: str, required: set[str], optional: frozenset[str] | set[str] = frozenset()
) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise SchemaError(f"{where}: expected a table")
    if missing := required - entry.keys():
        raise SchemaError(f"{where}: missing {', '.join(sorted(missing))}")
    # A misspelled key like `scael` would otherwise be ignored and its default used silently.
    if unknown := entry.keys() - required - optional:
        raise SchemaError(f"{where}: unknown key {', '.join(sorted(unknown))}")
    return entry


def _string(table: dict[str, Any], key: str, where: str) -> str:
    value = table[key]
    if not isinstance(value, str) or not value:
        raise SchemaError(f"{where}: {key} must be a non-empty string")
    return value
