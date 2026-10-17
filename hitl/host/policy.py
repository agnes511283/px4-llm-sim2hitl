"""Agent policy (agent_policy.json): action tiers for the LLM and the fixed flight-test parameters.

There is no in-app confirmation: the user gives consent in the conversation (user 2026-10-17). The agent asks
there before tier C actions (deploying a new algorithm to the FC, deleting logs, releases or reports).
"""

import json
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]


def policy():
    return json.loads((PROJECT / 'agent_policy.json').read_text())


def flight_test_overrides(args):
    """Return {name: (requested, fixed)} for parameters that differ from the policy."""
    fixed = policy()['flight_test']
    return {
        name: (getattr(args, name), value)
        for name, value in fixed.items()
        if float(getattr(args, name)) != float(value)
    }
