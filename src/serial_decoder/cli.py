import argparse


def main(argv: list[str] | None = None) -> int:
    """Runs the decoder and returns the process exit code."""
    parser = argparse.ArgumentParser(
        prog="serial-decoder",
        description="Decode COBS-framed, CRC-checked binary packets from an embedded device.",
    )
    parser.parse_args(argv)
    return 0
