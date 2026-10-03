import struct
from dataclasses import dataclass

from serial_decoder.crc import crc16_ccitt
from serial_decoder.schema import Message

CRC_SIZE = 2


class DecodeError(ValueError):
    """A packet that fails its CRC or doesn't match the schema."""


@dataclass(frozen=True)
class DecodedMessage:
    message: Message
    values: dict[str, int | float]  # in schema order, scale applied


def decode_packet(packet: bytes, messages: dict[int, Message]) -> DecodedMessage:
    """Checks a COBS-decoded packet's CRC and decodes it with the matching message."""
    if len(packet) < 1 + CRC_SIZE:
        raise DecodeError(f"packet too short ({len(packet)} bytes)")
    body = packet[:-CRC_SIZE]
    received = int.from_bytes(packet[-CRC_SIZE:], "little")
    # CRC first, so a corrupted packet is reported as corrupt rather than as an unknown message.
    if (computed := crc16_ccitt(body)) != received:
        raise DecodeError(f"CRC mismatch: packet says {received:#06x}, data gives {computed:#06x}")

    message = messages.get(body[0])
    if message is None:
        raise DecodeError(f"unknown message ID {body[0]:#04x}")
    payload = body[1:]
    # struct.unpack would also reject a wrong length, but without saying which message or why.
    if len(payload) != (expected := struct.calcsize(message.payload_format)):
        raise DecodeError(f"{message.name}: payload is {len(payload)} bytes, expected {expected}")

    raw = struct.unpack(message.payload_format, payload)
    values = {
        field.name: _scaled(value, field.scale)
        for field, value in zip(message.fields, raw, strict=True)
    }
    return DecodedMessage(message, values)


def _scaled(raw: int | float, scale: float) -> int | float:
    # Unscaled integers stay integers, so an uptime prints as 1000 rather than 1000.0.
    return raw if scale == 1.0 else raw * scale
