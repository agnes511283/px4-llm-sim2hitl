"""macOS input and terminal appearance for the independent macOS renderer."""
import os
import signal
import sys
import termios
from macos_bridge_renderer import BridgeDashboard as MacDashboard, vehicle_label


class DashboardStream:
    """Give the alternate-screen dashboard a dark background on light profiles.

    Plain output and the final reset pass through unchanged. The shared renderer
    uses reset codes between rows; keep its dashboard background until close.
    """
    def __init__(self, stream):
        self.stream = stream

    def __getattr__(self, name):
        return getattr(self.stream, name)

    def write(self, text):
        if '\x1b[H' in text:
            text = '\x1b[40m' + text.replace('\x1b[0m', '\x1b[0;40m')
        return self.stream.write(text)


class BridgeDashboard(MacDashboard):
    def __init__(self, plain=False, stream=None):
        super().__init__(plain=plain, stream=DashboardStream(stream or sys.stdout))


class DeviceSelection:
    """Nonblocking character input while a device menu is visible; restore tty."""
    def __init__(self, display, stream=None):
        self.display = display
        self.stream = stream or sys.stdin
        self.choices = ()
        self.response = ''
        self._saved = None

    def set_choices(self, choices):
        choices = tuple(choices)
        if choices == self.choices:
            return
        if choices and self._saved is None and self.stream.isatty():
            fd = self.stream.fileno()
            saved = termios.tcgetattr(fd)
            mode = termios.tcgetattr(fd)
            mode[3] &= ~(termios.ICANON | termios.ECHO)
            mode[6][termios.VMIN] = 1
            mode[6][termios.VTIME] = 0
            termios.tcsetattr(fd, termios.TCSANOW, mode)
            self._saved = (fd, saved)
        if not choices:
            self.close()
        self.choices, self.response = choices, ''
        self.display.select(choices)

    def reader(self):
        return self.stream if self.choices and self._saved is not None else None

    def read(self):
        # Caller must select() this fd first. ICANON is disabled only in the menu.
        for char in os.read(self.stream.fileno(), 64).decode('ascii', errors='ignore'):
            if char == '\x03':
                os.kill(os.getpid(), signal.SIGINT)
                return None
            if char in '\r\n':
                answer, self.response = self.response, ''
                if answer.isdigit() and 1 <= int(answer) <= len(self.choices):
                    chosen = self.choices[int(answer)-1]
                    self.set_choices(())
                    return chosen
                self.display.select(self.choices, '', True)
            elif char in ('\b', '\x7f'):
                self.response = self.response[:-1]
                self.display.select(self.choices, self.response)
            elif char.isdigit() and len(self.response) < 4:
                self.response += char
                self.display.select(self.choices, self.response)
        return None

    def close(self):
        if self._saved is not None:
            fd, saved = self._saved
            self._saved = None
            termios.tcsetattr(fd, termios.TCSANOW, saved)
