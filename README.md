# serial-decoder

Command-line tool that turns the binary packets an embedded device sends over a serial port into readable text or JSON. Message layouts come from a small TOML schema, so supporting a new device takes a schema file, not new code.

It's the companion to [stm32-uart-driver](https://github.com/Tonyc310/stm32-uart-driver): the example capture and schema come from that firmware's telemetry port, recorded in the Renode simulator.

## Features

- Reads from a serial port, a capture file, or stdin
- COBS framing with a CRC-16/CCITT-FALSE check on every packet
- Integer and float fields with scaling and units, defined in TOML
- Text output for reading, JSON Lines for piping into other tools
- Corrupt packets are reported and counted; decoding carries on

## Install

Requires Python 3.11+.

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
```

## Usage

```bash
serial-decoder --schema examples/telemetry.toml examples/telemetry.bin
serial-decoder --schema examples/telemetry.toml --port /dev/ttyUSB0 --baud 115200
serial-decoder --schema examples/telemetry.toml --json examples/telemetry.bin | jq .
```

## Packet format

Each packet is COBS-encoded and terminated by a `0x00` byte. Once decoded:

| Bytes | Field |
|---|---|
| 1 | Message ID |
| n | Payload: little-endian fields in schema order |
| 2 | CRC-16/CCITT-FALSE over ID and payload, little-endian |

## Schema

```toml
[[message]]
id = 0x01
name = "environment"
fields = [
  { name = "temperature", type = "i16", scale = 0.01, unit = "°C" },
  { name = "humidity",    type = "u16", scale = 0.01, unit = "%" },
]
```

Field types: `u8`, `i8`, `u16`, `i16`, `u32`, `i32`, `f32`.

## Test

```bash
pytest
ruff check . && ruff format --check . && mypy
```

## License

MIT
