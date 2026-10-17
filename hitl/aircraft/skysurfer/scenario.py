import json,math
from pathlib import Path
from host.abi import header,Initial
ALLOWED={'schema_version','aircraft_id','name','height_agl_m','velocity_mode','tas_m_s','body_velocity_m_s','alpha_deg','beta_deg','euler_deg','latitude_deg','longitude_deg','site_msl_m','geoid_separation_m','wind_ned_m_s','angular_rates_rad_s','seed_policy'}
def load_scene(value):
 scene=json.loads(Path(value).read_text()) if isinstance(value,(str,Path)) else dict(value)
 unknown=set(scene)-ALLOWED
 if unknown:raise ValueError('Unsupported scene fields: '+','.join(sorted(unknown)))
 if scene.get('schema_version')!=1 or scene.get('aircraft_id')!='skysurfer':raise ValueError('Scene schema/aircraft mismatch')
 for name in ['site_msl_m','geoid_separation_m','seed_policy']:
  if scene.get(name,0)!=0:raise ValueError(name+' is unsupported by this source recipe; supported value is 0')
 for name in ['wind_ned_m_s','angular_rates_rad_s']:
  if scene.get(name,[0,0,0])!=[0,0,0]:raise ValueError(name+' is unsupported by this source recipe')
 def number(name,default,lo,hi):
  v=scene.get(name,default)
  if isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or not lo<=v<=hi:raise ValueError(name+' outside supported range')
  return v
 mode=scene.get('velocity_mode','tas')
 if mode=='tas':
  if 'body_velocity_m_s' in scene:raise ValueError('TAS and body velocity modes are mutually exclusive')
  speed=number('tas_m_s',0,0,200);a=math.radians(number('alpha_deg',0,-45,45));b=math.radians(number('beta_deg',0,-45,45))
  velocity=[speed*math.cos(a)*math.cos(b),speed*math.sin(b),speed*math.sin(a)*math.cos(b)]
 elif mode=='body':
  if any(n in scene for n in ['tas_m_s','alpha_deg','beta_deg']):raise ValueError('Body velocity and TAS fields are mutually exclusive')
  velocity=scene.get('body_velocity_m_s')
 else:raise ValueError('Unknown velocity mode')
 euler=scene.get('euler_deg',[0,.8633,0])
 for name,values,limits in [('body_velocity',velocity,[200]*3),('Euler',euler,[180,80,360])]:
  if not isinstance(values,list) or len(values)!=3 or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or abs(v)>lim for v,lim in zip(values,limits)):raise ValueError(name+' invalid')
 initial=header(Initial);initial.height_m=number('height_agl_m',0,0,10000);initial.body_velocity_m_s[:]=velocity;initial.euler_deg[:]=euler
 initial.latitude_deg=number('latitude_deg',22.910275834988674,-90,90);initial.longitude_deg=number('longitude_deg',120.31096929726908,-180,180)
 return scene,initial
