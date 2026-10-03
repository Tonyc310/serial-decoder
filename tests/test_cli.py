import io
import sys
from pathlib import Path

import pytest
import serial

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


class FakePort:
    """Hands out reads like pyserial, then raises KeyboardInterrupt as if Ctrl-C was pressed."""

    def __init__(self, reads: list[bytes]) -> None:
        self._reads = reads

    def __enter__(self) -> "FakePort":
        return self

    def __exit__(self, *exc: object) -> None:
        pass

    def read(self, size: int) -> bytes:
        if not self._reads:
            raise KeyboardInterrupt
        return self._reads.pop(0)


def test_decodes_a_live_port_until_ctrl_c(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    data = CAPTURE.read_bytes()
    port = FakePort([data[:50], b"", data[50:]])  # b"" is a read that timed out
    opened: list[tuple[str, int]] = []

    def open_port(url: str, baudrate: int, timeout: float) -> FakePort:
        opened.append((url, baudrate))
        return port

    monkeypatch.setattr(serial, "serial_for_url", open_port)

    assert main(["--schema", SCHEMA, "--port", "socket://localhost:3456", "--baud", "9600"]) == 0

    assert opened == [("socket://localhost:3456", 9600)]
    out, err = capsys.readouterr()
    assert len(out.splitlines()) == 10
    assert err == "10 frames decoded, 0 bad\n"
