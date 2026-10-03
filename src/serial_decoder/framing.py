DELIMITER = b"\x00"


class FrameError(ValueError):
    """A frame that isn't valid COBS."""


class FrameSplitter:
    """Splits a byte stream into COBS frames at 0x00 delimiters, across reads of any size."""

    def __init__(self) -> None:
        self._pending = b""

    def feed(self, chunk: bytes) -> list[bytes]:
        """Returns the frames `chunk` completes, without their delimiters."""
        *frames, self._pending = (self._pending + chunk).split(DELIMITER)
        return [frame for frame in frames if frame]

    @property
    def pending(self) -> int:
        """Bytes of an unfinished frame still waiting for its delimiter."""
        return len(self._pending)


def cobs_decode(frame: bytes) -> bytes:
    """Decodes one COBS frame (without its delimiter)."""
    if DELIMITER in frame:
        raise FrameError("zero byte inside a frame")
    decoded = bytearray()
    i = 0
    while i < len(frame):
        # Each code byte is the distance to the next zero, which the encoder left out.
        code = frame[i]
        end = i + code
        if end > len(frame):
            raise FrameError(f"COBS code {code:#04x} at offset {i} runs past the end of the frame")
        decoded += frame[i + 1 : end]
        # 0xFF marks a full 254-byte block with no zero after it; the last block has none either.
        if code != 0xFF and end < len(frame):
            decoded.append(0)
        i = end
    return bytes(decoded)
