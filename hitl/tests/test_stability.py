"""Deterministic offline regressions for native faults and lossless fake PTY."""
import ctypes as C,errno,os,sys,time,unittest
from pathlib import Path
from unittest.mock import Mock
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from platform_support import needs_model
from host.abi import Model,Worker,diagnostics,io_events,io_stats,Input,Output,header
from host.release import read_release
from host.transport import PeerPump,FakePTY

@needs_model
class NativeFailureTests(unittest.TestCase):
 def setUp(self):
  release,manifest=read_release(ROOT);self.model=Model(release/manifest['library']);self.worker=Worker(release/manifest['worker'],self.model);self.model.reset()
 def tearDown(self):self.worker.stop();self.worker.lib.hil_io_stop();self.model.lib.hil_model_terminate()
 def test_full_pipe_fault_reaches_model_while_python_cannot_poll(self):
  rd,wr=os.pipe();os.set_blocking(wr,False)
  try:
   while True:
    try:os.write(wr,b'X'*4096)
    except BlockingIOError:break
   self.assertEqual(self.worker.lib.hil_io_start(wr),0);self.worker.lib.hil_io_config(1000000,3|(10<<8));self.worker.start()
   # PyDLL deliberately holds the GIL; no Python Core thread can stop the model.
   C.PyDLL(None).usleep(350000)
   s=self.worker.snapshot();event=diagnostics(self.worker)['io_last_event']
   self.assertEqual(s.fault,9);self.assertFalse(s.running);self.assertLess(s.produced,40)
   self.assertEqual(event['reason'],1);self.assertEqual(event['offset'],0);self.assertIn(event['write_errno'],[errno.EAGAIN,errno.EWOULDBLOCK]);self.assertGreaterEqual(event['end_ns']-event['begin_ns'],100000000)
   self.assertEqual(io_stats(self.worker)['errors'],1);self.assertEqual(len(io_events(self.worker)),1)
  finally:self.worker.stop();self.worker.lib.hil_io_stop();os.close(rd);os.close(wr)
 def test_fatal_write_errno_is_recorded(self):
  rd,wr=os.pipe();os.close(wr)
  try:
   self.assertEqual(self.worker.lib.hil_io_start(wr),0);self.worker.lib.hil_io_command(b'bad',3)
   end=time.monotonic()+1
   while not io_stats(self.worker)['errors'] and time.monotonic()<end:time.sleep(.001)
   event=diagnostics(self.worker)['io_last_event'];self.assertEqual(event['write_errno'],errno.EBADF);self.assertEqual(event['reason'],2);self.assertEqual(event['len'],3);self.assertEqual(event['offset'],0)
  finally:self.worker.lib.hil_io_stop();os.close(rd)

 def test_stopped_io_does_not_poison_offline_worker(self):
  rd,wr=os.pipe();os.close(wr)
  try:
   self.worker.lib.hil_io_start(wr);self.worker.lib.hil_io_command(b'bad',3);time.sleep(.02);self.assertEqual(io_stats(self.worker)['errors'],1);self.worker.lib.hil_io_stop()
   self.worker.start();time.sleep(.03);s=self.worker.snapshot();self.assertEqual(s.fault,0);self.assertTrue(s.running)
  finally:self.worker.stop();self.worker.lib.hil_io_stop();os.close(rd)
 def test_late_fault_preserves_previous_step_timeline(self):
  @C.CFUNCTYPE(C.c_int32,C.POINTER(Input),C.POINTER(Output))
  def delayed_step(inp,out):C.PyDLL(None).usleep(35000);return 0
  self.assertEqual(self.worker.lib.hil_worker_start(C.cast(delayed_step,C.c_void_p),C.byref(header(Input)),20000000),0)
  time.sleep(.1);s=self.worker.snapshot();d=diagnostics(self.worker)['worker'];self.assertEqual(s.fault,5);self.assertGreaterEqual(d['wake_ns']-d['deadline_ns'],20000000);self.assertGreaterEqual(d['previous_end_ns']-d['previous_begin_ns'],35000000);self.assertGreater(d['publish_end_ns'],d['publish_begin_ns'])

class FakePeerTests(unittest.TestCase):
 def test_short_write_and_eagain_preserve_pending_bytes(self):
  p=PeerPump(-1,ROOT.parent);p.pending.extend(b'abcdef');p.write_master=Mock(side_effect=[2,BlockingIOError(errno.EAGAIN,'full'),4])
  p.flush();self.assertEqual(p.pending,b'cdef');p.flush();self.assertEqual(p.pending,b'cdef');p.flush();self.assertEqual(p.pending,b'');self.assertEqual(p.stats['written_bytes'],6);self.assertEqual(p.stats['short_writes'],1);self.assertEqual(p.stats['would_block'],1)
 def test_reopen_starts_new_peer_and_closes_pty_descriptors(self):
  p=FakePTY(ROOT.parent)
  for _ in range(2):
   p.open();master=p.master;slave=p.slave;time.sleep(.02);self.assertTrue(p.diagnostics()['alive']);p.close();self.assertFalse(p.diagnostics()['alive'])
   for fd in [master,slave]:
    with self.assertRaises(OSError):os.fstat(fd)

if __name__=='__main__':unittest.main(verbosity=2)
