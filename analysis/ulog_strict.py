"""Strict whole-file ULog parse: every message must be well-formed, end exactly at EOF."""
import json, struct, sys

MAGIC = b'ULog\x01\x12\x35'
SIZES = {'int8_t': 1, 'uint8_t': 1, 'bool': 1, 'char': 1, 'int16_t': 2, 'uint16_t': 2,
         'int32_t': 4, 'uint32_t': 4, 'float': 4, 'int64_t': 8, 'uint64_t': 8, 'double': 8}
KNOWN = set(b'BFIMPQARDLCSO')


def parse(path):
    b = open(path, 'rb').read()
    err = []
    if b[:7] != MAGIC:
        return {'ok': False, 'errors': ['bad magic']}
    pos, formats, subs, counts = 16, {}, {}, {}
    sizes = {}

    def fmt_size(name, depth=0):
        if name in SIZES:
            return SIZES[name]
        if name in sizes:
            return sizes[name]
        if depth > 20 or name not in formats:
            raise KeyError(name)
        total = 0
        for ftype, fname in formats[name]:
            n = 1
            if '[' in ftype:
                ftype, n = ftype[:-1].split('[')
                n = int(n)
            total += fmt_size(ftype, depth + 1) * n
        sizes[name] = total
        return total

    def min_size(name):
        # trailing _padding fields may be omitted from data messages
        fields = list(formats[name])
        while fields and fields[-1][1].startswith('_padding'):
            fields.pop()
        t = 0
        for ftype, _ in fields:
            n = 1
            if '[' in ftype:
                ftype, n = ftype[:-1].split('[')
                n = int(n)
            t += fmt_size(ftype) * n
        return t

    header_done = False
    while pos < len(b):
        if pos + 3 > len(b):
            err.append(f'truncated header at {pos}')
            break
        size, t = struct.unpack_from('<HB', b, pos)
        p = b[pos + 3:pos + 3 + size]
        if len(p) != size:
            err.append(f'truncated payload at {pos}')
            break
        if t not in KNOWN:
            err.append(f'unknown type {t} at {pos}')
            break
        c = chr(t)
        counts[c] = counts.get(c, 0) + 1
        try:
            if c == 'B':
                if header_done or pos != 16:
                    err.append(f'flag bits not first at {pos}')
                if any(p[8:16]):
                    err.append(f'incompat flags set {p[8:16].hex()}')
            elif c == 'F':
                name, body = p.decode('ascii').split(':', 1)
                fields = []
                for f in body.split(';'):
                    if f:
                        ftype, fname = f.split(' ')
                        fields.append((ftype, fname))
                formats[name] = fields
            elif c in 'IMPQ':
                off = {'I': 0, 'M': 1, 'P': 0, 'Q': 1}[c]
                kl = p[off]
                key = p[off + 1:off + 1 + kl].decode('ascii')
                ktype = key.split(' ')[0]
                vlen = size - off - 1 - kl
                base = ktype.split('[')[0]
                n = int(ktype[:-1].split('[')[1]) if '[' in ktype else 1
                if base in SIZES and vlen != SIZES[base] * n:
                    err.append(f'{c} value size {vlen} != {ktype} at {pos}')
            elif c == 'A':
                header_done = True
                multi, mid = struct.unpack_from('<BH', p)
                name = p[3:].decode('ascii')
                fmt_size(name)
                if mid in subs:
                    err.append(f'msg_id {mid} added twice at {pos}')
                subs[mid] = name
            elif c == 'R':
                (mid,) = struct.unpack_from('<H', p)
                subs.pop(mid, None)
            elif c == 'D':
                (mid,) = struct.unpack_from('<H', p)
                if mid not in subs:
                    err.append(f'data for unknown msg_id {mid} at {pos}')
                else:
                    full = fmt_size(subs[mid])
                    if not (min_size(subs[mid]) <= size - 2 <= full):
                        err.append(f'data size {size - 2} vs {full} for {subs[mid]} at {pos}')
            elif c == 'L':
                p[9:].decode('utf-8')
            elif c == 'S':
                if p != b'\x2F\x73\x13\x20\x25\x0C\xBB\x12':
                    err.append(f'bad sync at {pos}')
            elif c == 'O':
                if size != 2:
                    err.append(f'dropout size {size} at {pos}')
        except Exception as e:  # noqa: BLE001
            err.append(f'{c} at {pos}: {type(e).__name__}: {e}')
        if len(err) > 20:
            break
        pos += 3 + size
    return {'ok': not err and pos == len(b), 'end': pos, 'file_size': len(b),
            'formats': len(formats), 'counts': counts, 'errors': err}


if __name__ == '__main__':
    out = {p: parse(p) for p in sys.argv[1:]}
    print(json.dumps(out, indent=1))
    sys.exit(0 if all(r['ok'] for r in out.values()) else 1)
