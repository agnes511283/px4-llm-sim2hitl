"""sks_template example after takeoff: settle in AUTO_LOITER, hand over to OFFBOARD (the module's guidance: course
+30 deg after 15 s, climb 10 m after 35 s, 60 s in all), then back to AUTO_LOITER, where the flight test observes the usual hold.
PX4 refuses OFFBOARD when no module sends the offboard signal: the Mode step then fails and the flight is FAIL."""
from commands.sequence import Mode, Wait

ON_FINISH = 'loiter'


def build_sequence():
    return [Mode(4, 3, timeout=8.), Wait(10.), Mode(6, 0, timeout=8.), Wait(60.), Mode(4, 3, timeout=8.)]
