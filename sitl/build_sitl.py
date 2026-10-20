#!/usr/bin/env python3
"""Build the SITL PX4 variant (PX4 + plant_sim) in its own build directory (sitl/README.md).

  python3 sitl/build_sitl.py [--plant-lib PATH]
  python3 sitl/build_sitl.py --replay

--replay builds PX4's own replay variant instead (`make px4_sitl_replay`, output in
<PX4 tree>/build/px4_sitl_replay): the default SITL board plus uORB publisher rules, used by sitl/replay.py
for the ULog replay. It has no plant_sim and needs no plant library.

1. Locates the PX4 source tree and checks it against px4/px4_lock.json (px4/check_px4_tree.py must PASS).
2. Picks the plant library: --plant-lib, or the cache of the active model release (its build.json records
   its plant library, published in the release next to the HIL library). A development build
   may point --plant-lib at a trial cache without publishing a release.
3. Runs `make px4_sitl_default EXTERNAL_MODULES_LOCATION=sitl/px4_external BUILD_DIR_SUFFIX=_sim2hitl`
   in the PX4 tree (incremental; output in <PX4 tree>/build/px4_sitl_default_sim2hitl, git-ignored).
   It never edits the PX4 tree's sources, and never touches build/px4_sitl_default.
   SIM2HITL_SITL_SUFFIX replaces _sim2hitl: a second checkout on the same machine (e.g. a fork next to the
   kit) that shares the PX4 tree sets its own, or each rebuild relinks the other's PX4 to its own plant.
4. Checks which plant library the built PX4 executable loads (loaded_library: macOS reads its install name
   through LC_RPATH with otool, Linux asks ldd). A file other than the plant library of step 2 is a FAIL: on
   macOS a library records the path it was compiled to, so without @rpath the executable loads the build cache.

Prints one JSON line (tree, plant library and its SHA-256, the library the executable loads, exit code, log path).
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'px4'))
sys.path.insert(0, str(ROOT / 'plant' / 'core'))
sys.path.insert(0, str(ROOT / 'hitl'))
from check_px4_tree import px4_root  # noqa: E402
import toolchain  # noqa: E402

LOGS = toolchain.cache_root()
BUILD_SUFFIX = os.environ.get('SIM2HITL_SITL_SUFFIX', '_sim2hitl')


def build_dir(tree):
    """This project's SITL build inside the PX4 tree (sitl/run_sitl.py runs its bin/px4)."""
    return tree / 'build' / f'px4_sitl_default{BUILD_SUFFIX}'


def active_plant_lib():
    """The plant library of the active model release (published next to the HIL library)."""
    from host.release import read_release

    release, manifest = read_release(ROOT / 'hitl')
    return release / manifest['plant_library']


def loaded_library(binary, name):
    """The file the dynamic loader opens for the library called `name` when `binary` runs, or None.
    macOS: the install name recorded in the binary (otool -L), with @rpath resolved through its LC_RPATH entries
    (otool -l); Linux: ldd."""
    if sys.platform == 'darwin':
        refs = [line.split(' (compatibility')[0].strip()
                for line in subprocess.check_output(['otool', '-L', str(binary)], text=True).splitlines()[1:]]
        ref = next((r for r in refs if Path(r).name == name), None)
        if ref is None or not ref.startswith('@rpath/'):
            return Path(ref) if ref else None
        load = subprocess.check_output(['otool', '-l', str(binary)], text=True).splitlines()
        rpaths = [load[k + 2].split('path ', 1)[1].rsplit(' (offset', 1)[0]
                  for k, line in enumerate(load[:-2]) if line.strip() == 'cmd LC_RPATH']
        for rpath in rpaths:
            folder = rpath.replace('@executable_path', str(binary.parent)).replace('@loader_path', str(binary.parent))
            if (Path(folder) / ref[len('@rpath/'):]).is_file():
                return Path(folder) / ref[len('@rpath/'):]
        return None
    for line in subprocess.check_output(['ldd', str(binary)], text=True).splitlines():
        if name in line:
            path = (line.split('=>', 1)[1] if '=>' in line else line).split(' (0x')[0].strip()
            return Path(path) if path and path != 'not found' else None
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--plant-lib', type=Path)
    parser.add_argument('--replay', action='store_true', help='build px4_sitl_replay (sitl/replay.py)')
    args = parser.parse_args()
    check = subprocess.run([sys.executable, str(ROOT / 'px4' / 'check_px4_tree.py')], capture_output=True, text=True)
    if check.returncode != 0:
        print(check.stdout + check.stderr)
        raise SystemExit('PX4 tree check did not PASS; see px4/README.md')
    tree = px4_root()
    LOGS.mkdir(parents=True, exist_ok=True)
    if args.replay:
        log = LOGS / f'sitl_replay_build_{time.strftime("%Y%m%d_%H%M%S")}.log'
        with open(log, 'w') as out:
            code = subprocess.run(['make', 'px4_sitl_replay'], cwd=tree, stdout=out, stderr=subprocess.STDOUT).returncode
        print(json.dumps({'status': 'PASS' if code == 0 else 'FAIL', 'tree': str(tree), 'target': 'px4_sitl_replay',
                          'exit': code, 'log': str(log)}))
        raise SystemExit(code)
    plant = (args.plant_lib or active_plant_lib()).resolve()
    if not plant.is_file():
        raise SystemExit(f'plant library not found: {plant}')
    log = LOGS / f'sitl_build_{time.strftime("%Y%m%d_%H%M%S")}.log'
    cmd = ['make', 'px4_sitl_default', f'EXTERNAL_MODULES_LOCATION={ROOT / "sitl" / "px4_external"}',
           f'BUILD_DIR_SUFFIX={BUILD_SUFFIX}', f'CMAKE_ARGS=-DPLANT_LIB={plant}']
    with open(log, 'w') as out:
        code = subprocess.run(cmd, cwd=tree, stdout=out, stderr=subprocess.STDOUT).returncode
    loads = loaded_library(build_dir(tree) / 'bin' / 'px4', plant.name) if code == 0 else None
    linked = loads is not None and loads.resolve() == plant
    print(json.dumps({'status': 'PASS' if code == 0 and linked else 'FAIL', 'tree': str(tree), 'plant_lib': str(plant),
                      'plant_lib_sha256': hashlib.sha256(plant.read_bytes()).hexdigest(),
                      'loads_plant_lib': str(loads) if loads else None, 'exit': code, 'log': str(log)}))
    if code == 0 and not linked:
        raise SystemExit(f'the PX4 executable loads {loads}, not {plant}')
    raise SystemExit(code)


if __name__ == '__main__':
    main()
