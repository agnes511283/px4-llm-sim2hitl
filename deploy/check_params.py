"""Check FC parameters against a release's parameter set, or list what a firmware change touches.

A release's parameters (deploy/<release>/params.json) are: the firmware's own defaults (the PX4 build's
parameters.json.xz) + 'airframe' and 'boot' (values the airframe / board / rcS scripts set at boot; checked,
never written) + 'verify_only' (checked, never written, e.g. SYS_AUTOSTART) + 'set' (the only values the project
writes). Parameters matching 'fc_owned' patterns belong to the physical FC (calibration, counters, ...): their
values are not compared, but they must be read completely and consistently like every other parameter.

  python3 deploy/check_params.py --readback <params_*.json from param-readback> [--release deploy/00_native]
      Verdict PASS (exit 0), FAIL (exit 3: a value differs, or the FC / local files are not the release's
      firmware) or INCOMPLETE (exit 5: the readback is incomplete or inconsistent, identity is missing, or the
      release's lists no longer match the firmware). 'not_default' only reports differences; it is never a
      list of values to write.

  python3 deploy/check_params.py --compare-firmware OLD.json.xz NEW.json.xz [--release deploy/00_native]
      For a PX4 upgrade: parameters added, removed, with a changed default, type or reboot flag, those the
      release manages, and those newly matched (or no longer matched) by the fc_owned patterns. An aid only:
      the boot scripts of the new version must be reviewed too. Exit 0.

Read-only: reads local files only, never the FC.
"""

import argparse
import hashlib
import json
import lzma
import math
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KINDS = {'Int32': 6, 'Float': 9}  # PX4 parameters.json type -> MAVLink param_type
SECTIONS = ['airframe', 'boot', 'verify_only', 'set']
INT32 = (-2 ** 31, 2 ** 31 - 1)


def load_firmware(path):
    raw = Path(path).read_bytes()
    listing = json.loads(lzma.decompress(raw) if str(path).endswith('.xz') else raw)
    params = {}
    for p in listing['parameters']:
        if p['name'] in params:
            raise ValueError(f'{path}: parameter {p["name"]} listed twice')
        params[p['name']] = p
    unknown = {p['type'] for p in params.values()} - set(KINDS)
    if unknown:
        raise ValueError(f'{path}: unknown parameter types {sorted(unknown)}')
    return params


def is_int32(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return float(value).is_integer() and INT32[0] <= value <= INT32[1]


def same(kind, a, b):
    if kind == 6:
        return is_int32(a) and is_int32(b) and int(a) == int(b)
    return struct.pack('<f', float(a)) == struct.pack('<f', float(b))  # PX4 stores float32


def managed(release):
    """name -> (expected value, section) for every parameter the release states."""
    out = {}
    for section in SECTIONS:
        for name, entry in release.get(section, {}).items():
            if name in out:
                raise ValueError(f'{name} is in both {out[name][1]} and {section}')
            out[name] = (entry['value'], section)
    return out


def owned_names(firmware, patterns):
    rule = re.compile('|'.join(patterns))
    return sorted(n for n in firmware if rule.search(n))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def expected_board_version(embedded):
    """What the FC of this firmware reports as AUTOPILOT_VERSION.board_version. PX4's px4_board_version() is the
    USB product id (CONFIG_CDCACM_PRODUCTID), not the board id in the image: equal on the Pixhawk 6C (56), not on
    the Cube Orange+ (0x1058 = 4184, board id 1063). px4/build_firmware.py records it; older records have only
    board_id."""
    return embedded.get('board_version', embedded['board_id'])


def entry_problem(entry, kind):
    """Why a readback entry is not a valid value of its type (None when valid); 'bits' are the wire bytes."""
    value, bits = entry.get('value'), entry.get('bits')
    if not isinstance(bits, str) or not re.fullmatch(r'[0-9a-f]{8}', bits):
        return 'no 4-byte bits'
    raw = bytes.fromhex(bits)
    if kind == 6:
        if not is_int32(value):
            return 'Int32 value is not an integer in range'
        return None if struct.unpack('<i', raw)[0] == int(value) else 'value does not match bits'
    decoded = struct.unpack('<f', raw)[0]
    if value is None:
        return None if not math.isfinite(decoded) else 'null value for finite bits'
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 'Float value is not a number'
    return None if struct.pack('<f', float(value)) == raw else 'value does not match bits'


def check(release_dir, readback_path):
    release_dir = Path(release_dir)
    release = json.loads((release_dir / 'params.json').read_text())
    firmware_info = json.loads((release_dir / release['firmware']).read_text())
    list_path = release_dir / release['firmware_params']['file']
    firmware = load_firmware(list_path)
    patterns = release['fc_owned']['patterns']
    owned = set(owned_names(firmware, patterns))
    readback = json.loads(Path(readback_path).read_text())
    expected = managed(release)
    report = {key: [] for key in ['local_mismatch', 'identity', 'structure', 'wrong_value', 'not_default',
                                  'unknown_name', 'not_read', 'not_in_firmware', 'fc_owned_set_changed',
                                  'redundant']}
    # Local files: the release's lists, the firmware recipe and the image must be the ones recorded.
    actual = sha256(list_path)
    for what, recorded in [('params.json firmware_params', release['firmware_params']['sha256']),
                           ('firmware.json parameters', firmware_info['outputs']['parameters']['sha256'])]:
        if recorded != actual:
            report['local_mismatch'].append(f'{what}: {recorded} != {actual}')
    image = release_dir / 'firmware' / firmware_info['outputs']['firmware']['file']
    if sha256(image) != firmware_info['outputs']['firmware']['sha256']:
        report['local_mismatch'].append(f'{image.name}: SHA-256 differs from firmware.json')
    # Identity: the readback must come from this firmware (AUTOPILOT_VERSION) and this parameter list.
    version = readback.get('autopilot_version')
    embedded = firmware_info['embedded']
    if not version:
        report['identity'].append({'problem': 'missing AUTOPILOT_VERSION', 'kind': 'incomplete'})
    else:
        board = expected_board_version(embedded)
        if version.get('board_version') != board:
            report['identity'].append({'problem': 'board', 'fc': version.get('board_version'),
                                       'expected': board, 'kind': 'fail'})
        if version.get('git_hash_prefix') != embedded['git_hash'][:10]:
            report['identity'].append({'problem': 'git hash', 'fc': version.get('git_hash_prefix'),
                                       'expected': embedded['git_hash'][:10], 'kind': 'fail'})
        # NuttX commit (os_custom_version): a NuttX patch committed in the build tree changes it.
        if embedded.get('nuttx_git_hash'):
            if not version.get('os_hash_prefix'):
                report['identity'].append({'problem': 'missing NuttX hash in AUTOPILOT_VERSION', 'kind': 'incomplete'})
            elif version['os_hash_prefix'] != embedded['nuttx_git_hash'][:16]:
                report['identity'].append({'problem': 'NuttX hash', 'fc': version['os_hash_prefix'],
                                           'expected': embedded['nuttx_git_hash'][:16], 'kind': 'fail'})
    if readback.get('param_list', {}).get('sha256') != actual:
        report['identity'].append({'problem': 'readback used another parameter list', 'kind': 'incomplete'})
    # The ownership rules must still resolve to the reviewed set (a new firmware may add matching names).
    resolved = release['fc_owned'].get('resolved_names', [])
    if sorted(owned) != resolved:
        report['fc_owned_set_changed'] = [{'added': sorted(owned - set(resolved)),
                                           'removed': sorted(set(resolved) - owned)}]
    # Structure: every name once, from the firmware, a valid value of its type; the readback's own checks.
    if readback.get('schema_version', 0) < 2:
        report['structure'].append({'problem': 'readback schema < 2 (no wire bits / consistency check)'})
    if readback.get('verdict') != 'PASS' or readback.get('consistency'):
        report['structure'].append({'problem': 'readback not PASS', 'verdict': readback.get('verdict'),
                                    'consistency': readback.get('consistency', [])[:20]})
    values = {}
    for entry in readback['parameters']:
        name = entry.get('name')
        if name in values:
            report['structure'].append({'problem': 'duplicate name', 'name': name})
            continue
        values[name] = entry
        if name not in firmware:
            report['not_in_firmware'].append(name)
            continue
        kind = KINDS[firmware[name]['type']]
        if entry.get('type') != kind:
            report['structure'].append({'problem': 'type', 'name': name, 'fc': entry.get('type'), 'firmware': kind})
            continue
        problem = entry_problem(entry, kind)
        if problem:
            report['structure'].append({'problem': problem, 'name': name})
    report['not_read'] = sorted(n for n in firmware if n not in values)
    # Recount the used indices from the rows themselves: 0..param_count_used-1, each exactly once, and the
    # readback's own summary must agree (the readback's PASS is not trusted on its own).
    count = readback.get('param_count_used')
    # Every row's index is an integer: -1 (not used) or a used index; anything else is a malformed row.
    bad_index = [e.get('name') for e in readback['parameters']
                 if isinstance(e.get('index'), bool) or not isinstance(e.get('index'), int) or e['index'] < -1]
    if bad_index:
        report['structure'].append({'problem': 'index is not -1 or a used index', 'names': bad_index[:20],
                                    'count': len(bad_index)})
    indices = sorted(e['index'] for e in readback['parameters'] if isinstance(e.get('index'), int) and e['index'] >= 0)
    if not isinstance(count, int) or indices != list(range(count)):
        report['structure'].append({'problem': 'used indices are not 0..param_count_used-1 once each',
                                    'param_count_used': count, 'used_rows': len(indices)})
    elif readback.get('used_received') != count or readback.get('used_index_missing'):
        report['structure'].append({'problem': 'readback summary disagrees with its rows'})
    # Values: managed ones as stated, the rest at the firmware default; fc_owned values are not compared.
    for name, (value, section) in sorted(expected.items()):
        if name not in firmware:
            report['unknown_name'].append({'name': name, 'section': section})
        elif name in owned:
            raise ValueError(f'{name} is both fc_owned and in {section}')
        elif section == 'set' and same(KINDS[firmware[name]['type']], value, firmware[name].get('default', 0)):
            report['redundant'].append(name)  # equals the default: harmless, but not needed
    bad = {e['name'] for e in report['structure'] if 'name' in e}
    for name, entry in sorted(firmware.items()):
        if name in owned or name not in values or name in bad:
            continue
        kind, got = KINDS[entry['type']], values[name]['value']
        if name in expected:
            want, section = expected[name]
            if got is None or not same(kind, got, want):
                report['wrong_value'].append({'name': name, 'section': section, 'fc': got, 'expected': want})
        elif got is None or not same(kind, got, entry.get('default', 0)):
            report['not_default'].append({'name': name, 'fc': got, 'default': entry.get('default', 0)})
    failed = (report['local_mismatch'] or report['wrong_value'] or report['not_default']
              or any(x['kind'] == 'fail' for x in report['identity']))
    incomplete = (report['structure'] or report['not_read'] or report['not_in_firmware'] or report['unknown_name']
                  or report['fc_owned_set_changed'] or report['identity'])
    report['verdict'] = 'FAIL' if failed else 'INCOMPLETE' if incomplete else 'PASS'
    report.update(
        readback=str(readback_path), readback_verdict=readback.get('verdict'),
        autopilot_version=version, firmware_params=release['firmware_params'],
        fc_owned_skipped=len(owned), managed={s: len(release.get(s, {})) for s in SECTIONS},
    )
    return report


def compare_firmware(old_path, new_path, release_dir=None):
    old, new = load_firmware(old_path), load_firmware(new_path)
    expected, patterns = {}, None
    if release_dir:
        release = json.loads((Path(release_dir) / 'params.json').read_text())
        expected, patterns = managed(release), release['fc_owned']['patterns']

    def reboot(p):
        return bool(p.get('rebootRequired', False))

    changed = [n for n in sorted(set(old) & set(new))
               if old[n]['type'] != new[n]['type']
               or not same(KINDS[new[n]['type']], old[n].get('default', 0), new[n].get('default', 0))]
    reboot_changed = [n for n in sorted(set(old) & set(new)) if reboot(old[n]) != reboot(new[n])]
    added, removed = sorted(set(new) - set(old)), sorted(set(old) - set(new))
    out = {
        'added': added,
        'removed': removed,
        'changed': [{'name': n, 'old': [old[n]['type'], old[n].get('default', 0)],
                     'new': [new[n]['type'], new[n].get('default', 0)]} for n in changed],
        'reboot_changed': [{'name': n, 'old': reboot(old[n]), 'new': reboot(new[n])} for n in reboot_changed],
        'managed_removed': [n for n in removed if n in expected],
        'managed_changed': [n for n in changed if n in expected],
        'counts': {'old': len(old), 'new': len(new), 'added': len(added), 'removed': len(removed),
                   'changed': len(changed), 'reboot_changed': len(reboot_changed)},
    }
    if patterns:
        before, after = set(owned_names(old, patterns)), set(owned_names(new, patterns))
        out['fc_owned_added'] = sorted(after - before)  # review: a new name swallowed by a pattern
        out['fc_owned_removed'] = sorted(before - after)
    return out


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--release', type=Path, default=ROOT / 'deploy/00_native')
    p.add_argument('--readback', type=Path, help='params_*.json written by ./runbridge param-readback')
    p.add_argument('--compare-firmware', nargs=2, type=Path, metavar=('OLD', 'NEW'))
    args = p.parse_args(argv)
    if bool(args.readback) == bool(args.compare_firmware):
        p.error('give --readback or --compare-firmware')
    if args.compare_firmware:
        print(json.dumps(compare_firmware(*args.compare_firmware, args.release), indent=1))
        return 0
    report = check(args.release, args.readback)
    print(json.dumps(report, indent=1))
    return {'PASS': 0, 'FAIL': 3, 'INCOMPLETE': 5}[report['verdict']]


if __name__ == '__main__':
    sys.exit(main())
