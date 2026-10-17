import hashlib, json, platform, sys
from pathlib import Path


def platform_id():
    machine = platform.machine().lower()
    return (
        'macos-'
        if sys.platform == 'darwin'
        else 'windows-' if sys.platform == 'win32'
        else 'linux-' if sys.platform.startswith('linux') else 'unsupported-'
    ) + (
        'arm64'
        if machine in ['arm64', 'aarch64']
        else 'x64' if machine in ['amd64', 'x86_64'] else machine
    )


def read_release(runtime, pointer=None):
    runtime = Path(runtime).resolve()
    pid = platform_id()
    ptr = Path(pointer) if pointer else runtime / 'active' / f'{pid}.json'
    active = json.loads(ptr.read_text())
    release = (runtime / active['release']).resolve()
    if runtime / 'releases' not in release.parents:
        raise ValueError('Release path escapes release tree')
    manifest_file = release / 'manifest.json'
    if active.get('manifest_sha256') != hashlib.sha256(manifest_file.read_bytes()).hexdigest():
        raise ValueError('Release manifest checksum mismatch')
    manifest = json.loads(manifest_file.read_text())
    if manifest['platform'] != pid or active['build_id'] != manifest['build_id']:
        raise ValueError('Platform/build mismatch')
    for rel, digest in manifest['files'].items():
        p = (release / rel).resolve()
        if release not in p.parents or hashlib.sha256(p.read_bytes()).hexdigest() != digest:
            raise ValueError('Release checksum mismatch: ' + rel)
    if manifest.get('required_status') != 'PASS':
        raise ValueError('Release required checks did not pass')
    return release, manifest
