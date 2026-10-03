import binascii


def crc16_ccitt(data: bytes) -> int:
    """CRC-16/CCITT-FALSE: poly 0x1021, init 0xFFFF, no reflection, no final XOR."""
    # crc_hqx is the unreflected 0x1021 CRC; starting it at 0xFFFF makes it the CCITT-FALSE variant.
    return binascii.crc_hqx(data, 0xFFFF)
