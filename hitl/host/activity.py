"""macOS App Nap guard: a process-scoped NSProcessInfo activity (user initiated, latency critical).

Core holds one from model start to model stop, so the owner process asks for the highest timer precision
while the 4 ms worker runs, also in the background (the GUI's own activity starts only when its status poll
sees the model running). Apple documents these options as hints, not a deadline guarantee. The GUI session uses
the same class for its operations.
"""

import threading


class MacActivity:
    """Process-scoped latency activity while HIL/operations run; no global settings.

    Options from Apple's NSProcessInfo.h: user initiated allowing idle system
    sleep, plus latency critical. Idle/display sleep flags are not requested.
    """

    def __init__(self):
        import sys

        self.supported = sys.platform == 'darwin'
        self.token = None
        self.error = None
        self.options = (0x00FFFFFF & ~(1 << 20)) | 0xFF00000000
        self.process = None
        self.lock = threading.Lock()  # Core: start (operation thread) and fault/stop (I/O loop)

    def _begin(self):
        import ctypes as C

        self.foundation = C.CDLL('/System/Library/Frameworks/Foundation.framework/Foundation')
        self.objc = C.CDLL('/usr/lib/libobjc.A.dylib')
        self.objc.objc_getClass.argtypes = [C.c_char_p]
        self.objc.objc_getClass.restype = C.c_void_p
        self.objc.sel_registerName.argtypes = [C.c_char_p]
        self.objc.sel_registerName.restype = C.c_void_p
        address = C.cast(self.objc.objc_msgSend, C.c_void_p).value
        self.send = C.CFUNCTYPE(C.c_void_p, C.c_void_p, C.c_void_p)(address)
        self.send_string = C.CFUNCTYPE(C.c_void_p, C.c_void_p, C.c_void_p, C.c_char_p)(address)
        self.begin = C.CFUNCTYPE(C.c_void_p, C.c_void_p, C.c_void_p, C.c_uint64, C.c_void_p)(
            address
        )
        self.end = C.CFUNCTYPE(None, C.c_void_p, C.c_void_p, C.c_void_p)(address)
        self.objc.objc_retain.argtypes = [C.c_void_p]
        self.objc.objc_retain.restype = C.c_void_p
        self.objc.objc_release.argtypes = [C.c_void_p]
        self.objc.objc_release.restype = None
        self.process = self.send(
            self.objc.objc_getClass(b'NSProcessInfo'), self.objc.sel_registerName(b'processInfo')
        )
        reason = self.send_string(
            self.objc.objc_getClass(b'NSString'),
            self.objc.sel_registerName(b'stringWithUTF8String:'),
            b'SkySurfer HIL 4ms model and GUI operations',
        )
        token = self.begin(
            self.process,
            self.objc.sel_registerName(b'beginActivityWithOptions:reason:'),
            self.options,
            reason,
        )
        if not token:
            raise RuntimeError('NSProcessInfo activity unavailable')
        return self.objc.objc_retain(token)

    def _end(self, token):
        self.end(self.process, self.objc.sel_registerName(b'endActivity:'), token)
        self.objc.objc_release(token)

    def set_active(self, active):
        """True when the requested state holds afterwards (always on platforms without App Nap)."""
        if not self.supported:
            return True
        with self.lock:
            self._set_active(active)
            return bool(self.token) == bool(active)

    def _set_active(self, active):
        try:
            if active and not self.token:
                self.token = self._begin()
                self.error = None
            elif not active and self.token:
                self._end(self.token)
                self.token = None
        except Exception as exc:
            self.error = str(exc)

    def diagnostics(self):
        with self.lock:  # one consistent snapshot
            return {
                'supported': self.supported,
                'active': bool(self.token),
                'error': self.error,
                'options': hex(self.options),
            }
