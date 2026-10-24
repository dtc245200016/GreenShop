"""Observe PID1 and worker process UID/GID/capabilities without exporting argv/env."""

if __name__ == "__main__":
 raise SystemExit("Retired QA/recovery harness. Use GreenShop-Official: docker compose up -d --build")
import importlib.util,json
from pathlib import Path
R=Path(__file__).resolve().parents[2]
s=importlib.util.spec_from_file_location('a',R/'tests/logging/acceptance.py');a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
rows=[]
for env in ['qa','main']:
 ids=a.rt.run(['docker','ps','-q','--filter','label=com.docker.compose.project='+a.rt.project(env)]).decode().splitlines()
 for cid in ids:
  d=a.rt.info(cid);service=d['Config']['Labels']['com.docker.compose.service'];top=a.rt.run(['docker','top',cid]).decode().splitlines()[1:];processes=[]
  for line in top:
   cols=line.split()
   if len(cols)<3 or not cols[1].isdigit():continue
   pid=int(cols[1])
   try:data=dict(x.split(':',1) for x in Path('/proc/'+str(pid)+'/status').read_text().splitlines() if ':' in x)
   except FileNotFoundError:continue
   processes.append({'pid':pid,'is_container_pid1':pid==d['State']['Pid'],'name':data['Name'].strip(),'uid':[int(v) for v in data['Uid'].split()],'gid':[int(v) for v in data['Gid'].split()],'effective_capabilities':data['CapEff'].strip(),'no_new_privileges':data['NoNewPrivs'].strip()})
  assert any(p['is_container_pid1'] for p in processes)
  rows.append({'environment':env,'service':service,'container_user':d['Config']['User'] or 'image entrypoint default','processes':processes,'privileged':d['HostConfig']['Privileged'],'caps_add':d['HostConfig']['CapAdd'],'caps_drop':d['HostConfig']['CapDrop'],'security_options':d['HostConfig']['SecurityOpt'],'host_mount_destinations':[m['Destination'] for m in d['Mounts'] if m['Type']=='bind' and m['Destination'] in ['/rootfs','/sys','/var/run','/var/lib/docker']],'classification':'Root master/entrypoint/host collector risk must be assessed separately; no forced USER override.' if service in ['nginx','phpmyadmin','db','cadvisor'] else 'Observed actual UID/GID; no privilege change made.'})
a.record('process-privileges-final',{'status':'PASS','observed_utc':a.now(),'method':'docker inspect + docker top PID list + host /proc/PID/status; no argv/environment exported','services':rows,'runtime_changes':False,'scope':'Audit PASS means observations collected, not all services non-root.'})
print('PASS PID1 and worker UID/GID audit:',len(rows),'services; no runtime privilege changes.',flush=True)
