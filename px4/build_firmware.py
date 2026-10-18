#!/usr/bin/env python3
"""Build the FC firmware of a deploy recipe: locked PX4 + committed patches + modules of modules/src.

  python3 px4/build_firmware.py --release deploy/<name>

The recipe is deploy/<name>/firmware/firmware.json "recipe":
  {"make_target": "px4_fmu-v6c_default",
   "patches": [{"file": "px4/patches/<x>.patch", "repo": "platforms/nuttx/NuttX/nuttx"}],
   "modules": ["<module folder in modules/src>", ...]}

The user's PX4 tree (px4/check_px4_tree.py) is never changed. Builds run in a build tree next to it
(<tree>-build, or SIM2HITL_PX4_BUILD_TREE), copied from it once and reset to the locked commit before every
build. Each patch is committed in its repository with `git am`, committer = author and committer date = author
date, so the same patches give the same commits: the firmware then reports a NuttX hash (AUTOPILOT_VERSION
os_custom_version) that tells it apart from the native one, and deploy/check_params.py compares it.

Writes the firmware (.px4) and its parameter list next to firmware.json, records outputs, embedded identity,
flash use and the build in firmware.json ("flashed" is cleared), and the list's SHA-256 in params.json.
Stops when the PX4 tree check, a patch or the build fails. Prints one JSON line.
"""
import argparse
import datetime
import hashlib
import json
import lzma
import os
import shutil
import subprocess
import sys
import time
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'px4'))
sys.path.insert(0, str(ROOT / 'plant' / 'core'))
import check_px4_tree  # noqa: E402
import toolchain  # noqa: E402

LOCK = json.loads((ROOT / 'px4' / 'px4_lock.json').read_text())
# Fixed on purpose: the patch commits (and so the NuttX hash the FC reports) depend on this identity. Changing it
# changes the expected hash of every recipe with a patch.
COMMITTER = ['-c', 'user.name=SkySurfer build', '-c', 'user.email=build@skysurfer.invalid']


def portable(text, source, tree):
    """A recorded path or command without this machine's folders."""
    return (str(text).replace(str(tree), '<PX4 build tree>').replace(str(source), '<PX4 tree>')
            .replace(str(Path.home()), '~'))


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(tree, *args, env=None):
    result = subprocess.run(['git', '-C', str(tree), *args], capture_output=True, text=True, env=env)
    if result.returncode:
        raise SystemExit(f'git {" ".join(args)} in {tree} failed: {result.stderr.strip()[-800:]}')
    return result.stdout.strip()


def build_tree(source):
    """The build tree, reset to the locked commit with clean submodules (the user's tree is the source)."""
    tree = Path(os.environ.get('SIM2HITL_PX4_BUILD_TREE') or str(source) + '-build')
    if not tree.exists():
        # One copy of the user's tree (objects included, no network); its build outputs are left out.
        subprocess.run(['rsync', '-a', '--exclude=/build/', f'{source}/', f'{tree}/'], check=True)
    git(tree, 'checkout', '-q', '--detach', '--force', LOCK['commit'])
    git(tree, 'submodule', 'update', '-q', '--init', '--recursive', '--force')
    git(tree, 'submodule', 'foreach', '-q', '--recursive', 'git reset -q --hard && git clean -fdq')
    git(tree, 'clean', '-fdq')
    report, code = check_px4_tree.check(tree, LOCK)
    if code:
        raise SystemExit('build tree does not match the lock after the reset: ' + json.dumps(report))
    return tree


def apply_patches(tree, patches):
    applied = []
    for patch in patches:
        repo = tree / patch['repo']
        file = ROOT / patch['file']
        env = dict(os.environ, GIT_COMMITTER_NAME='SkySurfer build', GIT_COMMITTER_EMAIL='build@skysurfer.invalid')
        result = subprocess.run(['git', '-C', str(repo), *COMMITTER, 'am', '-q', '--committer-date-is-author-date',
                                 str(file)], capture_output=True, text=True, env=env)
        if result.returncode:
            subprocess.run(['git', '-C', str(repo), 'am', '--abort'], capture_output=True)
            raise SystemExit(f'patch {patch["file"]} does not apply in {patch["repo"]}: {result.stderr.strip()[-800:]}')
        applied.append({'file': patch['file'], 'sha256': sha256(file), 'repo': patch['repo'],
                        'commit': git(repo, 'rev-parse', 'HEAD')})
    return applied


def external_modules(work, modules):
    """An EXTERNAL_MODULES_LOCATION holding only this recipe's modules (links to modules/src)."""
    ext = work / 'ext'
    if ext.exists():
        shutil.rmtree(ext)
    (ext / 'src').mkdir(parents=True)
    for name in modules:
        if not (ROOT / 'modules' / 'src' / name / 'CMakeLists.txt').is_file():
            raise SystemExit(f'module {name} not found in modules/src')
        (ext / 'src' / name).symlink_to(ROOT / 'modules' / 'src' / name)
    listing = '\n'.join('\t' + name for name in modules)
    (ext / 'src' / 'CMakeLists.txt').write_text(f'set(config_module_list_external\n{listing}\n\tPARENT_SCOPE\n)\n')
    return ext


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--release', type=Path, required=True, help='deploy recipe folder, e.g. deploy/01_sdfix')
    args = parser.parse_args()
    release = args.release.resolve()
    info_path = release / 'firmware' / 'firmware.json'
    info = json.loads(info_path.read_text())
    recipe = info.get('recipe')
    if not recipe:
        raise SystemExit(f'{info_path} has no "recipe" (a prebuilt firmware such as 00_native is not rebuilt here)')
    source = check_px4_tree.px4_root()
    if check_px4_tree.check(source, LOCK)[1]:
        raise SystemExit('PX4 tree check did not PASS: python3 px4/check_px4_tree.py')
    work = toolchain.cache_root() / 'firmware' / release.name
    work.mkdir(parents=True, exist_ok=True)
    tree = build_tree(source)
    applied = apply_patches(tree, recipe.get('patches', []))
    modules = recipe.get('modules', [])
    target = recipe['make_target']
    suffix = '_' + release.name
    cmd = ['make', target, f'BUILD_DIR_SUFFIX={suffix}']
    if modules:
        cmd.append(f'EXTERNAL_MODULES_LOCATION={external_modules(work, modules)}')
    log = work / f'build_{time.strftime("%Y%m%d_%H%M%S")}.log'
    started = time.monotonic()
    # PX4's own switch to leave submodules as they are (Tools/check_submodules.sh): the build tree was reset to the
    # lock above and the patches are committed in their submodules on purpose. (CI=true would reset them.)
    env = dict(os.environ, GIT_SUBMODULES_ARE_EVIL='1')
    env.pop('CI', None)
    with open(log, 'w') as out:
        code = subprocess.run(cmd, cwd=tree, stdout=out, stderr=subprocess.STDOUT, env=env).returncode
    seconds = round(time.monotonic() - started, 1)
    if code:
        print(json.dumps({'status': 'FAIL', 'release': str(release), 'exit': code, 'log': str(log)}))
        raise SystemExit(code)
    outdir = tree / 'build' / (target + suffix)
    image = outdir / f'{target}.px4'
    params = outdir / 'parameters.json.xz'
    shutil.copy2(image, release / 'firmware' / image.name)
    shutil.copy2(params, release / 'firmware' / params.name)
    px4 = json.loads(image.read_text())
    listing = json.loads(lzma.decompress(params.read_bytes()))['parameters']
    nuttx = tree / 'platforms' / 'nuttx' / 'NuttX' / 'nuttx'
    info['outputs'] = {
        'firmware': {'file': image.name, 'sha256': sha256(image), 'size': image.stat().st_size},
        'image_bin': {'file': 'not kept (inside the .px4 image field)',
                      'sha256': hashlib.sha256(zlib.decompress(__import__('base64').b64decode(px4['image']))).hexdigest(),
                      'size': px4['image_size']},
        'parameters': {'file': params.name, 'sha256': sha256(params), 'count': len(listing),
                       'origin': 'PX4 build output, unmodified'},
    }
    info['embedded'] = {
        'board_id': px4['board_id'], 'git_identity': px4.get('git_identity'), 'git_hash': git(tree, 'rev-parse', 'HEAD'),
        'nuttx_git_hash': git(nuttx, 'rev-parse', 'HEAD'), 'image_size': px4['image_size'],
        'image_maxsize': px4['image_maxsize'], 'flash_used_percent': round(100 * px4['image_size'] / px4['image_maxsize'], 2),
    }
    info['build'] = {
        'command': portable(' '.join(cmd), source, tree), 'build_tree': '<PX4 build tree>',
        'output_dir': portable(outdir, source, tree), 'patches': applied,
        'modules': {name: {p.name: sha256(p) for p in sorted((ROOT / 'modules' / 'src' / name).glob('*')) if p.is_file()}
                    for name in modules},
        'toolchain': subprocess.run(['arm-none-eabi-gcc', '--version'], capture_output=True, text=True).stdout.splitlines()[0],
        'built_at_utc': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'), 'seconds': seconds,
        'log': portable(log, source, tree),
    }
    info['flashed'] = None
    info_path.write_text(json.dumps(info, indent=2, ensure_ascii=False) + '\n')
    config_path = release / 'params.json'
    config = json.loads(config_path.read_text())
    config['firmware_params'] = {'file': 'firmware/' + params.name, 'sha256': sha256(params)}
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'status': 'PASS', 'release': str(release), 'firmware_sha256': info['outputs']['firmware']['sha256'],
                      'git_hash': info['embedded']['git_hash'], 'nuttx_git_hash': info['embedded']['nuttx_git_hash'],
                      'flash_used_percent': info['embedded']['flash_used_percent'], 'seconds': seconds, 'log': str(log)}))


if __name__ == '__main__':
    main()
