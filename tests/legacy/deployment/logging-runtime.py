"""M3 rollout for the audited GreenShop lab. No Git operations or volume deletion.

Historical prepare/deploy actions are QA-only. Main uses plan/status/update.
Main refresh regenerates exact targets/mounts and grants group traversal only on selected Docker log directories.
"""

if __name__ == "__main__":
 raise SystemExit("Retired QA/recovery harness. Use GreenShop-Official: docker compose up -d --build")
import argparse,copy,hashlib,importlib.util,json,os,subprocess,time
from pathlib import Path
import requests,yaml
R=Path(__file__).resolve().parents[1]
P=Path.home()/'.local/share/greenshop-monitoring'
E=R/'docs/evidence/commit3'
def run(args,**kw):
 p=subprocess.run(args,capture_output=True,**kw)
 if p.returncode:
  raise RuntimeError('Command failed: '+str(args[:3])+'; '+p.stderr.decode(errors='replace')[-800:])
 return p.stdout
def info(n):return json.loads(run(['docker','inspect',n]))[0]
def save(f,d):
 f.parent.mkdir(parents=True,exist_ok=True)
 if f.exists():f.chmod(0o600)
 f.write_text(json.dumps(d,indent=2)+'\n');f.chmod(0o600)
def project(env):return 'greenshop-m2-qa' if env=='qa' else 'dtc245200016_btl_tkqt_htpm'
def dc(env,*args):return run(['docker','compose','-p',project(env),'-f',str(P/env/'compose.json'),*args])
def container(env,s):
 ids=run(['docker','ps','-aq','--filter','label=com.docker.compose.project='+project(env),'--filter','label=com.docker.compose.service='+s]).decode().splitlines()
 assert len(ids)==1,(env,s,ids)
 return ids[0]
def record(name,d):
 E.mkdir(parents=True,exist_ok=True);(E/(name+'.json')).write_text(json.dumps(d,indent=2)+'\n')
def prepare(env):
 if env=='main':raise RuntimeError('Historical rollout disabled on Main; use plan/status/update after separate approval')
 b=P/'m3'/env;b.mkdir(parents=True,exist_ok=True,mode=0o700)
 assert not (b/'before-plan.json').exists(),'Refuse to overwrite M3 baseline'
 c=json.loads((P/env/'compose.json').read_text());save(b/'before-plan.json',c)
 # Fresh snapshot includes hashes only; raw customer rows never enter evidence.
 spec=importlib.util.spec_from_file_location('m2',R/'tests/monitoring/acceptance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 if env=='main':save(b/'data-before.json',m.snapshot())
 for svc,folders in [('web_app',[('/app/keys','keys'),('/app/wwwroot/uploads/products','uploads')]),('nginx',[('/etc/nginx/ssl','tls')])]:
  cid=container(env,svc)
  for folder,name in folders:
   data=run(['docker','exec',cid,'tar','cf','-','-C',folder,'.']);f=b/(name+'.tar');f.write_bytes(data);f.chmod(0o600)
 if env=='main':
  data=run(['docker','exec',container(env,'db'),'sh','-c','MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysqldump -uroot --single-transaction --routines --triggers --events --no-tablespaces --set-gtid-purged=OFF greenshop'])
  f=b/'mysql.sql';f.write_bytes(data);f.chmod(0o600)
 # Preserve alert/dashboard/contact point state as authenticated API exports.
 port=21300 if env=='qa' else 3000;pw=json.loads((P/env/'passwords.json').read_text())['grafana']
 for name,url in [('rules','/api/v1/provisioning/alert-rules'),('contact-points','/api/v1/provisioning/contact-points'),('datasources','/api/datasources'),('dashboards','/api/search?type=dash-db')]:
  r=requests.get(f'http://127.0.0.1:{port}'+url,auth=('admin',pw),timeout=20);r.raise_for_status();save(b/(name+'-before.json'),r.json())
 # Existing database/image/volume identities and all environment credentials stay intact.
 save(b/'core-before.json',{s:info(container(env,s)) for s in ['web_app','nginx','db','phpmyadmin','grafana','prometheus']})
 envs=dict(os.environ,MYSQL_ROOT_PASSWORD='render-validation-only',MYSQL_APP_PASSWORD='render-validation-only',MONITORING_SECRETS_DIR=str(P/env/'secrets'),LOGGING_RUNTIME_DIR=str(b))
 source=json.loads(run(['docker','compose','--project-directory',str(R),'--profile','monitoring','--profile','qa','-f',str(R/'docker-compose.yml'),'config','--format','json'],env=envs))
 c['networks']['logging_net']={'name':project(env)+'_logging_net','driver':'bridge','internal':True}
 c['services']['grafana']['networks']['logging_net']=None
 c['services']['grafana']['mem_limit']=536870912
 c['services']['grafana']['memswap_limit']=805306368
 for s in ['loki','promtail']:
  c['services'][s]=source['services'][s];c['services'][s].pop('profiles',None);c['services'][s].pop('build',None)
  c['services'][s]['networks']={'logging_net':None}
 for v in ['loki_data','promtail_positions']:c['volumes'][v]={'name':project(env)+'_'+v}
 w=c['services']['web_app'];w.pop('build',None);w['image']='greenshop-m3-web:qa';
 if env=='main':
  run(['docker','tag','greenshop-m3-web:qa','greenshop-m3-web:release']);w['image']='greenshop-m3-web:release'
 w['user']='1654:1654'
 for k in ['cap_drop','security_opt','mem_limit','cpus','logging']:
  # Rendered Compose uses mem_limit and cpus supported by current CLI.
  if k in source['services']['web_app']:w[k]=source['services']['web_app'][k]
 for s in ['nginx','phpmyadmin','db']:c['services'][s]['logging']=source['services'][s]['logging']
 # Keep original Main TLS bind. Use a dedicated private QA config (Host preserves port).
 if env=='qa':
  f=P/env/'nginx-m3.conf';f.write_text((R/'nginx/default.conf').read_text().replace('proxy_set_header Host $host;','proxy_set_header Host $http_host;'))
  for v in c['services']['nginx']['volumes']:
   if v['target']=='/etc/nginx/conf.d/default.conf':v['source']=str(f)
 save(b/'proposed-plan.json',c)
 record(env+'-plan-diff',{'status':'PASS','project':project(env),'changed_services':['web_app','nginx','grafana (logging network only)'],'added_services':['loki','promtail'],'unchanged_volume_names':{k:v['name'] for k,v in c['volumes'].items() if k not in ['loki_data','promtail_positions']},'database_recreate':False,'phpmyadmin_recreate':False,'credentials_changed':False})
 print('PASS prepared private baseline, backups and concrete plan:',env,flush=True)
def ownership(env,restore=False):
 if env=='main':raise RuntimeError('Historical rollout disabled on Main; use plan/status/update after separate approval')
 b=P/'m3'/env;c=json.loads((b/'core-before.json').read_text())['web_app']
 mounts=[m for m in c['Mounts'] if m['Destination'] in ['/app/keys','/app/wwwroot/uploads/products']]
 args=['docker','run','--rm','--network','none','--cap-drop','ALL','--cap-add','CHOWN','--cap-add','DAC_OVERRIDE','--security-opt','no-new-privileges']
 for n,m in enumerate(mounts):args+=['-v',m['Name']+':/v'+str(n)]
 code='''import os,json,stat,sys
result=[]
for root in ['/v0','/v1']:
 for path,dirs,files in os.walk(root):
  for p in [path]+[os.path.join(path,f) for f in files]:
   s=os.lstat(p);assert not stat.S_ISLNK(s.st_mode);assert s.st_uid in (0,1654),(p,s.st_uid)
   result.append([p,s.st_uid,s.st_gid,stat.S_IMODE(s.st_mode)])
if sys.argv[1]=='apply':
 print(json.dumps(result))
 for p,u,g,m in result:os.chown(p,1654,1654)
else:
 for p,u,g,m in json.load(sys.stdin):os.chown(p,u,g);os.chmod(p,m)
'''
 if restore:
  run(args+['-i','python:3.12.10-alpine3.21','python','-c',code,'restore'],input=(b/'ownership.json').read_bytes())
 else:
  data=run(args+['python:3.12.10-alpine3.21','python','-c',code,'apply'])
  if not (b/'ownership.json').exists():save(b/'ownership.json',json.loads(data))
def core(env):
 if env=='main':raise RuntimeError('Historical rollout disabled on Main; use plan/status/update after separate approval')
 b=P/'m3'/env
 if env=='main':
  d=json.loads((E/'qa-acceptance.json').read_text());assert d['status']=='PASS','QA gate failed'
 c=json.loads((b/'proposed-plan.json').read_text())
 # Back up live authoritative plan before replacing it, after QA gate.
 ownership(env)
 save(P/env/'compose.json',c)
 try:
  dc(env,'up','-d','--no-deps','--wait','--wait-timeout','180','web_app','nginx')
  run(['docker','exec',container(env,'nginx'),'nginx','-t'])
  port='21543' if env=='qa' else '443'
  requests.packages.urllib3.disable_warnings()
  for p in ['/health/ready','/','/SanPham/CuaHang','/Account/Login']:
   assert requests.get('https://localhost:'+port+p,verify=False,timeout=20).status_code==200,p
 except Exception:
  rollback_core(env);raise
 print('PASS core non-root web + safe Nginx logs:',env,flush=True)
def rollback_core(env):
 if env=='main':raise RuntimeError('Historical rollout disabled on Main; use plan/status/update after separate approval')
 b=P/'m3'/env;current=json.loads((P/env/'compose.json').read_text());old=json.loads((b/'before-plan.json').read_text())
 dc(env,'stop','web_app');ownership(env,restore=True)
 for s in ['web_app','nginx']:current['services'][s]=old['services'][s]
 save(P/env/'compose.json',current);dc(env,'up','-d','--no-deps','--wait','web_app','nginx')
 print('Core image/config/ownership restored; verify data/auth before declaring rollback PASS.',flush=True)
def refresh_qa(env):
 if env!='qa':raise RuntimeError('QA-only legacy refresh; use refresh_main for Main')
 b=P/'m3'/env;c=json.loads((P/env/'compose.json').read_text());targets=[];mounts=[]
 for s,label in [('web_app','greenshop-web'),('nginx','nginx'),('db','mysql')]:
  d=info(container(env,s));assert d['HostConfig']['LogConfig']['Type']=='json-file'
  path=Path(d['LogPath']);assert str(path).startswith('/var/lib/docker/containers/')
  target='/logs/'+s
  # Directory watch needs read+execute; only selected Docker container directories.
  run(['docker','run','--rm','--network','none','--cap-drop','ALL','-v',str(path.parent)+':/selected','busybox:1.37.0-musl','chmod','g+r','/selected'])
  mounts.append({'type':'bind','source':str(path.parent),'target':target,'read_only':True,'bind':{'create_host_path':False}})
  targets.append({'targets':['localhost'],'labels':{'__path__':target+'/'+path.name,'environment':env,'project':project(env),'service':label,'source':'docker'}})
 save(b/'targets/containers.json',targets)
 (b/'targets').chmod(0o755);(b/'targets/containers.json').chmod(0o444)
 p=c['services']['promtail'];p['volumes']=[v for v in p['volumes'] if not v['target'].startswith('/logs/')]+mounts
 save(P/env/'compose.json',c)
 print('PASS refreshed exact container paths:',env,flush=True)
def logging(env):
 if env=='main':raise RuntimeError('Historical rollout disabled on Main; use plan/status/update after separate approval')
 b=P/'m3'/env
 refresh(env)
 # Initialize only new logging volumes, never existing business volumes.
 for v,uid in [('loki_data','10001:10001'),('promtail_positions','10001:0')]:
  name=project(env)+'_'+v;run(['docker','volume','create',name])
  run(['docker','run','--rm','--network','none','-v',name+':/data','busybox:1.37.0-musl','chown',uid,'/data'])
 dc(env,'up','-d','--no-deps','--wait','--wait-timeout','180','loki')
 dc(env,'up','-d','--no-deps','--wait','--wait-timeout','90','promtail')
 g=container(env,'grafana')
 run(['docker','update','--memory','512m','--memory-swap','768m',g])
 network=project(env)+'_logging_net'
 if network not in info(g)['NetworkSettings']['Networks']:run(['docker','network','connect',network,g])
 pw=json.loads((P/env/'passwords.json').read_text())['grafana'];port=21300 if env=='qa' else 3000
 r=requests.post(f'http://127.0.0.1:{port}/api/admin/provisioning/datasources/reload',auth=('admin',pw),timeout=30);r.raise_for_status()
 print('PASS logging ready and Grafana provisioning reloaded:',env,flush=True)

# One Main entrypoint, always using the official source and the existing project.
MAIN_PROJECT='dtc245200016_btl_tkqt_htpm'
MAIN_PLAN=P/'main/compose.json'
MAIN_CANDIDATE=P/'main/compose.next.json'
M3_RELEASE='greenshop-m3-web:release'
MANAGED=('web_app','nginx','promtail','loki')
def need(value,message):
 if not value:raise RuntimeError(message)
def main_run(args,**kw):
 need(R==Path('/home/trung/GreenShop-Official'),'Main must use GreenShop-Official')
 e=dict(kw.pop('env',os.environ))
 for key in ('DOCKER_CONTEXT','DOCKER_HOST','COMPOSE_FILE','COMPOSE_PROJECT_NAME','COMPOSE_PROFILES','COMPOSE_ENV_FILES'):
  e.pop(key,None)
 return run(['docker','--host','unix:///var/run/docker.sock',*args],env=e,cwd=R,**kw)
def main_info(service):
 ids=main_run(['ps','-aq','--no-trunc','--filter','label=com.docker.compose.project='+MAIN_PROJECT,'--filter','label=com.docker.compose.service='+service]).decode().split()
 need(len(ids)==1,'Expected exactly one Main container: '+service)
 d=json.loads(main_run(['inspect',ids[0]]))[0]
 need(d['Config']['Labels'].get('com.docker.compose.project')==MAIN_PROJECT,'Unexpected project')
 need(d['Config']['Labels'].get('com.docker.compose.service')==service,'Unexpected service')
 return d
def main_sources():
 targets=[];mounts=[]
 for service,label in [('web_app','greenshop-web'),('nginx','nginx'),('db','mysql')]:
  d=main_info(service);cid=d['Id'];path=Path(d['LogPath'])
  need(d['State']['Running'],'Source is not running: '+service)
  need(d['HostConfig']['LogConfig']['Type']=='json-file','Expected json-file: '+service)
  need(path==Path('/var/lib/docker/containers')/cid/(cid+'-json.log'),'Unexpected Docker log path')
  target='/logs/'+service
  mounts.append({'type':'bind','source':str(path.parent),'target':target,'read_only':True,'bind':{'create_host_path':False}})
  targets.append({'targets':['localhost'],'labels':{'__path__':target+'/'+path.name,'environment':'main','project':MAIN_PROJECT,'service':label,'source':'docker'}})
 return targets,mounts
def main_validate(c):
 need(c.get('name')==MAIN_PROJECT,'Unexpected Compose project')
 proof=c.get('x-greenshop-main',{})
 need(proof.get('repository')==str(R),'Main plan must first be generated/reviewed from the official repository')
 for key,saved in proof['networks'].items():
  n=json.loads(main_run(['network','inspect',c['networks'][key]['name']]))[0]
  need(n['Id']==saved['id'] and n['Driver']==saved['driver'] and n['Internal']==saved['internal'],'Network identity changed: '+key)
  for cid in n.get('Containers',{}):
   member=json.loads(main_run(['inspect',cid]))[0]
   need(member['Config']['Labels'].get('com.docker.compose.project')==MAIN_PROJECT,'Non-Main container in Main network')
 for key,saved in proof['volumes'].items():
  v=json.loads(main_run(['volume','inspect',c['volumes'][key]['name']]))[0]
  need(all(v.get(k)==saved[k] for k in ('Name','Driver','Mountpoint','CreatedAt')),'Volume identity changed: '+key)
 for service,cid in proof['retained_containers'].items():
  need(main_info(service)['Id']==cid,'Retained container changed: '+service)
 for service,image in proof['managed_images'].items():
  need(json.loads(main_run(['image','inspect',c['services'][service]['image']]))[0]['Id']==image,'Release image changed: '+service)
 for service,target,key in [('db','/var/lib/mysql','mysql_data'),('web_app','/app/keys','data_protection_keys'),('web_app','/app/wwwroot/uploads/products','product_images')]:
  matches=[v for v in main_info(service)['Mounts'] if v['Destination']==target]
  need(len(matches)==1 and matches[0].get('Name')==c['volumes'][key]['name'],'Business volume mismatch: '+target)
 return c
def main_plan():
 c=json.loads(MAIN_PLAN.read_text())
 need(c.get('name')==MAIN_PROJECT,'Unexpected existing project')
 e=dict(os.environ,MYSQL_ROOT_PASSWORD='render-only',MYSQL_APP_PASSWORD='render-only',MONITORING_SECRETS_DIR=str(P/'main/secrets'),LOGGING_RUNTIME_DIR=str(P/'m3/main'))
 src=json.loads(main_run(['compose','--project-directory',str(R),'--profile','monitoring','--profile','qa','-f',str(R/'docker-compose.yml'),'config','--format','json'],env=e))
 need(main_info('web_app')['State']['Running'],'Existing Web must be running during planning')
 release=json.loads(main_run(['image','inspect',M3_RELEASE]))[0]
 M3_IMAGE=release['Id']
 qa=main_run(['ps','-aq','--no-trunc','--filter','label=com.docker.compose.project=greenshop-m2-qa','--filter','label=com.docker.compose.service=web_app']).decode().split()
 need(len(qa)==1 and json.loads(main_run(['inspect',qa[0]]))[0]['Image']==M3_IMAGE,'QA image differs from M3 release')
 w=c['services']['web_app']
 for key in ('healthcheck','networks','secrets','cap_drop','security_opt','mem_limit','cpus','logging'):
  w[key]=copy.deepcopy(src['services']['web_app'][key])
 w.pop('build',None);w['image']=M3_IMAGE;w['user']='1654:1654'
 w['environment']=dict(v.split('=',1) for v in main_info('web_app')['Config']['Env'] if '=' in v)
 w['environment']['Metrics__TokenFile']='/run/secrets/metrics_token'
 for service in ('nginx','db','phpmyadmin'):
  c['services'][service]['networks']=copy.deepcopy(src['services'][service]['networks'])
 # Preserve DB/PMA's actual log settings: changing these would require recreation.
 for service in ('db','phpmyadmin'):
  log=main_info(service)['HostConfig']['LogConfig'];c['services'][service]['logging']={'driver':log['Type'],'options':log['Config'] or {}}
 n=c['services']['nginx']
 n['healthcheck']=copy.deepcopy(src['services']['nginx']['healthcheck'])
 n['logging']=copy.deepcopy(src['services']['nginx']['logging'])
 for v in n['volumes']:
  if v['target']=='/etc/nginx/conf.d/default.conf':v['source']=str(R/'nginx/default.conf')
  if v['target']=='/etc/nginx/ssl':v['source']=str(P/'main/tls')
 proof={'repository':str(R),'networks':{},'volumes':{},'retained_containers':{},'managed_images':{},'notes':'DB/PMA adopted without recreation; legacy Compose labels and current logging policy retained.'}
 for key,n in c['networks'].items():
  d=json.loads(main_run(['network','inspect',n['name']]))[0]
  proof['networks'][key]={'id':d['Id'],'driver':d['Driver'],'internal':d['Internal']}
  c['networks'][key]={'name':d['Name'],'external':True}
 for key,v in c['volumes'].items():
  d=json.loads(main_run(['volume','inspect',v['name']]))[0]
  proof['volumes'][key]={k:d.get(k) for k in ('Name','Driver','Mountpoint','CreatedAt')}
  c['volumes'][key]={'name':d['Name'],'external':True}
 for service in c['services']:
  if service not in MANAGED:
   actual=main_info(service);proof['retained_containers'][service]=actual['Id'];c['services'][service]['image']=actual['Image']
 for service in MANAGED:
  proof['managed_images'][service]=json.loads(main_run(['image','inspect',c['services'][service]['image']]))[0]['Id']
 for service in MANAGED:
  for v in c['services'][service].get('volumes',[]):
   if v.get('type')=='bind':v.setdefault('bind',{})['create_host_path']=False
 c['x-greenshop-main']=proof
 _,mounts=main_sources();p=c['services']['promtail']
 p['volumes']=[v for v in p['volumes'] if not v['target'].startswith('/logs/')]+mounts
 main_validate(c)
 # No change to the authoritative plan, targets, runtime or repository evidence.
 MAIN_CANDIDATE.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
 fd=os.open(MAIN_CANDIDATE,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'w') as f:json.dump(c,f,indent=2);f.write('\n')
 print('Candidate only; NOT installed:',MAIN_CANDIDATE)
 print('Web release pinned and equal to current QA; existing volumes/networks external; DB/PMA adopted. Apply reviewed candidate to main/compose.json.')
def main_status():
 c=json.loads(MAIN_PLAN.read_text());need(c.get('name')==MAIN_PROJECT,'Unexpected project')
 for service in c['services']:
  d=main_info(service)
  print(service,d['Id'][:12],d['State']['Status'],'oom='+str(d['State']['OOMKilled']),'restarts='+str(d['RestartCount']))
 print('Reviewed Main entrypoint plan:',bool(c.get('x-greenshop-main')))
def refresh_main():
 c=main_validate(json.loads(MAIN_PLAN.read_text()));targets,mounts=main_sources()
 target=P/'m3/main/targets/containers.json'
 need(target.parent.is_dir(),'Targets directory is missing; stop for review')
 # Grant the non-root collector access to only the three exact Docker log directories.
 # Root-owned directories remain inaccessible to other users; files are not chmodded.
 helper=c['x-greenshop-main']['managed_images']['nginx']
 for mount in mounts:
  main_run(['run','--rm','--network','none','--user','0:0','--cap-drop','ALL',
   '--security-opt','no-new-privileges','--entrypoint','/bin/sh',
   '--mount','type=bind,source='+mount['source']+',target=/selected',helper,'-ec',
   'test "$(stat -c %u:%g /selected)" = "0:0"; chmod g+rx /selected'])
  main_run(['run','--rm','--network','none','--user','10001:0','--cap-drop','ALL',
   '--security-opt','no-new-privileges','--entrypoint','/bin/sh',
   '--mount','type=bind,source='+mount['source']+',target=/selected,readonly',helper,'-ec',
   'test -r /selected; test -x /selected; test -r /selected/'+Path(mount['source']).name+'-json.log'])
 temp=target.with_name('.containers.json.pending')
 fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o444)
 with os.fdopen(fd,'w') as f:
  json.dump(targets,f,indent=2);f.write('\n');f.flush();os.fchmod(f.fileno(),0o444)
 p=c['services']['promtail'];p['volumes']=[v for v in p['volumes'] if not v['target'].startswith('/logs/')]+mounts
 main_validate(c)
 os.replace(temp,target)
 save(MAIN_PLAN,c)
 print('Targets AND mounts refreshed; positions unchanged; container NOT restarted.')
def refresh(env):
 return refresh_main() if env=='main' else refresh_qa(env)
def main_start():
 c=main_validate(json.loads(MAIN_PLAN.read_text()))
 for service,spec in c['services'].items():
  d=main_info(service)
  expected={c['networks'][key]['name'] for key in spec['networks']}
  need(set(d['NetworkSettings']['Networks'])==expected,'Runtime network drift: '+service)
  if service in MANAGED:
   need(d['Image']==c['x-greenshop-main']['managed_images'][service],'Runtime image drift: '+service)
 logs={v['target']:v['source'] for v in c['services']['promtail']['volumes'] if v['target'].startswith('/logs/')}
 for service in ('web_app','nginx','db'):
  need(logs.get('/logs/'+service)==str(Path(main_info(service)['LogPath']).parent),'Promtail targets need refresh before start')
 for service in ('db','loki','web_app','nginx','mysql-exporter','nginx-exporter','cadvisor','qa-alert-receiver','prometheus','grafana','promtail','phpmyadmin'):
  # start only: missing containers fail validation above; nothing is recreated.
  main_run(['compose','--project-directory',str(R),'-p',MAIN_PROJECT,'-f',str(MAIN_PLAN),'start','--wait','--wait-timeout','180',service])
 print('Started existing Main containers only; verify health, metrics and logs before demo.')
def main_update(service,force=False):
 need(service in MANAGED,'Only managed Web/Nginx/Promtail/Loki services may be recreated')
 c=main_validate(json.loads(MAIN_PLAN.read_text()))
 if service=='loki':
  qa=main_run(['ps','-q','--filter','label=com.docker.compose.project=greenshop-m2-qa','--filter','label=com.docker.compose.service=loki']).decode().split()
  need(len(qa)==1 and json.loads(main_run(['inspect',qa[0]]))[0]['Image']==c['x-greenshop-main']['managed_images']['loki'],'Loki image must match verified QA')
 if service=='nginx':
  for path in ('cert.pem','key.pem'):
   need((P/'main/tls'/path).is_file(),'Preserved TLS copy missing: '+path)
 if service=='promtail':refresh_main()
 # Exactly one service; never build, pull, recreate dependencies or run down.
 main_run(['compose','--project-directory',str(R),'-p',MAIN_PROJECT,'-f',str(MAIN_PLAN),'up','-d','--no-deps','--no-build','--pull','never','--wait','--wait-timeout','180',*(['--force-recreate'] if force else []),service])
 if service in ('web_app','nginx'):
  refresh_main()
  main_update('promtail')
 print('Updated one approved Main service:',service)
if __name__=='__main__':
 a=argparse.ArgumentParser()
 a.add_argument('action',choices=['prepare','deploy-core','deploy-logging','refresh','rollback-core','plan','status','update','start'])
 a.add_argument('environment',choices=['qa','main'])
 a.add_argument('--service',choices=MANAGED)
 a.add_argument('--force-recreate',action='store_true',help='Recreate this one managed service, then refresh collector mounts')
 a.add_argument('--approved-main-change',action='store_true',help='Use only after approval of the exact Main command')
 o=a.parse_args()
 if o.environment=='main':
  need(o.action in ('plan','status','refresh','update','start'),'Historical Main rollout disabled; use plan/status/update')
  if o.action in ('refresh','update','start'):need(o.approved_main_change,'Separate approval required for this exact Main command')
  if o.action=='plan':main_plan()
  elif o.action=='status':main_status()
  elif o.action=='refresh':refresh_main()
  elif o.action=='start':main_start()
  else:main_update(o.service,o.force_recreate)
 else:
  need(o.action not in ('plan','status','update','start'),'These actions are Main-only')
  {'prepare':prepare,'deploy-core':core,'deploy-logging':logging,'refresh':refresh,'rollback-core':rollback_core}[o.action]('qa')
