import argparse
import contextlib
import json
import sys
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import BinaryIO

import serial

from serial_decoder.decode import DecodedMessage, DecodeError, decode_packet
from serial_decoder.framing import FrameError, FrameSplitter, cobs_decode
from serial_decoder.schema import Field, Message, SchemaError, load_schema

EXIT_OK = 0
EXIT_BAD_FRAMES = 1
EXIT_ERROR = 2  # also what argparse uses for usage errors
CHUNK_SIZE = 4096
READ_TIMEOUT_S = 0.1


def main(argv: list[str] | None = None) -> int:
    """Runs the decoder and returns the process exit code."""
    args = _parser().parse_args(argv)
    try:
        messages = load_schema(args.schema)
        with _open_source(args) as chunks:
            return _decode_stream(chunks, messages, args.json)
    except (SchemaError, OSError) as error:
        print(f"serial-decoder: {error}", file=sys.stderr)
        return EXIT_ERROR


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="serial-decoder",
        description="Decode COBS-framed, CRC-checked binary packets from an embedded device.",
        epilog="Exit status: 0 if every frame decoded, 1 if some were bad, 2 on any other error.",
    )
    parser.add_argument("--schema", type=Path, required=True, help="TOML file describing messages")
    parser.add_argument("--json", action="store_true", help="print JSON Lines instead of text")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("input", nargs="?", default="-", help="capture file (default: stdin)")
    source.add_argument("--port", help="serial device or pyserial URL, e.g. socket://host:port")
    parser.add_argument("--baud", type=int, default=115200, help="baud rate (default: 115200)")
    return parser


@contextlib.contextmanager
def _open_source(args: argparse.Namespace) -> Iterator[Iterable[bytes]]:
    if args.port:
        # serial_for_url also accepts URLs, so a simulator's TCP UART works like a device.
        with serial.serial_for_url(args.port, baudrate=args.baud, timeout=READ_TIMEOUT_S) as port:
            yield _port_chunks(port)
    elif args.input == "-":
        yield _stream_chunks(sys.stdin.buffer)
    else:
        with open(args.input, "rb") as file:
            yield _stream_chunks(file)


def _stream_chunks(stream: BinaryIO) -> Iterator[bytes]:
    return iter(lambda: stream.read(CHUNK_SIZE), b"")


def _port_chunks(port: serial.SerialBase) -> Iterator[bytes]:
    while True:
        # A read returns whatever arrived within the timeout; empty just means nothing yet.
        if chunk := port.read(CHUNK_SIZE):
            yield chunk


def _decode_stream(chunks: Iterable[bytes], messages: dict[int, Message], json_lines: bool) -> int:
    splitter = FrameSplitter()
    width = max(len(message.name) for message in messages.values())
    decoded = bad = 0

    # Ctrl-C ends a live session the way end-of-file ends a capture.
    with contextlib.suppress(KeyboardInterrupt):
        for chunk in chunks:
            for frame in splitter.feed(chunk):
                try:
                    message = decode_packet(cobs_decode(frame), messages)
                except (FrameError, DecodeError) as error:
                    bad += 1
                    print(f"frame {decoded + bad}: {error}", file=sys.stderr)
                    continue
                decoded += 1
                # Flushed per line so piped output keeps up with a live device.
                print(_as_json(message) if json_lines else _as_text(message, width), flush=True)

    summary = f"{decoded} frames decoded, {bad} bad"
    if splitter.pending:
        summary += f", {splitter.pending} bytes of an unfinished frame at the end"
    print(summary, file=sys.stderr)
    return EXIT_BAD_FRAMES if bad or splitter.pending else EXIT_OK


def _as_text(decoded: DecodedMessage, width: int) -> str:
    fields = (_field_text(field, decoded.values[field.name]) for field in decoded.message.fields)
    return f"{decoded.message.name:<{width}}  {'  '.join(fields)}"


def _field_text(field: Field, value: int | float) -> str:
    text = f"{field.name}={value:g}" if isinstance(value, float) else f"{field.name}={value}"
    return f"{text} {field.unit}" if field.unit else text


def _as_json(decoded: DecodedMessage) -> str:
    message = decoded.message
    return json.dumps({"id": message.id, "message": message.name, "values": decoded.values})
