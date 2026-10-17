import hashlib, json, os, secrets, socket, socketserver, sys, threading, uuid
from pathlib import Path
from .errors import PreconditionError

# A request is one short line. status lists the operations only as bounded summaries (Core._operations_view);
# one whole operation ('operation' request) can still carry a large result (log list, readback summary).
REPLY_LIMIT = 4 * 1024 * 1024
KEEP_FINISHED = 32  # finished operations kept for their clients; an unfinished one is never dropped
MAX_UNFINISHED = 16  # accepted or running operations at once; more are refused (the status list stays bounded)
ACTIONS = {'model-start', 'model-stop', 'model-reset', 'stop-takeoff', 'takeoff', 'read-parameters', 'param-plan',
           'param-deploy', 'param-readback', 'fetch-log', 'sd-list', 'sd-get', 'sd-put', 'sd-rm', 'recover', 'reboot',
           'shutdown', 'recover-and-exit'}
_operations_lock = threading.Lock()


def remember(operations, op):
    """Append an accepted operation and return it; drop the oldest finished ones beyond KEEP_FINISHED, never one
    that is still accepted or running (its client is waiting for it). In the same locked step: an operation with
    the same request_id already kept is returned instead (the caller answers with it and runs nothing again), and
    with MAX_UNFINISHED unfinished ones already the new one is refused (PreconditionError): nothing waiting is
    dropped and the list stays bounded."""
    with _operations_lock:
        same = next((o for o in list(operations) if o['request_id'] == op['request_id']), None)
        if same is not None:
            return same
        if sum(o['state'] not in ['complete', 'failed'] for o in list(operations)) >= MAX_UNFINISHED:
            raise PreconditionError(f'Owner busy: {MAX_UNFINISHED} operations are already waiting; retry later')
        operations.append(op)
        finished = [o for o in list(operations) if o['state'] in ['complete', 'failed']]
        for old in finished[:max(0, len(finished) - KEEP_FINISHED)]:
            operations.remove(old)
        return op


def read_reply(stream):
    """One JSON reply line from the owner. A reply cut off before its newline is an error, not JSON garbage."""
    raw = stream.readline(REPLY_LIMIT + 1)
    if not raw.endswith(b'\n'):
        raise ValueError(f'Management reply incomplete or larger than {REPLY_LIMIT} bytes ({len(raw)} bytes read)')
    return json.loads(raw)


def cache_root():
    """Per-user cache for owner state and run evidence: one rule for the whole project (plant/core/toolchain.py)."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'plant' / 'core'))
    import toolchain

    return toolchain.cache_root()


def state_path(runtime, fake_state_dir=None):
    if fake_state_dir is not None:
        return Path(fake_state_dir).resolve()
    key = hashlib.sha256(str(Path(runtime).resolve()).encode()).hexdigest()[:12]
    base = (
        Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) / 'PX4HIL/Runtime'
        if sys.platform == 'win32'
        else cache_root() / 'runtime'
    )
    return base / key


def reserve(runtime, fake_state_dir=None):
    path = state_path(runtime, fake_state_dir)
    path.mkdir(parents=True, exist_ok=True)
    lock = (path / 'owner.lock').open('a+')
    try:
        if sys.platform == 'win32':
            import msvcrt

            lock.write('0')
            lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        lock.close()
        raise PreconditionError('Another host owns this project')
    return lock


class Endpoint:
    def __init__(self, core, lease=None):
        self.core = core
        self.path = state_path(core.runtime, core.fake_state_dir)
        self.path.mkdir(parents=True, exist_ok=True)
        self.lock = lease or reserve(core.runtime, core.fake_state_dir)
        self.token = secrets.token_hex(32)
        owner = self

        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                self.connection.settimeout(3)
                try:
                    raw = self.rfile.readline(65537)
                    if len(raw) > 65536:
                        raise ValueError('Request too large')
                    request = json.loads(raw)
                    if (
                        not secrets.compare_digest(str(request.get('token', '')), owner.token)
                        or request.get('instance_id') != core.instance_id
                    ):
                        raise ValueError('Instance authentication failed')
                    ident = request['request_id']
                    action = request['action']
                    args = request.get('arguments', {})
                    if not isinstance(ident, str) or not 0 < len(ident) <= 64:
                        raise ValueError('request_id must be a string of 1 to 64 characters')
                    if action not in ACTIONS | {'status', 'operation'}:
                        raise ValueError(f'Unknown operation {str(action)[:64]}')
                    prior = next((o for o in list(core.operations) if o['request_id'] == ident), None)
                    if prior:
                        self.wfile.write(
                            (
                                json.dumps(
                                    {
                                        'status': (
                                            prior['state']
                                            if prior['state'] in ['complete', 'failed']
                                            else 'accepted'
                                        ),
                                        'request_id': ident,
                                        'operation': prior,
                                    }
                                )
                                + '\n'
                            ).encode()
                        )
                        return
                    if action == 'status':
                        response = {
                            'status': 'complete',
                            'request_id': ident,
                            'result': core.status(),
                        }
                    elif action == 'operation':
                        # One whole operation by its request_id (status lists only summaries); read-only.
                        wanted = args.get('request_id')
                        found = next((o for o in list(core.operations) if o['request_id'] == wanted), None)
                        response = (
                            {'status': 'complete', 'request_id': ident, 'operation': found}
                            if found
                            else {'status': 'failed', 'request_id': ident,
                                  'error': f'The owner does not keep operation {wanted}'}
                        )
                    else:
                        op = {
                            'request_id': ident,
                            'action': action,
                            'state': 'accepted',
                            'error': None,
                        }
                        kept = remember(core.operations, op)
                        if kept is not op:
                            # The same request_id arrived twice at once: answer with the first, run nothing again.
                            self.wfile.write((json.dumps({
                                'status': kept['state'] if kept['state'] in ['complete', 'failed'] else 'accepted',
                                'request_id': ident, 'operation': kept}) + '\n').encode())
                            return

                        def perform():
                            try:
                                with core.operation_lock:
                                    if request.get('run_id') != core.run_id:
                                        raise RuntimeError(
                                            'Request belongs to an earlier model run; query status and retry'
                                        )
                                    op['state'] = 'running'
                                    if action == 'model-start':
                                        core.start(args.get('scene'))
                                    elif action == 'model-stop':
                                        core.stop()
                                    elif action == 'model-reset':
                                        core.reset(args.get('scene'))
                                    elif action == 'stop-takeoff':
                                        core.stop_pilot()
                                    elif action == 'takeoff':
                                        op['result'] = core.takeoff(args.get('argv', []))
                                    elif action == 'read-parameters':
                                        op['result'] = core.read_parameters(args.get('names', []))
                                    elif action in ['param-plan', 'param-deploy']:
                                        if not args.get('out'):
                                            raise ValueError(action + ' needs an output directory')
                                        run = core.param_plan if action == 'param-plan' else core.param_deploy
                                        op['result'] = run(args.get('out'), args.get('release'))
                                    elif action == 'param-readback':
                                        if not args.get('out'):
                                            raise ValueError('param-readback needs an output directory')
                                        op['result'] = core.param_readback(args.get('out'), core.release_param_list(args.get('release')))
                                    elif action == 'fetch-log':
                                        if not args.get('out') and not args.get('list'):
                                            raise ValueError('fetch-log needs an output directory')
                                        op['result'] = core.fetch_log(args.get('out'), args.get('log_id'),
                                                                      bool(args.get('list')))
                                    elif action == 'sd-list':
                                        op['result'] = core.sd_list(args.get('sd_path') or '/fs/microsd/etc')
                                    elif action in ['sd-get', 'sd-put', 'sd-rm']:
                                        if not args.get('out') or not args.get('sd_path'):
                                            raise ValueError(action + ' needs an output directory and an SD path')
                                        if action == 'sd-get':
                                            op['result'] = core.sd_get(args['sd_path'], args['out'])
                                        elif action == 'sd-put':
                                            if not args.get('file'):
                                                raise ValueError('sd-put needs a local file')
                                            op['result'] = core.sd_put(args['file'], args['sd_path'], args['out'])
                                        else:
                                            op['result'] = core.sd_remove(args['sd_path'], args['out'])
                                    elif action in ['recover', 'reboot']:
                                        if action == 'reboot' and core.state == 'running':
                                            raise RuntimeError('Model running; use recover')
                                        core.recover(
                                            allow_hil_force_disarm=bool(
                                                args.get('hil_force_disarm', False)
                                            )
                                        )
                                    elif action == 'shutdown':
                                        core.close(args.get('force', False))
                                    elif action == 'recover-and-exit':
                                        core.recover(
                                            allow_hil_force_disarm=bool(
                                                args.get('hil_force_disarm', False)
                                            )
                                        )
                                        core.close()
                                    else:
                                        raise ValueError('Unknown operation')
                                    op['state'] = 'complete'
                            except Exception as exc:
                                op['state'] = 'failed'
                                op['error'] = str(exc)
                                op['exit_code'] = getattr(
                                    exc, 'exit_code', 4 if isinstance(exc, ValueError) else 3
                                )

                        threading.Thread(target=perform, name='hil-operation', daemon=True).start()
                        response = {'status': 'accepted', 'request_id': ident, 'operation': op}
                    self.wfile.write((json.dumps(response, allow_nan=False) + '\n').encode())
                except Exception as exc:
                    self.wfile.write(
                        (json.dumps({'status': 'failed', 'error': str(exc)}) + '\n').encode()
                    )

        class Server(socketserver.ThreadingTCPServer):
            allow_reuse_address = False
            daemon_threads = True

        try:
            self.server = Server(('127.0.0.1', 0), Handler)
        except Exception:
            self.lock.close()
            raise
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.file = self.path / 'host.json'
        temp = self.path / 'host.tmp'
        temp.write_text(
            json.dumps(
                {
                    'port': self.server.server_address[1],
                    'token': self.token,
                    'instance_id': core.instance_id,
                    'pid': os.getpid(),
                }
            )
        )
        os.chmod(temp, 0o600)
        os.replace(temp, self.file)

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.file.unlink(missing_ok=True)
        self.lock.close()


def whole_operation(ask, summary):
    """The whole finished operation (status lists only its summary); the summary, marked, if the owner cannot
    give it any more."""
    try:
        reply = ask()
    except (OSError, ValueError) as exc:
        return dict(summary, result_error=f'whole result not received ({exc})')
    op = reply.get('operation')
    if reply.get('status') != 'complete' or not op or op.get('request_id') != summary['request_id']:
        return dict(summary, result_error=str(reply.get('error') or 'whole result not received'))
    return op


def request(runtime, action, arguments=None, wait=True, fake_state_dir=None, timeout_s=45):
    file = state_path(runtime, fake_state_dir) / 'host.json'
    if not file.exists():
        raise PreconditionError('No running HIL host; start runbridge first')
    data = json.loads(file.read_text())
    ident = str(uuid.uuid4())

    def send(action, args, request_id):
        with socket.create_connection(('127.0.0.1', data['port']), timeout=3) as sock:
            payload = {
                'token': data['token'],
                'instance_id': data['instance_id'],
                'request_id': request_id,
                'action': action,
                'arguments': args or {},
                'run_id': expected_run_id,
            }
            sock.sendall((json.dumps(payload) + '\n').encode())
            with sock.makefile('rb') as stream:
                return read_reply(stream)

    expected_run_id = None
    if action != 'status':
        expected_run_id = send('status', {}, str(uuid.uuid4())).get('result', {}).get('run_id')
    result = send(action, arguments, ident)
    if not wait or action == 'status' or result['status'] != 'accepted':
        return result
    import time

    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        time.sleep(0.05)
        try:
            status = send('status', {}, str(uuid.uuid4()))
        except OSError:
            if action in ['shutdown', 'recover-and-exit']:
                return {'status': 'complete', 'request_id': ident}
            raise
        op = next(
            (o for o in status.get('result', {}).get('operations', []) if o['request_id'] == ident),
            None,
        )
        if op and op['state'] in ['complete', 'failed']:
            if status['result'].get('operations_summarized'):
                op = whole_operation(lambda: send('operation', {'request_id': ident}, str(uuid.uuid4())), op)
            return {'status': op['state'], 'request_id': ident, 'operation': op}
    return {
        'status': 'failed',
        'request_id': ident,
        'error': 'Operation wait timeout; inspect status before retrying',
    }
