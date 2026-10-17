"""Hand a successful takeoff to PX4 AUTO_LOITER and maintain neutral manual-input availability."""
from commands.sequence import Mode

ON_FINISH = 'loiter'

def build_sequence():
    return [Mode(4, 3, timeout=8.)]
