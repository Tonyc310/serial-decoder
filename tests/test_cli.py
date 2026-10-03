import io
import sys
from pathlib import Path

import pytest

from serial_decoder.cli import main

EXAMPLES = Path(__file__).parents[1] / "examples"
SCHEMA = str(EXAMPLES / "telemetry.toml")
CAPTURE = EXAMPLES / "telemetry.bin"


@pytest.mark.parametrize(
    ("options", "first_line"),
    [
        ([], "status         uptime=1000 ms  led=0"),
        (["--json"], '{"id": 1, "message": "status", "values": {"uptime": 1000, "led": 0}}'),
    ],
)
def test_decodes_capture_as_text_or_json_lines(
    capsys: pytest.CaptureFixture[str], options: list[str], first_line: str
) -> None:
    assert main(["--schema", SCHEMA, str(CAPTURE), *options]) == 0

    out, err = capsys.readouterr()
    assert len(out.splitlines()) == 10
    assert out.splitlines()[0] == first_line
    assert err == "10 frames decoded, 0 bad\n"


def test_reports_bad_frames_from_stdin_and_keeps_going(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    data = bytearray(CAPTURE.read_bytes())
    data[3] ^= 0xFF  # corrupt the first frame's uptime
    data += b"\x04\x01"  # and cut the stream off mid-frame
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(bytes(data))))

    assert main(["--schema", SCHEMA]) == 1

    out, err = capsys.readouterr()
    assert len(out.splitlines()) == 9
    assert err.startswith("frame 1: CRC mismatch")
    assert err.endswith("9 frames decoded, 1 bad, 2 bytes of an unfinished frame at the end\n")


def test_schema_errors_exit_with_status_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "missing.toml"

    assert main(["--schema", str(missing), str(CAPTURE)]) == 2
    assert str(missing) in capsys.readouterr().err
