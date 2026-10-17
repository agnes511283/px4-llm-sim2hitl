"""Default flight and judgement of the flight tests (hitl/flight_test.json)."""

import json
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[1] / 'flight_test.json'


def config():
    return json.loads(CONFIG.read_text())


def flight_test_overrides(args):
    """Return {name: (requested, default)} for flight values that differ from the default."""
    fixed = config()['flight_test']
    return {
        name: (getattr(args, name), value)
        for name, value in fixed.items()
        if float(getattr(args, name)) != float(value)
    }
