"""Empty post-takeoff template; explicitly selected with --after.

Fill build_sequence() with Wait, Mode or Sticks actions when a test is defined.
Import them from commands.sequence. Sticks are normalized MAVLink x/y/z/r,
not roll/pitch angles. Do not create sockets or sleep in this module.
"""

ON_FINISH = 'hold'


def build_sequence():
    return []
