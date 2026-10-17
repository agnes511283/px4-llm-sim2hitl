#!/usr/bin/env python3
"""Compile the generated plant core into libskysurfer_core and, with C Truth and C sensors, into
libskysurfer_plant (shared libraries; compiler, MATLAB headers and suffix from toolchain.py).

  python3 plant/core/compile_core.py --cache <build cache>

The cache holds the generated code (hitl/update.py lays it out from model/generated). Output:
<cache>/native/libskysurfer_core.*, <cache>/native/libskysurfer_plant.* and
<cache>/results/core_compile.json (sources, SHA-256, compiler commands). Generated C is never edited.
"""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

import toolchain

CORE = Path(__file__).resolve().parent
PLANT = CORE.parent


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--cache', type=Path, required=True)
    args = parser.parse_args()
    gen = args.cache / 'codegen' / 'SkySurfer_Core_ert_rtw'
    out = args.cache / 'native'
    out.mkdir(exist_ok=True)
    makefile = (gen / 'SkySurfer_Core.mk').read_text()
    defines = []
    for key in ('DEFINES_BUILD_ARGS', 'DEFINES_OPTS', 'DEFINES_STANDARD'):
        match = re.search(rf'^{key}\s*=\s*(.*)$', makefile, re.M)
        defines += match.group(1).split() if match else []
    if '-DMULTI_INSTANCE_CODE=1' not in defines:
        raise RuntimeError('Generated core is not reusable (MULTI_INSTANCE_CODE != 1)')
    generated = [gen / name for name in ('SkySurfer_Core.c', 'SkySurfer_Core_data.c', 'rtGetInf.c', 'rtGetNaN.c', 'rt_nonfinite.c')]
    sources = generated + [CORE / 'sks_core.c']
    library = out / toolchain.lib('skysurfer_core')
    MATLAB = toolchain.matlab_root()
    cmd = toolchain.cc() + ['-std=c11', '-O2', '-fno-fast-math', '-ffp-contract=off'] + toolchain.shared_flags()
    for inc in (PLANT / 'include', gen, MATLAB / 'extern/include', MATLAB / 'simulink/include', MATLAB / 'rtw/c/src', MATLAB / 'rtw/c/ert'):
        cmd += ['-I', str(inc)]
    base = list(cmd) + ['-I', str(PLANT / 'sensors')] + defines + toolchain.model_defines(args.cache)
    cmd = base + [str(p) for p in sources] + ['-o', str(library)]
    subprocess.run(cmd, check=True)
    # Hand-written C is held to warnings-as-errors; generated C is compiled as generated.
    handwritten = [CORE / 'sks_core.c', PLANT / 'truth' / 'sks_plant.c', PLANT / 'sensors' / 'sks_sensors.c',
                   PLANT / 'sensors' / 'sks_wmm.c', PLANT / 'sensors' / 'sks_wmm_coeffs.c']
    for source in handwritten:
        check = [x for x in base if x not in toolchain.shared_flags()]
        subprocess.run(check + ['-Wall', '-Wextra', '-Werror', '-fsyntax-only', str(source)], check=True)
    plant_library = out / toolchain.lib('skysurfer_plant')
    plant_sources = sources + handwritten[1:]
    plant_cmd = base + [str(p) for p in plant_sources] + ['-o', str(plant_library)]
    subprocess.run(plant_cmd, check=True)
    # Every hand-written header the libraries include, so the record identifies the exact build inputs.
    headers = sorted((PLANT / 'include').glob('*.h')) + sorted((PLANT / 'sensors').glob('*.h'))
    record = {
        'library': str(library),
        'library_sha256': sha256(library),
        'plant_library': str(plant_library),
        'plant_library_sha256': sha256(plant_library),
        'sources': {str(p): sha256(p) for p in plant_sources},
        'headers': {str(p): sha256(p) for p in headers},
        'compiler': toolchain.compiler_version(),
        'command': cmd,
        'plant_command': plant_cmd,
    }
    (args.cache / 'results' / 'core_compile.json').write_text(json.dumps(record, indent=2))
    print(json.dumps({'status': 'PASS', 'library_sha256': record['library_sha256'],
                      'plant_library_sha256': record['plant_library_sha256']}))


if __name__ == '__main__':
    main()
