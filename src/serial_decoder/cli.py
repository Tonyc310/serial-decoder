import argparse
import contextlib
import json
import sys
from collections.abc import Iterable
from contextlib import AbstractContextManager
from pathlib import Path
from typing import BinaryIO

from serial_decoder.decode import DecodedMessage, DecodeError, decode_packet
from serial_decoder.framing import FrameError, FrameSplitter, cobs_decode
from serial_decoder.schema import Field, Message, SchemaError, load_schema

EXIT_OK = 0
EXIT_BAD_FRAMES = 1
EXIT_ERROR = 2  # also what argparse uses for usage errors
CHUNK_SIZE = 4096


def main(argv: list[str] | None = None) -> int:
    """Runs the decoder and returns the process exit code."""
    args = _parser().parse_args(argv)
    try:
        messages = load_schema(args.schema)
        with _open_input(args.input) as stream:
            chunks = iter(lambda: stream.read(CHUNK_SIZE), b"")
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
    parser.add_argument("input", nargs="?", default="-", help="capture file (default: stdin)")
    parser.add_argument("--schema", type=Path, required=True, help="TOML file describing messages")
    parser.add_argument("--json", action="store_true", help="print JSON Lines instead of text")
    return parser


def _open_input(path: str) -> AbstractContextManager[BinaryIO]:
    if path == "-":
        # nullcontext so leaving the `with` doesn't close stdin.
        return contextlib.nullcontext(sys.stdin.buffer)
    return open(path, "rb")


def _decode_stream(chunks: Iterable[bytes], messages: dict[int, Message], json_lines: bool) -> int:
    splitter = FrameSplitter()
    width = max(len(message.name) for message in messages.values())
    decoded = bad = 0

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
