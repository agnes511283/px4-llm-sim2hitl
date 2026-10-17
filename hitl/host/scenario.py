import importlib.util,json,re
from pathlib import Path
def load_scene(value):
 scene=json.loads(Path(value).read_text()) if isinstance(value,(str,Path)) else dict(value)
 aircraft=scene.get('aircraft_id','')
 if not isinstance(aircraft,str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,31}',aircraft):raise ValueError('Invalid aircraft id')
 recipe=Path(__file__).resolve().parents[1]/'aircraft'/aircraft/'scenario.py'
 if not recipe.is_file():raise ValueError('Aircraft scene recipe not installed')
 spec=importlib.util.spec_from_file_location('hil_scene_'+aircraft,recipe);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 return module.load_scene(scene)
