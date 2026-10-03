import re
from pathlib import Path

import pytest

from serial_decoder.schema import SchemaError, load_schema

EXAMPLE = Path(__file__).parents[1] / "examples" / "telemetry.toml"


def test_loads_firmware_schema() -> None:
    messages = load_schema(EXAMPLE)

    assert sorted(messages) == [0x01, 0x02]
    status = messages[0x01]
    assert status.name == "status"
    assert status.payload_format == "<IB"
    assert (status.fields[0].unit, status.fields[0].scale) == ("ms", 1.0)
    assert messages[0x02].payload_format == "<III"


@pytest.mark.parametrize(
    ("text", "error"),
    [
        ('title = "no messages"', "no [[message]] tables"),
        (
            '[[message]]\nid = 1\nname = "a"\nfields = []\n'
            '[[message]]\nid = 1\nname = "b"\nfields = []',
            "duplicate message ID 0x01",
        ),
        ('[[message]]\nid = 256\nname = "a"\nfields = []', "id must be an integer from 0 to 255"),
        (
            '[[message]]\nid = 1\nname = "a"\nfields = [{ name = "x", type = "u24" }]',
            "field 'x' has unknown type 'u24'",
        ),
        (
            '[[message]]\nid = 1\nname = "a"\nfields = [{ name = "x", type = "u8", scael = 2 }]',
            "unknown key scael",
        ),
    ],
)
def test_rejects_invalid_schemas_naming_the_file(tmp_path: Path, text: str, error: str) -> None:
    path = tmp_path / "bad.toml"
    path.write_text(text)

    with pytest.raises(SchemaError, match=re.escape(error)) as raised:
        load_schema(path)
    assert str(path) in str(raised.value)
