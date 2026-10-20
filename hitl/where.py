"""This machine's paths for the kit, found the way the tools find them (read-only).

  ./runbridge where           one JSON object
  ./runbridge where NAME      only that value (nothing, exit 1, when it is not set), for scripts:
                              PY="$(./runbridge where python)"

The docs point here instead of spelling out one platform's folders (Linux ~/.cache/..., macOS ~/Library/...):
  python          the project's venv interpreter (the one running this)
  venv            its environment folder (SIM2HITL_VENV)
  cache           build caches, SITL runs, logs and run evidence (plant/core/toolchain.py cache_root)
  runtime_state   the owner's state folder of this project folder (hitl/host/ipc.py state_path)
  px4_config      the file that remembers the PX4 tree (px4/check_px4_tree.py)
  px4_tree        the PX4 tree as configured, or null when its location is not set
  px4_sitl        the SITL build's px4 executable (sitl/build_sitl.py build_dir, SIM2HITL_SITL_SUFFIX), or null
  platform        this machine's release platform (linux-x64, macos-arm64, ...)
  release         the active model release, or null (release_problem says why)
  plant_library   its plant library (the one sitl/build_sitl.py links), or null
"""
import json
import os
import sys
from pathlib import Path

RUNTIME = Path(__file__).resolve().parent
ROOT = RUNTIME.parent
sys.path.insert(0, str(RUNTIME))
sys.path.insert(0, str(ROOT / 'plant' / 'core'))
sys.path.insert(0, str(ROOT / 'px4'))
sys.path.insert(0, str(ROOT / 'sitl'))
import check_px4_tree  # noqa: E402
import toolchain  # noqa: E402
from build_sitl import build_dir  # noqa: E402
from host.ipc import state_path  # noqa: E402
from host.release import platform_id, read_release  # noqa: E402


def paths():
    tree, _ = check_px4_tree.locate(None)
    px4 = build_dir(tree) / 'bin' / 'px4' if tree else None
    value = {'python': sys.executable, 'venv': os.environ.get('UV_PROJECT_ENVIRONMENT') or sys.prefix,
             'cache': str(toolchain.cache_root()), 'runtime_state': str(state_path(RUNTIME)),
             'px4_config': str(check_px4_tree.config_file()), 'px4_tree': str(tree) if tree else None,
             'px4_sitl': str(px4) if px4 and px4.is_file() else None, 'platform': platform_id(),
             'release': None, 'plant_library': None}
    try:
        release, manifest = read_release(RUNTIME)
        value['release'] = str(release)
        if manifest.get('plant_library'):
            value['plant_library'] = str(release / manifest['plant_library'])
    except (OSError, ValueError, KeyError) as exc:
        value['release_problem'] = str(exc) or type(exc).__name__
    return value


def main(argv):
    value = paths()
    if not argv:
        print(json.dumps(value, indent=2))
        return 0
    if len(argv) > 1 or argv[0] not in value:
        print('usage: ./runbridge where [' + '|'.join(value) + ']', file=sys.stderr)
        return 2
    if value[argv[0]] is None:
        return 1
    print(value[argv[0]])
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
