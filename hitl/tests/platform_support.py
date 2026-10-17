"""What this machine's active release can test: an FC-only release (Linux, no MATLAB) has no model library."""
from pathlib import Path
import sys
import unittest

RUNTIME = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUNTIME))
from host.release import read_release

HAS_MODEL = bool(read_release(RUNTIME)[1].get('library'))
needs_model = unittest.skipUnless(HAS_MODEL, 'needs the model library; the active release here is FC-only')
