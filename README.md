# serial-decoder

[![CI](https://github.com/Tonyc310/serial-decoder/actions/workflows/ci.yml/badge.svg)](https://github.com/Tonyc310/serial-decoder/actions/workflows/ci.yml)

Command-line tool that turns the binary packets an embedded device sends over a serial port into readable text or JSON. Message layouts come from a small TOML schema, so supporting a new device takes a schema file, not new code.

It's the companion to [stm32-uart-driver](https://github.com/Tonyc310/stm32-uart-driver): the example capture and schema come from that firmware's telemetry port, recorded in the Renode simulator.

## Features

- Reads from a serial port or any pyserial URL (such as `socket://` to a simulator), a capture file, or stdin
- COBS framing with a CRC-16/CCITT-FALSE check on every packet
- Integer and float fields with scaling and units, defined in TOML
- Text output for reading, JSON Lines for piping into other tools
- Corrupt and cut-off packets are reported and counted; decoding carries on

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

Decoding the example capture:

```
$ serial-decoder --schema examples/telemetry.toml examples/telemetry.bin
status         uptime=1000 ms  led=0
console_stats  rx_bytes=0  tx_bytes=34  rx_dropped=0
status         uptime=2000 ms  led=0
console_stats  rx_bytes=0  tx_bytes=34  rx_dropped=0
status         uptime=3000 ms  led=1
console_stats  rx_bytes=13  tx_bytes=100  rx_dropped=0
status         uptime=4000 ms  led=1
console_stats  rx_bytes=13  tx_bytes=100  rx_dropped=0
status         uptime=5000 ms  led=1
console_stats  rx_bytes=13  tx_bytes=100  rx_dropped=0
10 frames decoded, 0 bad
```

As JSON Lines:

```
{"id": 1, "message": "status", "values": {"uptime": 1000, "led": 0}}
{"id": 2, "message": "console_stats", "values": {"rx_bytes": 0, "tx_bytes": 34, "rx_dropped": 0}}
```

Problems go to stderr without stopping the decode, such as a capture cut off mid-frame:

```
$ head -c 100 examples/telemetry.bin | serial-decoder --schema examples/telemetry.toml
...
7 frames decoded, 0 bad, 9 bytes of an unfinished frame at the end
```

Exit status is 0 when every frame decodes, 1 when any frame was corrupt or cut off, and 2 for a bad schema, file, or port.

## Live from the simulator

From a built [stm32-uart-driver](https://github.com/Tonyc310/stm32-uart-driver), run the firmware in Renode with its telemetry UART on TCP port 3456:

```bash
renode -e 'include @tests/sim/stm32f4.resc; emulation CreateServerSocketTerminal 3456 "telemetry" false; connector Connect sysbus.usart3 telemetry; start'
```

Then decode it as it arrives; Ctrl-C prints the summary:

```bash
serial-decoder --schema examples/telemetry.toml --port socket://localhost:3456
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

Each field needs a `name` and a `type`: `u8`, `i8`, `u16`, `i16`, `u32`, `i32`, or `f32`. `scale` (default 1) multiplies the raw value, and `unit` is printed after it. The schema is checked when it loads, so a mistake such as an unknown type or a misspelled key stops with an error naming the file and message.

## Test

```bash
pytest
ruff check . && ruff format --check . && mypy
```

## License

MIT
