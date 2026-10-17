"""Minimal ULog reader (PX4 logger file format; ROADMAP batch 4h). numpy only, no pyulog.

  log = ulog.read(path)
  log.topics[('vehicle_attitude', 0)]   -> numpy structured array, one row per logged sample
  log.info['ver_hw'], log.params['FW_MAN_P_MAX'], log.dropouts (list of (timestamp_us, duration_ms))

Format (PX4 docs, "ULog File Format"): 16-byte header (magic 'ULog' 0x01 0x12 0x35, version, start time us),
then messages of uint16 size + uint8 type. Definitions: 'B' flag bits, 'F' format "name:type field;...",
'I' info, 'M' multi info, 'P' parameter, 'Q' default parameter. Data: 'A' subscription (multi_id, msg_id,
name), 'D' data (msg_id + packed fields), 'O' dropout (ms), 'L'/'C' log text, 'S' sync, 'R' unsubscribe.
Fields are packed in order (formats carry explicit _padding fields); nested message types become nested
numpy dtypes. Only parameter values logged before the data section are in params; later changes are listed
in param_changes, timed by the largest data timestamp read so far (topics are not written in time order).
Files are refused when the 'B' message sets an incompatible flag this reader does not know (only bit 0 of
byte 0, appended data, is known; the appended part is ignored). A cut-off last message sets truncated=True.
"""
import struct
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

MAGIC = b'ULog\x01\x12\x35'
BASE = {'int8_t': 'i1', 'uint8_t': 'u1', 'int16_t': '<i2', 'uint16_t': '<u2', 'int32_t': '<i4',
        'uint32_t': '<u4', 'int64_t': '<i8', 'uint64_t': '<u8', 'float': '<f4', 'double': '<f8',
        'bool': 'u1', 'char': 'S1'}
VALUE = {'int32_t': '<i', 'float': '<f', 'int8_t': '<b', 'uint8_t': '<B', 'int16_t': '<h', 'uint16_t': '<H',
         'uint32_t': '<I', 'int64_t': '<q', 'uint64_t': '<Q', 'double': '<d', 'bool': '<?'}


@dataclass
class ULog:
    start_us: int = 0
    info: dict = field(default_factory=dict)
    params: dict = field(default_factory=dict)
    param_changes: list = field(default_factory=list)  # (last timestamp seen, name, value)
    topics: dict = field(default_factory=dict)         # (name, multi_id) -> structured array
    dropouts: list = field(default_factory=list)       # (last timestamp seen, duration ms)
    messages: list = field(default_factory=list)       # (timestamp_us, level, text)
    truncated: bool = False                            # the last message was cut off
    appended_data: bool = False                        # incompat flag 0: data appended after the log (ignored)


def _value(key, raw):
    kind, name = key.split(' ', 1)
    if kind.startswith('char['):
        return name, raw.decode(errors='replace').rstrip('\0')
    base = kind.split('[')[0]
    if base in VALUE and '[' not in kind:
        return name, struct.unpack(VALUE[base], raw[:struct.calcsize(VALUE[base])])[0]
    return name, raw


def _dtype(name, formats, cache):
    if name in cache:
        return cache[name]
    fields = []
    for item in formats[name].split(';'):
        if not item:
            continue
        kind, fname = item.split(' ')
        count = 1
        if '[' in kind:
            kind, n = kind[:-1].split('[')
            count = int(n)
        sub = np.dtype(BASE[kind]) if kind in BASE else _dtype(kind, formats, cache)
        fields.append((fname, sub, (count,)) if count > 1 else (fname, sub))
    cache[name] = np.dtype(fields)  # packed: numpy structured dtypes have no alignment by default
    return cache[name]


def read(path):
    data = Path(path).read_bytes()
    if data[:7] != MAGIC:
        raise ValueError(f'{path}: not a ULog file')
    log = ULog(start_us=struct.unpack_from('<Q', data, 8)[0])
    formats, subscriptions, chunks, dtypes = {}, {}, {}, {}
    last_time = log.start_us
    in_data = False
    i = 16
    while i + 3 <= len(data):
        size, kind = struct.unpack_from('<HB', data, i)
        body = data[i + 3:i + 3 + size]
        i += 3 + size
        if len(body) < size:
            log.truncated = True  # the last message is cut off (e.g. a log still being written)
            break
        t = chr(kind)
        if t == 'B' and size >= 16:
            incompat = body[8:16]
            if incompat[0] & ~0x01 or any(incompat[1:]):
                raise ValueError(f'{path}: unknown ULog incompatible flags {incompat.hex()}')
            log.appended_data = bool(incompat[0] & 0x01)
        elif t == 'F':
            name, spec = body.decode().split(':', 1)
            formats[name] = spec
        elif t == 'I':
            n = body[0]
            key, value = _value(body[1:1 + n].decode(), body[1 + n:])
            log.info[key] = value
        elif t == 'M':
            n = body[1]
            key, value = _value(body[2:2 + n].decode(), body[2 + n:])
            log.info.setdefault(key, b'')
            log.info[key] = (log.info[key] if isinstance(log.info[key], bytes) else b'') + (value if isinstance(value, bytes) else str(value).encode())
        elif t == 'P':
            n = body[0]
            key, value = _value(body[1:1 + n].decode(), body[1 + n:])
            if in_data:
                log.param_changes.append((last_time, key, value))
            else:
                log.params[key] = value
        elif t == 'A':
            in_data = True
            multi_id, msg_id = struct.unpack_from('<BH', body)
            subscriptions[msg_id] = (body[3:].decode(), multi_id)
        elif t == 'D':
            msg_id = struct.unpack_from('<H', body)[0]
            chunks.setdefault(msg_id, []).append(body[2:])
            if len(body) >= 10:
                # timestamp is the first field of every topic; topics interleave out of time order
                last_time = max(last_time, struct.unpack_from('<Q', body, 2)[0])
        elif t == 'O':
            log.dropouts.append((last_time, struct.unpack_from('<H', body)[0]))
        elif t == 'L':
            log.messages.append((struct.unpack_from('<Q', body, 1)[0], body[0], body[9:].decode(errors='replace')))
        elif t == 'C':
            log.messages.append((struct.unpack_from('<Q', body, 3)[0], body[0], body[11:].decode(errors='replace')))
    for msg_id, parts in chunks.items():
        name, multi_id = subscriptions[msg_id]
        dtype = _dtype(name, formats, dtypes)
        raw = b''.join(p[:dtype.itemsize].ljust(dtype.itemsize, b'\0') for p in parts)
        log.topics[(name, multi_id)] = np.frombuffer(raw, dtype=dtype)
    return log


def intervals(log, name, multi_id=0):
    """Sample-interval statistics of a topic in ms: median, max, and the number of samples."""
    t = log.topics[(name, multi_id)]['timestamp'].astype(np.int64)
    d = np.diff(t) / 1000.0
    return {'samples': int(len(t)), 'median_ms': float(np.median(d)) if len(d) else None,
            'max_ms': float(d.max()) if len(d) else None}
