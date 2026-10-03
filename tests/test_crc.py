from serial_decoder.crc import crc16_ccitt


def test_matches_standard_check_value() -> None:
    assert crc16_ccitt(b"123456789") == 0x29B1
