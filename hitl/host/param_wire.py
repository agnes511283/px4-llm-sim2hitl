"""The 4 value bytes of PARAM_VALUE / PARAM_SET, exactly as on the wire.

MAVLink carries every parameter in a float field. Going through a Python float changes an Int32 whose bits
look like a signalling NaN (0x7f800001 becomes 0x7fc00001, -8388607 becomes -4194303), so values are read
from, and written into, the packet bytes. param_value is the first payload field of both messages.
"""

import struct

from pymavlink.generator.mavcrc import x25crc


def _payload_start(buf):
    return 10 if buf[:1] == b'\xfd' else 6  # MAVLink 2 / MAVLink 1 header


def param_bits(message):
    """The value bytes of a parsed PARAM_VALUE or PARAM_SET (only within the payload: MAVLink 2 truncates
    trailing zero bytes, so a short payload is padded with zeros, never read into the CRC)."""
    if message.get_type() not in ('PARAM_VALUE', 'PARAM_SET'):
        raise ValueError('not a PARAM_VALUE / PARAM_SET: ' + message.get_type())
    buf = bytes(message.get_msgbuf())
    start = _payload_start(buf)
    payload = buf[start:start + buf[1]]
    return payload[:4].ljust(4, b'\0')


def with_bits(packet, bits, crc_extra):
    """An unsigned packed PARAM_VALUE / PARAM_SET with its value bytes replaced and the CRC recomputed."""
    if len(bits) != 4:
        raise ValueError('value bits must be 4 bytes')
    buf = bytearray(packet)
    if buf[:1] == b'\xfd' and buf[2] & 1:
        raise ValueError('signed MAVLink packets are not rewritten')
    start = _payload_start(buf)
    length = buf[1]
    if length < 4:
        raise ValueError('payload shorter than the value field')
    buf[start:start + 4] = bits
    crc = x25crc(bytes(buf[1:start + length]))
    crc.accumulate(struct.pack('B', crc_extra))
    buf[start + length:start + length + 2] = struct.pack('<H', crc.crc)
    return bytes(buf)


def encode(kind, value):
    """Bits of a value of MAVLink param_type kind (6 Int32, 9 Float)."""
    return struct.pack('<i', int(value)) if kind == 6 else struct.pack('<f', float(value))


def decode(kind, bits):
    return struct.unpack('<i' if kind == 6 else '<f', bits)[0]
