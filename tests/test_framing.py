from pathlib import Path

import pytest

from serial_decoder.crc import crc16_ccitt
from serial_decoder.framing import FrameError, FrameSplitter, cobs_decode

CAPTURE = Path(__file__).parents[1] / "examples" / "telemetry.bin"


def test_decodes_firmware_capture_read_one_byte_at_a_time() -> None:
    splitter = FrameSplitter()
    packets = []
    for byte in CAPTURE.read_bytes():
        packets += [cobs_decode(frame) for frame in splitter.feed(bytes([byte]))]

    assert len(packets) == 10
    assert splitter.pending == 0
    # status: ID 1, uptime 1000 ms, LED off, then the CRC little-endian.
    assert packets[0] == bytes.fromhex("01 e8 03 00 00 00 4d e9")
    for packet in packets:
        assert crc16_ccitt(packet[:-2]) == int.from_bytes(packet[-2:], "little")


def test_decodes_full_254_byte_blocks() -> None:
    data = bytes(range(1, 255))
    encoded = b"\xff" + data

    assert cobs_decode(encoded) == data
    # The firmware's encoder ends such a frame with an extra empty block.
    assert cobs_decode(encoded + b"\x01") == data


@pytest.mark.parametrize("frame", [b"\x05\x11\x22", b"\x03\x11\x00"])
def test_rejects_malformed_frames(frame: bytes) -> None:
    with pytest.raises(FrameError):
        cobs_decode(frame)
