"""PX4 BARO mask and native/Python wire parity; no FC or sockets."""
import ctypes as C
import math
import os
from pathlib import Path
import sys
import unittest

from pymavlink.dialects.v20 import common as mav

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from platform_support import needs_model
from host.abi import Model,Worker,Output,header
from host.packets import Encoder,baro_metadata
from host.release import read_release


@needs_model
class BaroCompatibilityTests(unittest.TestCase):
 def setUp(self):
  if os.environ.get('FW_HIL_LIBRARY_CACHE'):
   folder=Path(os.environ['FW_HIL_LIBRARY_CACHE'])/'native';sys.path.insert(0,str(ROOT.parent/'plant/core'))
   from toolchain import lib;names={'library':lib('skysurfer'),'worker':lib('hil_worker')}
  else:folder,names=read_release(ROOT)
  self.model=Model(folder/names['library']);self.worker=Worker(folder/names['worker'],self.model)
 def tearDown(self):self.worker.stop();self.worker.lib.hil_io_stop();self.model.lib.hil_model_terminate()
 def encode_native(self,o):
  buffer=C.create_string_buffer(1024)
  length=self.worker.lib.hil_io_encode(C.byref(o),1000000,buffer,1024,0)
  if length<0:return length
  return mav.MAVLink(None).parse_buffer(buffer.raw[:length])[0]
 def test_native_and_python_match_complete_px4_baro_group(self):
  for altitude in [0.,100.,1000.]:
   with self.subTest(altitude=altitude):
    o=header(Output);o.absolute_pressure_pa=101325*(1-.0065*altitude/288.15)**(1/.1902632365084836);o.fields_updated=0x7ff
    native=self.encode_native(o)
    frame=Encoder({'fix_type':3,'satellites':10,'eph_cm':30,'epv_cm':50}).encode(o,1000000)[0][1]
    python=mav.MAVLink(None).parse_buffer(frame)[0]
    self.assertEqual(native.to_dict(),python.to_dict())
    self.assertEqual(native.fields_updated&0x1a00,0x1a00)
    self.assertAlmostEqual(native.pressure_alt,altitude,places=3)
    self.assertAlmostEqual(native.temperature,15-.0065*altitude,places=4)
    self.assertEqual(o.fields_updated,0x7ff)  # ABI retains the original source availability.
 def test_invalid_pressure_rejected_in_both_encoders(self):
  for pressure in [0.,-1.,math.nan]:
   o=header(Output);o.absolute_pressure_pa=pressure;o.fields_updated=0x7ff
   self.assertEqual(self.encode_native(o),-4)
   with self.assertRaises(ValueError):baro_metadata(pressure,o.fields_updated)
 def test_no_baro_source_does_not_claim_derived_baro(self):
  o=header(Output);o.fields_updated=0x1ff
  native=self.encode_native(o)
  self.assertEqual(native.fields_updated&0x1a00,0)


if __name__=='__main__':unittest.main(verbosity=2)
