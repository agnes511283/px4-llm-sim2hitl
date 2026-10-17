"""Startup provenance and explicit source drift, without a model or transport."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
RUNTIME=Path(__file__).resolve().parents[1];sys.path.insert(0,str(RUNTIME))
from host.runtime_identity import capture,inventory,source_id,drift

class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.project=Path(self.temp.name)/'project';self.logs=Path(self.temp.name)/'logs';self.logs.mkdir()
        for name,content in [('hil_runtime/main.py','main'),('hil_runtime/gui/window.py','gui'),('hil_runtime/gui/theme.qss','style'),('hil_runtime/requirements.txt','requirements'),('hil_bridge/commands/example.py','command')]:
            p=self.project/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
    def tearDown(self):self.temp.cleanup()
    def test_deterministic_sorted_content_identity(self):
        a=inventory(self.project);self.assertEqual(source_id(a),source_id(list(reversed(a))))
        self.assertEqual([x['path'] for x in a],sorted(x['path'] for x in a))
    def test_gui_and_commands_change_id(self):
        first=source_id(inventory(self.project));(self.project/'hil_runtime/gui/theme.qss').write_text('new-style')
        self.assertNotEqual(first,source_id(inventory(self.project)))
    def test_logs_cache_tests_secrets_excluded(self):
        first=source_id(inventory(self.project))
        for name in ['logs/wire.bin','hil_runtime/tests/test_new.py','hil_runtime/gui/__pycache__/x.py','state/host.json','hil_runtime/releases/example/a.py']:
            p=self.project/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('secret-fixture')
        self.assertEqual(first,source_id(inventory(self.project)))
    def test_capture_stays_fixed_and_drift_is_explicit(self):
        value=capture(self.project,self.logs,'model-id','manifest-sha');saved=json.loads((self.logs/value['manifest']).read_text());before=copy.deepcopy(value)
        (self.project/'hil_runtime/gui/window.py').write_text('changed-after-start')
        self.assertEqual(value,before);self.assertEqual(drift(self.project,saved['files']),['hil_runtime/gui/window.py'])
        self.assertEqual(saved['model_build_id'],'model-id');self.assertEqual(saved['model_manifest_sha256'],'manifest-sha')

if __name__=='__main__':unittest.main(verbosity=2)
