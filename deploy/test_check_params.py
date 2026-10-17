"""deploy/check_params.py on a synthetic release and readbacks (no FC, no PX4 tree)."""

import copy
import hashlib
import json
import lzma
import struct
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_params as cp  # noqa: E402

FIRMWARE = [
    {'name': 'SYS_AUTOSTART', 'type': 'Int32', 'default': 0},
    {'name': 'CA_SV_CS_COUNT', 'type': 'Int32', 'default': 0},
    {'name': 'SYS_HITL', 'type': 'Int32', 'default': 0, 'rebootRequired': True},
    {'name': 'FW_R_TC', 'type': 'Float', 'default': 0.4},
    {'name': 'NAV_ACC_RAD', 'type': 'Float', 'default': 10.0},
    {'name': 'GPS_1_CONFIG', 'type': 'Int32', 'default': 201},
    {'name': 'CAL_ACC0_XOFF', 'type': 'Float', 'default': 0.0},
]
GOOD = {'SYS_AUTOSTART': (2100, 6), 'CA_SV_CS_COUNT': (4, 6), 'SYS_HITL': (1, 6), 'FW_R_TC': (0.4, 9),
        'NAV_ACC_RAD': (10.0, 9), 'GPS_1_CONFIG': (0, 6), 'CAL_ACC0_XOFF': (0.123, 9)}
GIT = 'd6f12ad1c4f70ad3230afd7d86e971421e02fef4'
NUTTX = 'fb2fadf6f599c1406f052db013efd00a2518e72c'


def bits(value, kind):
    return struct.pack('<i' if kind == 6 else '<f', value).hex()


class CheckParamsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name)
        (self.dir / 'firmware').mkdir()
        self.write_firmware(FIRMWARE)
        image = self.dir / 'firmware/fw.px4'
        image.write_bytes(b'image')
        self.info = {'outputs': {'firmware': {'file': 'fw.px4', 'sha256': hashlib.sha256(b'image').hexdigest()},
                                 'parameters': {'sha256': self.list_sha}},
                     'embedded': {'board_id': 56, 'git_hash': GIT}}
        (self.dir / 'firmware/firmware.json').write_text(json.dumps(self.info))
        self.release = {
            'schema_version': 1, 'firmware': 'firmware/firmware.json',
            'firmware_params': {'file': 'firmware/parameters.json.xz', 'sha256': self.list_sha},
            'fc_owned': {'patterns': ['^CAL_'], 'resolved_names': ['CAL_ACC0_XOFF']},
            'verify_only': {'SYS_AUTOSTART': {'value': 2100}},
            'airframe': {'CA_SV_CS_COUNT': {'value': 4}, 'NAV_ACC_RAD': {'value': 10.0}},
            'boot': {'GPS_1_CONFIG': {'value': 0}},
            'set': {'SYS_HITL': {'value': 1}},
        }
        self.write_release(self.release)

    def tearDown(self):
        self.temp.cleanup()

    def write_firmware(self, params, name='firmware/parameters.json.xz'):
        raw = lzma.compress(json.dumps({'parameters': params}).encode())
        (self.dir / name).write_bytes(raw)
        self.list_sha = hashlib.sha256(raw).hexdigest()
        return self.dir / name

    def write_release(self, release):
        (self.dir / 'params.json').write_text(json.dumps(release))

    def readback(self, values=None, extra=(), **changes):
        values = GOOD if values is None else values
        rows = [{'name': n, 'value': v, 'type': t, 'bits': bits(v, t), 'index': i}
                for i, (n, (v, t)) in enumerate(sorted(values.items()))]
        data = {'schema_version': 2, 'verdict': 'PASS', 'consistency': [],
                'param_count_used': len(rows), 'used_received': len(rows), 'used_index_missing': [],
                'param_list': {'sha256': self.list_sha},
                'autopilot_version': {'board_version': 56, 'git_hash_prefix': GIT[:10]},
                'parameters': rows + [dict(e, index=e.get('index', -1)) for e in extra]}
        data.update(changes)
        path = self.dir / 'rb.json'
        path.write_text(json.dumps(data))
        return cp.check(self.dir, path)

    def test_pass_skips_fc_owned_values_and_compares_float32(self):
        r = self.readback(dict(GOOD, FW_R_TC=(0.4000000059604645, 9)))  # the float32 of 0.4, as on the wire
        self.assertEqual(r['verdict'], 'PASS', r)
        self.assertEqual(r['fc_owned_skipped'], 1)

    def test_wrong_managed_value_and_manual_change_fail(self):
        r = self.readback(dict(GOOD, SYS_HITL=(0, 6), FW_R_TC=(0.5, 9), GPS_1_CONFIG=(201, 6)))
        self.assertEqual(r['verdict'], 'FAIL')
        self.assertEqual(sorted(x['name'] for x in r['wrong_value']), ['GPS_1_CONFIG', 'SYS_HITL'])
        self.assertEqual([x['name'] for x in r['not_default']], ['FW_R_TC'])  # only reported, never written

    def test_identity(self):
        # GPT review N1: another board or git hash fails; a missing identity or another parameter list is incomplete.
        r = self.readback(autopilot_version={'board_version': 53, 'git_hash_prefix': GIT[:10]})
        self.assertEqual((r['verdict'], r['identity'][0]['problem']), ('FAIL', 'board'))
        r = self.readback(autopilot_version={'board_version': 56, 'git_hash_prefix': 'aaaaaaaaaa'})
        self.assertEqual((r['verdict'], r['identity'][0]['problem']), ('FAIL', 'git hash'))
        self.assertEqual(self.readback(autopilot_version=None)['verdict'], 'INCOMPLETE')
        self.assertEqual(self.readback(param_list={'sha256': 'x'})['verdict'], 'INCOMPLETE')

    def test_nuttx_identity(self):
        # A recipe that records its NuttX commit: the FC's os_custom_version must match (a committed NuttX patch
        # changes it); an old readback without it is incomplete. Without the record nothing is compared.
        self.assertEqual(self.readback()['verdict'], 'PASS')
        self.info['embedded']['nuttx_git_hash'] = NUTTX
        (self.dir / 'firmware/firmware.json').write_text(json.dumps(self.info))
        version = {'board_version': 56, 'git_hash_prefix': GIT[:10]}
        self.assertEqual(self.readback(autopilot_version=dict(version, os_hash_prefix=NUTTX[:16]))['verdict'], 'PASS')
        r = self.readback(autopilot_version=dict(version, os_hash_prefix='0' * 16))
        self.assertEqual((r['verdict'], r['identity'][0]['problem']), ('FAIL', 'NuttX hash'))
        self.assertEqual(self.readback(autopilot_version=version)['verdict'], 'INCOMPLETE')

    def test_local_files_must_match_the_recipe(self):
        (self.dir / 'firmware/fw.px4').write_bytes(b'other image')
        r = self.readback()
        self.assertEqual(r['verdict'], 'FAIL')
        self.assertTrue(any('fw.px4' in x for x in r['local_mismatch']))
        (self.dir / 'firmware/fw.px4').write_bytes(b'image')
        self.write_release(dict(self.release, firmware_params={'file': 'firmware/parameters.json.xz', 'sha256': 'y'}))
        self.assertEqual(self.readback()['verdict'], 'FAIL')

    def edited(self, name, **fields):
        """A good readback with one entry's fields replaced (e.g. a value that does not match its bits)."""
        self.readback()
        data = json.loads((self.dir / 'rb.json').read_text())
        data['parameters'] = [dict(p, **fields) if p['name'] == name else p for p in data['parameters']]
        (self.dir / 'rb.json').write_text(json.dumps(data))
        return cp.check(self.dir, self.dir / 'rb.json')

    def test_structure(self):
        # GPT review N2: each of these is INCOMPLETE, with the reason in 'structure' (or 'not_in_firmware').
        dup = {'name': 'SYS_HITL', 'value': 1, 'type': 6, 'bits': bits(1, 6)}
        new = {'name': 'ZZ_NEW', 'value': 1, 'type': 6, 'bits': bits(1, 6)}
        for r, reason in [
            (self.readback(extra=[dup]), 'duplicate name'),
            (self.edited('SYS_HITL', value=1.75), 'Int32 value is not an integer in range'),
            (self.edited('SYS_HITL', bits='0000c07f'), 'value does not match bits'),
            (self.edited('FW_R_TC', bits=None), 'no 4-byte bits'),
            (self.readback(schema_version=1), 'readback schema < 2 (no wire bits / consistency check)'),
            (self.readback(verdict='INCOMPLETE', consistency=[{'problem': 'index_conflict'}]), 'readback not PASS'),
        ]:
            self.assertEqual(r['verdict'], 'INCOMPLETE', (reason, r))
            self.assertIn(reason, [x['problem'] for x in r['structure']])
        r = self.readback(extra=[new])
        self.assertEqual((r['verdict'], r['not_in_firmware']), ('INCOMPLETE', ['ZZ_NEW']))
        missing = dict(GOOD)
        del missing['CAL_ACC0_XOFF']  # fc_owned values are not compared, but must be read
        r = self.readback(missing)
        self.assertEqual((r['verdict'], r['not_read']), ('INCOMPLETE', ['CAL_ACC0_XOFF']))
        # Review 9 D6: the used indices are recounted from the rows, not taken from the readback's verdict.
        for fields in [dict(param_count_used=9999), dict(used_received=0), dict(used_index_missing=[2])]:
            r = self.readback(**fields)
            self.assertEqual(r['verdict'], 'INCOMPLETE', fields)
        r = self.edited('SYS_HITL', index=0)  # two rows on used index 0
        self.assertIn('used indices are not 0..param_count_used-1 once each', [x['problem'] for x in r['structure']])
        # Review 10 E7: an unused row's index is -1, nothing else (not -2, a string, a bool or missing).
        used = dict(GOOD)
        del used['NAV_ACC_RAD']
        unused = {'name': 'NAV_ACC_RAD', 'value': 10.0, 'type': 9, 'bits': bits(10.0, 9)}
        self.assertEqual(self.readback(used, extra=[dict(unused, index=-1)])['verdict'], 'PASS')
        for index in [-2, 'bogus', True, None]:
            r = self.readback(used, extra=[dict(unused, index=index)])
            self.assertEqual(r['verdict'], 'INCOMPLETE', index)
            self.assertIn('index is not -1 or a used index', [x['problem'] for x in r['structure']], index)

    def test_release_lists_must_match_the_firmware(self):
        self.write_release(dict(self.release, set={'SYS_HITL': {'value': 1}, 'GONE_PARAM': {'value': 1}}))
        r = self.readback()
        self.assertEqual((r['verdict'], r['unknown_name']), ('INCOMPLETE', [{'name': 'GONE_PARAM', 'section': 'set'}]))
        # GPT review N4: the fc_owned patterns must still resolve to the reviewed set.
        self.write_release(dict(self.release, fc_owned={'patterns': ['^CAL_', '^FW_'], 'resolved_names': ['CAL_ACC0_XOFF']}))
        r = self.readback()
        self.assertEqual((r['verdict'], r['fc_owned_set_changed'][0]['added']), ('INCOMPLETE', ['FW_R_TC']))

    def test_inconsistent_release_is_rejected(self):
        self.write_release(dict(self.release, set={'CAL_ACC0_XOFF': {'value': 1.0}}))
        with self.assertRaisesRegex(ValueError, 'fc_owned'):
            self.readback()
        self.write_release(dict(self.release, set={'SYS_AUTOSTART': {'value': 2100}}))
        with self.assertRaisesRegex(ValueError, 'both'):
            self.readback()

    def test_compare_firmware_lists_what_changed(self):
        new = copy.deepcopy([p for p in FIRMWARE if p['name'] != 'SYS_HITL'])
        new += [{'name': 'NEW_P', 'type': 'Int32', 'default': 1}, {'name': 'CAL_NEW_ENABLE', 'type': 'Int32', 'default': 0}]
        next(p for p in new if p['name'] == 'NAV_ACC_RAD')['default'] = 15.0
        next(p for p in new if p['name'] == 'FW_R_TC')['rebootRequired'] = True
        old_path = self.dir / 'firmware/parameters.json.xz'
        new_path = self.write_firmware(new, 'new.json.xz')
        r = cp.compare_firmware(old_path, new_path, self.dir)
        self.assertEqual((r['added'], r['removed']), (['CAL_NEW_ENABLE', 'NEW_P'], ['SYS_HITL']))
        self.assertEqual([c['name'] for c in r['changed']], ['NAV_ACC_RAD'])
        self.assertEqual([c['name'] for c in r['reboot_changed']], ['FW_R_TC'])
        self.assertEqual((r['managed_removed'], r['managed_changed']), (['SYS_HITL'], ['NAV_ACC_RAD']))
        self.assertEqual(r['fc_owned_added'], ['CAL_NEW_ENABLE'])  # a new name swallowed by a pattern


if __name__ == '__main__':
    unittest.main(verbosity=2)
