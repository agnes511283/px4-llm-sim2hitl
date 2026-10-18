#!/usr/bin/env python3
"""Export a ULog (SITL or the FC's) to CSV files, one per topic, plus the parameters and log messages: for MATLAB
without UAV Toolbox (readtable), spreadsheets or any plotting tool. numpy only (analysis/ulog.py).

  <SkySurfer venv python> -B analysis/ulog_export.py <flight.ulg> <new folder> [--topics a,b,...] [--list]

--list prints the topics with their sample counts and fields (nothing written). Without --topics every topic is
written. Columns: time_s (since the log start), then every field; arrays become name_0, name_1, ...; nested
messages become parent.child. Files: <topic>_<multi id>.csv, parameters.csv, messages.csv, info.json.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ulog  # noqa: E402


def columns(array, prefix=''):
    """Flatten a structured array into (name, 1-D column) pairs, skipping padding fields."""
    for name in array.dtype.names:
        if name.startswith('_padding'):
            continue
        values = array[name]
        if values.dtype.names:
            yield from columns(values, prefix + name + '.')
        elif values.ndim > 1:
            for k in range(values.shape[1]):
                yield f'{prefix}{name}_{k}', values[:, k]
        else:
            yield prefix + name, values


def text(value):
    if isinstance(value, (bytes, np.bytes_)):
        return value.decode('ascii', 'replace')
    return value.item() if hasattr(value, 'item') else value


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('ulog', type=Path)
    parser.add_argument('out', type=Path, nargs='?')
    parser.add_argument('--topics', help='comma-separated topic names (default: all)')
    parser.add_argument('--list', action='store_true', help='only list the topics')
    args = parser.parse_args()
    log = ulog.read(args.ulog)
    if args.list:
        for (name, multi), array in sorted(log.topics.items()):
            fields = [n for n, _ in columns(array)]
            print(f'{name}[{multi}]  {len(array)} samples  {", ".join(fields[:12])}{" ..." if len(fields) > 12 else ""}')
        return 0
    if not args.out:
        parser.error('the output folder is required unless --list')
    args.out.mkdir(parents=True, exist_ok=False)
    wanted = set(args.topics.split(',')) if args.topics else None
    written = {}
    for (name, multi), array in sorted(log.topics.items()):
        if wanted is not None and name not in wanted:
            continue
        cols = list(columns(array))
        path = args.out / f'{name}_{multi}.csv'
        time_s = (array['timestamp'].astype(np.int64) - log.start_us) * 1e-6
        with path.open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['time_s'] + [n for n, _ in cols])
            for row in range(len(array)):
                writer.writerow([f'{time_s[row]:.6f}'] + [text(c[row]) for _, c in cols])
        written[path.name] = len(array)
    with (args.out / 'parameters.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['name', 'value'])
        for key, value in sorted(log.params.items()):
            writer.writerow([key, text(value)])
    with (args.out / 'messages.csv').open('w', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['time_s', 'level', 'text'])
        for stamp, level, message in log.messages:
            writer.writerow([f'{(stamp - log.start_us) * 1e-6:.6f}', level, message])
    info = {k: text(v) for k, v in log.info.items()}
    (args.out / 'info.json').write_text(json.dumps({'source': str(args.ulog), 'info': info, 'dropouts': log.dropouts,
                                                    'truncated': log.truncated, 'topics': written}, indent=2, default=str))
    print(json.dumps({'status': 'PASS', 'out': str(args.out), 'topics': len(written)}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
