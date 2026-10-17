"""GUI client for one pinned owner; creates no model or serial connection."""

import copy
import json
import socket
import threading
import time
import uuid
from .ipc import read_reply, request, state_path, whole_operation


class RemoteCore:
    # Attached GUI client: closing its window must not stop the owner.
    attached = True

    def __init__(self, runtime, status, fake_state_dir=None):
        self.runtime = runtime
        self.fake_state_dir = fake_state_dir
        self.operation_lock = threading.RLock()
        self.lock = threading.Lock()
        self.quit = threading.Event()
        self.latest = copy.deepcopy(status)
        self.instance_id = status['instance_id']
        self.manifest = {'build_id': status['build_id']}
        self.last_success = time.monotonic()
        self.connection_error = None
        self._command_context = None

    @property
    def scene(self):
        with self.lock:
            return copy.deepcopy(self.latest['scene'])

    @property
    def state(self):
        return self.latest['model']

    @property
    def recovery_required(self):
        return self.latest['recovery_required']

    @property
    def unarmed_only(self):
        return self.latest.get('unarmed_only', False)

    def status(self):
        try:
            result = request(self.runtime, 'status', fake_state_dir=self.fake_state_dir)
            value = result.get('result')
            if result.get('status') != 'complete' or not isinstance(value, dict):
                raise RuntimeError(result.get('error') or 'owner status incomplete')
            if value.get('instance_id') != self.instance_id:
                raise RuntimeError('Owner changed; reopen the attached window')
            with self.lock:
                self.latest = copy.deepcopy(value)
                self.last_success = time.monotonic()
                self.connection_error = None
            return copy.deepcopy(value)
        except Exception as exc:
            self.connection_error = str(exc)
            raise

    def begin_commands(self, expected):
        self._command_context = expected

    def end_commands(self):
        self._command_context = None

    def _send_pinned(self, action, args, ident, run_id):
        # CLI's request() discovers its owner each time. This GUI must stay pinned
        # even if host.json is replaced after the last read. Do not alter the
        # server protocol or read-only CLI behavior to implement that distinction.
        data = json.loads((state_path(self.runtime, self.fake_state_dir) / 'host.json').read_text())
        if data.get('instance_id') != self.instance_id:
            raise RuntimeError('Owner changed; command not sent')
        payload = {
            'token': data['token'],
            'instance_id': self.instance_id,
            'request_id': ident,
            'action': action,
            'arguments': args or {},
            'run_id': run_id,
        }
        with socket.create_connection(('127.0.0.1', data['port']), timeout=3) as sock:
            sock.sendall((json.dumps(payload) + '\n').encode())
            with sock.makefile('rb') as stream:
                return read_reply(stream)

    def command(self, action, args=None):
        if self.connection_error or time.monotonic() - self.last_success > 1:
            raise RuntimeError('Owner status is stale; check the connection before retrying')
        with self.lock:
            run_id = (
                self._command_context[1]
                if self._command_context is not None
                else self.latest.get('run_id')
            )
        ident = str(uuid.uuid4())
        result = self._send_pinned(action, args, ident, run_id)
        if result.get('status') == 'accepted':
            deadline = time.monotonic() + (90 if action == 'recover' else 45)
            while time.monotonic() < deadline:
                time.sleep(0.05)
                try:
                    status = self._send_pinned('status', None, str(uuid.uuid4()), None)
                except OSError:
                    if action == 'shutdown':
                        return  # Preserve the existing accepted-shutdown semantics.
                    raise
                op = next(
                    (
                        x
                        for x in status.get('result', {}).get('operations', [])
                        if x.get('request_id') == ident
                    ),
                    None,
                )
                if op and op.get('state') in ['complete', 'failed']:
                    value = status.get('result', {})
                    if value.get('instance_id') != self.instance_id:
                        raise RuntimeError('Owner changed; stopping further operations')
                    if value.get('operations_summarized'):
                        op = whole_operation(
                            lambda: self._send_pinned('operation', {'request_id': ident}, str(uuid.uuid4()), None),
                            op,
                        )
                    with self.lock:
                        self.latest = copy.deepcopy(value)
                        self.last_success = time.monotonic()
                    if op['state'] == 'complete' and self._command_context is not None:
                        self._command_context = (
                            self.instance_id,
                            value.get('run_id'),
                            value.get('fc', {}).get('connection_generation'),
                        )
                    result = {'status': op['state'], 'operation': op}
                    break
            else:
                raise RuntimeError('Operation wait timed out; result unknown. Check status; the command was not resent')
        if result.get('status') != 'complete':
            raise RuntimeError(
                result.get('error') or result.get('operation', {}).get('error') or str(result)
            )

    def start(self, scene):
        self.command('model-start', {'scene': scene})

    def stop(self):
        self.command('model-stop')

    def reset(self, scene):
        self.command('model-reset', {'scene': scene})

    def recover(self):
        self.command('recover')

    def close(self, force=False):
        self.command('shutdown', {'force': force})
        self.quit.set()
