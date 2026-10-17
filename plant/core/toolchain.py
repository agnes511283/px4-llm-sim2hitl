"""Build environment, found on this machine instead of written into the code.

Every value can be set with an environment variable; when something cannot be found, the error says which
one to set. Verified on Ubuntu 24.04 x86-64 (gcc, MATLAB R2026b); on another platform check that these
answers fit before building.

  SKYSURFER_MATLAB_ROOT  MATLAB installation folder (default: from `matlab` on PATH)
  CC                     C compiler command (default: cc)
  SKYSURFER_CACHE        folder for build caches and runtime state (default: the platform's user cache)
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

LIB_SUFFIX = '.dylib' if sys.platform == 'darwin' else '.dll' if sys.platform == 'win32' else '.so'


def lib(name):
    """File name of a shared library built from this project, e.g. lib('skysurfer') -> libskysurfer.so."""
    return f'lib{name}{LIB_SUFFIX}'


def matlab_root():
    if os.environ.get('SKYSURFER_MATLAB_ROOT'):
        return Path(os.environ['SKYSURFER_MATLAB_ROOT'])
    exe = shutil.which('matlab')
    if exe:
        return Path(exe).resolve().parents[1]
    raise RuntimeError('MATLAB not found: put matlab on PATH or set SKYSURFER_MATLAB_ROOT')


def cc():
    """The C compiler as a command list."""
    return (os.environ.get('CC') or 'cc').split()


def shared_flags():
    return ['-dynamiclib'] if sys.platform == 'darwin' else ['-shared', '-fPIC']


def compiler_version():
    return subprocess.check_output(cc() + ['--version'], text=True)


def model_constants(cache):
    """Mass and gravity of the source model (Mass0 and g of model/FW_SkySurfer_InitialFunction.m), as
    build_core.m recorded them in <cache>/results/core_build.json."""
    import json

    build = json.loads((Path(cache) / 'results' / 'core_build.json').read_text())
    return float(build['mass_kg']), float(build['gravity_m_s2'])


def model_defines(cache):
    """Compiler defines that carry model constants into C Truth (plant/truth/sks_plant.c)."""
    mass, _ = model_constants(cache)
    return [f'-DSKS_MASS_KG={mass!r}']


def cache_root():
    if os.environ.get('SKYSURFER_CACHE'):
        return Path(os.environ['SKYSURFER_CACHE'])
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Caches' / 'SkySurfer'
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'SkySurfer'
    return Path(os.environ.get('XDG_CACHE_HOME') or Path.home() / '.cache') / 'SkySurfer'
