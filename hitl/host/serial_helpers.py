"""Serial-port and MAVLink frame helpers of the runtime (devices, owner check, frame scan).

Taken unchanged from the former terminal bridge (hil_bridge/macos/bridge/fw_hil_macos_bridge.py in the
FW_SkySurfer project), keeping only what the runtime uses: SerialTransport finds and opens the FC with
devices / choose_device / serial_owner, and Core separates joystick frames with split_manual_control.
Device names: macOS callout nodes, Linux CDC-ACM / USB-serial nodes; check them on another platform.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import sys

os.environ.setdefault('MAVLINK20', '1')
from serial.tools import list_ports  # noqa: E402
from pymavlink import mavutil  # noqa: E402

try:
    from fastcrc.crc16 import mcrf4xx
except ImportError:
    from pymavlink.generator.mavcrc import x25crc

    def mcrf4xx(data: bytes) -> int:
        return x25crc(data).crc


MANUAL_CONTROL_MSG_ID = 69

CRC_EXTRA = {msgid: bytes((message.crc_extra,))
             for msgid, message in mavutil.mavlink.mavlink_map.items()}
AUTOPILOT_USB_VIDS = frozenset((0x26AC, 0x2DAE, 0x3162, 0x3185))


def is_likely_pixhawk(port: object) -> bool:
    if getattr(port, 'vid', None) in AUTOPILOT_USB_VIDS:
        return True
    attributes = (
        getattr(port, "device", ""),
        getattr(port, "description", ""),
        getattr(port, "manufacturer", ""),
        getattr(port, "product", ""),
        getattr(port, "hwid", ""),
    )
    identity = " ".join(str(value or "") for value in attributes).lower()
    keywords = (
        "pixhawk",
        "px4",
        "autopilot",
        "cubeorange",
        "cubepilot",
        "holybro",
    )
    return any(keyword in identity for keyword in keywords)


# USB serial nodes: macOS callout devices (any /dev/cu.* listed with USB metadata), Linux CDC-ACM and USB-serial.
if sys.platform == 'darwin':
    USB_SERIAL_PREFIXES = ('/dev/cu.usbmodem', '/dev/cu.usbserial')
    DEVICE_PREFIXES = ('/dev/cu.',)
else:
    USB_SERIAL_PREFIXES = DEVICE_PREFIXES = ('/dev/ttyACM', '/dev/ttyUSB')


def is_usb_serial(port):
    hwid = str(getattr(port, 'hwid', '') or '').upper()
    path = str(getattr(port, 'device', '') or '')
    if 'Bluetooth' in path or hwid.startswith('BTHENUM'):
        return False
    return (getattr(port, 'vid', None) is not None or hwid.startswith('USB')
            or path.startswith(USB_SERIAL_PREFIXES))


@dataclass(frozen=True)
class Device:
    path: str
    identity: str
    label: str
    priority: int = 1


def device_identity(port):
    """Serial numbers such as 0 are placeholders; prefer USB location instead."""
    serial_number = str(getattr(port, 'serial_number', '') or '').strip()
    base = f"usb:{getattr(port, 'vid', None)}:{getattr(port, 'pid', None)}"
    if (serial_number.lower() not in {'', 'unknown', 'none', 'n/a'}
            and serial_number.replace('-', '').strip('0')):
        return f'{base}:serial:{serial_number}'
    location = getattr(port, 'location', None)
    if location:
        return f'{base}:location:{location}'
    return 'path:' + port.device


def usb_callout_paths():
    """Rescan /dev on every discovery attempt, including late USB attachment."""
    root = Path('/dev')
    return sorted({str(path) for prefix in USB_SERIAL_PREFIXES
                   for path in root.glob(prefix[len('/dev/'):] + '*')})


def devices():
    """Enumerate USB serial devices (macOS callout or Linux ACM/USB nodes); retain USB identity across renumbering."""
    result = []
    for port in list_ports.comports():
        if not is_usb_serial(port) or not port.device.startswith(DEVICE_PREFIXES):
            continue
        identity = device_identity(port)
        result.append(Device(port.device, identity, port.description or port.device,
                             0 if is_likely_pixhawk(port) else 1))
    listed = {item.path for item in result}
    for path in usb_callout_paths():
        if path not in listed:
            result.append(Device(path, 'path:' + path, path))
    return sorted(result, key=lambda item: (item.priority, item.path))


def choose_device(found, preferred=None, requested='auto'):
    if preferred is not None:
        matches = [d for d in found if d.identity == preferred.identity]
        if not matches and preferred.identity.startswith('path:'):
            # IOKit metadata may appear after /dev created the USB callout node.
            matches = [d for d in found if d.path == preferred.path]
        return matches[0] if len(matches) == 1 else None
    if requested != 'auto':
        match = next((d for d in found if os.path.realpath(d.path) == os.path.realpath(requested)), None)
        if match:
            return match
        return Device(requested, 'path:' + requested, requested) if Path(requested).exists() else None
    return found[0] if len(found) == 1 else None


def serial_owner(path):
    """Check both Darwin names (or the one Linux node) for the same device before opening it."""
    paths = [path]
    if path.startswith('/dev/cu.'):
        paths.append('/dev/tty.' + path[len('/dev/cu.'):])
    try:
        lsof = '/usr/sbin/lsof' if Path('/usr/sbin/lsof').exists() else shutil.which('lsof') or 'lsof'
        result = subprocess.run([lsof, '-t', '--', *paths],
                                capture_output=True, text=True, timeout=2, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OSError(f'Cannot check serial port owner: {exc}') from exc
    owners = [line for line in result.stdout.splitlines()
              if line.isdigit() and int(line) != os.getpid()]
    return ','.join(sorted(set(owners))) or None


def scan_frames(data):
    """Locate complete CRC-valid MAVLink v1/v2 frames without decoding payloads.

    Returns (frames, end, bad): frames holds (msgid, start, stop) slices, end is
    the start of a trailing partial frame, and bad counts CRC failures. A CRC
    failure resynchronizes one byte later. Unknown IDs cannot be CRC-checked, so
    they are skipped only when the next frame start is where their length says.
    """
    frames = []
    bad = 0
    size = len(data)
    index = 0
    while index < size:
        stx = data[index]
        if stx == 0xFD:
            if size - index < 10:
                break
            length = data[index+1]
            msgid = data[index+7] | data[index+8] << 8 | data[index+9] << 16
            crc_at = index + 10 + length
            stop = crc_at + (15 if data[index+2] & 1 else 2)
        elif stx == 0xFE:
            if size - index < 6:
                break
            length = data[index+1]
            msgid = data[index+5]
            crc_at = index + 6 + length
            stop = crc_at + 2
        else:
            v2 = data.find(b'\xfd', index)
            v1 = data.find(b'\xfe', index)
            candidates = [found for found in (v1, v2) if found >= 0]
            index = min(candidates) if candidates else size
            continue
        if stop > size:
            break
        extra = CRC_EXTRA.get(msgid)
        if extra is None:
            index = stop if stop == size or data[stop] in (0xFD, 0xFE) else index + 1
            continue
        if mcrf4xx(bytes(data[index+1:crc_at]) + extra) != data[crc_at] | data[crc_at+1] << 8:
            bad += 1
            index += 1
            continue
        frames.append((msgid, index, stop))
        index = stop
    return frames, index, bad


def split_manual_control(raw):
    """Separate CRC-valid joystick frames, preserving every other byte."""
    found = [(start, stop) for msgid, start, stop in scan_frames(raw)[0]
             if msgid == MANUAL_CONTROL_MSG_ID]
    if not found:
        return raw, b''
    rest = []
    index = 0
    for start, stop in found:
        rest.append(raw[index:start])
        index = stop
    rest.append(raw[index:])
    return b''.join(rest), b''.join(raw[start:stop] for start, stop in found)
