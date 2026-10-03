import struct
from pathlib import Path

import pytest

from serial_decoder.crc import crc16_ccitt
from serial_decoder.decode import DecodeError, decode_packet
from serial_decoder.framing import FrameSplitter, cobs_decode
from serial_decoder.schema import Field, Message, load_schema

EXAMPLES = Path(__file__).parents[1] / "examples"
SENSOR = Message(
    id=0x03,
    name="sensor",
    fields=(Field("temperature", "i16", scale=0.01, unit="°C"), Field("pressure", "f32")),
)


def packet(body: bytes) -> bytes:
    return body + crc16_ccitt(body).to_bytes(2, "little")


def test_decodes_firmware_capture() -> None:
    messages = load_schema(EXAMPLES / "telemetry.toml")
    frames = FrameSplitter().feed((EXAMPLES / "telemetry.bin").read_bytes())
    decoded = [decode_packet(cobs_decode(frame), messages) for frame in frames]

    statuses = [d.values for d in decoded if d.message.name == "status"]
    assert [s["uptime"] for s in statuses] == [1000, 2000, 3000, 4000, 5000]
    assert [s["led"] for s in statuses] == [0, 0, 1, 1, 1]
    assert decoded[-1].values == {"rx_bytes": 13, "tx_bytes": 100, "rx_dropped": 0}


def test_applies_scale_to_signed_and_float_fields() -> None:
    body = struct.pack("<Bhf", 0x03, -1234, 101.5)

    values = decode_packet(packet(body), {0x03: SENSOR}).values

    assert values == {"temperature": pytest.approx(-12.34), "pressure": 101.5}


@pytest.mark.parametrize(
    ("data", "error"),
    [
        (b"\x03\x00", "packet too short"),
        (struct.pack("<Bhf", 0x03, 0, 0.0) + b"\x00\x00", "CRC mismatch"),
        (packet(b"\x09"), "unknown message ID 0x09"),
        (packet(struct.pack("<Bh", 0x03, 0)), "sensor: payload is 2 bytes, expected 6"),
    ],
)
def test_rejects_bad_packets(data: bytes, error: str) -> None:
    with pytest.raises(DecodeError, match=error):
        decode_packet(data, {0x03: SENSOR})
