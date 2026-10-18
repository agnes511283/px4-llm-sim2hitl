"""plant/wind.py: the wind description shared by SITL and HITL (defaults, rejections, reminders, the SITL line)."""
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT / 'plant'))
sys.path.insert(0, str(PROJECT / 'hitl'))
import wind  # noqa: E402
from host.scenario import load_scene, load_wind  # noqa: E402

GROUND = {'schema_version': 1, 'aircraft_id': 'skysurfer', 'name': 'test'}


class WindTests(unittest.TestCase):
    def test_no_wind_is_still_air(self):
        config, reminders = wind.parse(None)
        self.assertEqual(config, wind.default_config())
        self.assertEqual(reminders, [])
        self.assertEqual(config['start_mode'], 0)

    def test_malformed_is_rejected(self):
        for bad in [{'speed': 3}, {'start': {'mode': 'now'}}, {'gust': {'length_m': [0, 1, 1]}},
                    {'turbulence': {'seed': [1, 2, 3]}}, {'shear': {'speed_6m_m_s': -1}},
                    {'steady_ned_m_s': [1, 2]}, {'steady_ned_m_s': [float('nan'), 0, 0]}]:
            with self.assertRaises(ValueError, msg=str(bad)):
                wind.parse(bad)

    def test_reminders(self):
        _, r = wind.parse({'steady_ned_m_s': [0, 5, 1], 'shear': {'speed_6m_m_s': 2}, 'turbulence': {'speed_6m_m_s': 1},
                           'start': {'mode': 'from_start'}})
        text = ' '.join(r)
        for words in ['vertical part', 'steady wind is not used', 'tips it', 'Turbulence is the Dryden']:
            self.assertIn(words, text)
        _, r = wind.parse({'steady_ned_m_s': [0, 5, 0]})
        self.assertEqual(r, [])  # default start after airborne: nothing to warn about

    def test_turbulence_direction_follows_shear(self):
        config, _ = wind.parse({'shear': {'speed_6m_m_s': 2, 'from_deg': 250}, 'turbulence': {'speed_6m_m_s': 1}})
        self.assertEqual(config['turbulence_from_deg'], 250.0)

    def test_sitl_line_has_22_numbers(self):
        config, _ = wind.parse({'steady_ned_m_s': [1, 2, 0], 'gust': {'magnitude_m_s': [3, 2, 1]}})
        words = wind.sitl_line(config).split()
        self.assertEqual(words[0], 'wind')
        self.assertEqual(len(words) - 1, 22)

    def test_scene(self):
        scene, _ = load_scene(dict(GROUND, wind_ned_m_s=[0, 4, 0], wind={'start': {'ramp_s': 2}}))
        config, reminders = load_wind(scene)
        self.assertEqual(config['steady_ned_m_s'], [0.0, 4.0, 0.0])
        self.assertEqual(config['ramp_s'], 2.0)
        with self.assertRaises(ValueError):
            load_scene(dict(GROUND, wind={'gust': {'length_m': [0, 1, 1]}}))
        with self.assertRaises(ValueError):
            load_wind(dict(GROUND, wind_ned_m_s=[0, 4, 0], wind={'steady_ned_m_s': [0, 3, 0]}))


if __name__ == '__main__':
    unittest.main()
