"""Private backup/restore, rollback rehearsal and bounded network segmentation."""

if __name__ == "__main__":
 raise SystemExit("Retired QA/recovery harness. Use GreenShop-Official: docker compose up -d --build")
import datetime,hashlib,importlib.util,json,os,subprocess,sys,tarfile,time
from pathlib import Path
import requests
R=Path(__file__).resolve().parents[2]
sp=importlib.util.spec_from_file_location('a',R/'tests/logging/acceptance.py');a=importlib.util.module_from_spec(sp);sp.loader.exec_module(a)
rt=a.rt;P=a.P;E=a.E;m=a.m
def restore(env):
 assert env=='main'
 b=P/'m3/main';snapshot=json.loads((b/'data-before.json').read_text());db=rt.container('qa','db');schema='greenshop_m3_restore'
 # Dedicated restore schema in existing isolated QA DB; no Main tables or credentials changed.
 assert m.sql(db,"SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name='"+schema+"'",db='greenshop_m2_qa')=='0'
 m.sql(db,'CREATE DATABASE '+schema,db='greenshop_m2_qa')
 m.sql(db,(b/'mysql.sql').read_text(),db=schema)
 hashes={t:hashlib.sha256(m.sql(db,'SELECT * FROM `'+t+'` ORDER BY '+('MigrationId' if t=='__EFMigrationsHistory' else '1'),db=schema).encode()).hexdigest() for t in snapshot['tables']}
 assert hashes==snapshot['tables']
 archives=[]
 for name in ['keys','uploads','tls']:
  f=b/(name+'.tar')
  with tarfile.open(f) as t:
   files=[x for x in t.getmembers() if x.isfile()]
   assert all(len(t.extractfile(x).read())==x.size for x in files)
  archives.append({'name':f.name,'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'files':len(files)})
 rt.record('backup-restore',{'status':'PASS','time':a.now(),'database':'Fresh Main dump restored into isolated QA schema; every table content hash equals predeployment snapshot','tables_verified':len(hashes),'archives':archives,'private_only':True})
 print('PASS fresh Main backup restored in isolated QA schema; all table hashes match',flush=True)
def rollback(env):
 assert env=='qa'
 old=rt.info(rt.container('qa','web_app'));db=rt.container(env,'db');users=m.sql(db,'SELECT COUNT(*) FROM Users',db='greenshop_m2_qa')
 rt.rollback_core(env)
 try:
  acc=json.loads((P/'qa/accounts.json').read_text());s=requests.Session();assert m.login(s,*acc['customer']).status_code==302
  assert requests.get(a.base(env)+'/health/ready',verify=False,timeout=20).status_code==200
 finally:
  rt.core(env);rt.logging(env)
 assert m.sql(db,'SELECT COUNT(*) FROM Users',db='greenshop_m2_qa')==users
 acc=json.loads((P/'qa/accounts.json').read_text());assert m.login(requests.Session(),*acc['customer']).status_code==302
 rt.record('qa-rollback',{'status':'PASS','time':a.now(),'checks':['Previous M2 web image/Nginx config and exact ownership manifest restored','Real Customer sign-in with existing key ring succeeds on rollback','M3 non-root web restored and existing Customer credentials sign in','Users count unchanged','Collector refreshed for recreated source containers'],'scope':'QA only; Main rollback not executed'})
 print('PASS QA rollback to M2 and return to M3 with real authentication',flush=True)
def segment(env):
 assert env=='main'
 c=json.loads((P/env/'compose.json').read_text());network=rt.project(env)+'_database_net';old=rt.project(env)+'_app_net'
 rt.run(['docker','network','create','--internal',network])
 before={s:rt.info(rt.container(env,s))['NetworkSettings']['Networks'] for s in ['db','web_app','mysql-exporter','phpmyadmin']}
 rt.save(P/'m3/main/networks-before.json',before)
 try:
  for s in ['db','web_app','mysql-exporter','phpmyadmin']:
   rt.run(['docker','network','connect','--alias',s,network,rt.container(env,s)])
  # Keep original loopback publishing: internal-only networks suppress Docker NAT.
  admin=rt.project(env)+'_db_admin_net'
  rt.run(['docker','network','create',admin])
  rt.run(['docker','network','connect','--alias','db',admin,rt.container(env,'db')])
  rt.run(['docker','network','connect','--alias','phpmyadmin',rt.project(env)+'_admin_net',rt.container(env,'phpmyadmin')])
  c['networks']['db_admin_net']={'name':admin,'driver':'bridge'}
  c['services']['db']['networks']['db_admin_net']=None
  c['services']['phpmyadmin']['networks']['admin_net']=None
  # Remove DB from proxy network only after all legitimate consumers have a DB-zone route.
  for s in ['db','mysql-exporter','phpmyadmin']:
   rt.run(['docker','network','disconnect',old,rt.container(env,s)])
  a.wait(lambda:requests.get(a.base(env)+'/health/ready',verify=False,timeout=10).status_code==200,80)
  for s in ['db','web_app','mysql-exporter','phpmyadmin']:
   c['services'][s]['networks']['database_net']=None
   if s!='web_app':c['services'][s]['networks'].pop('app_net',None)
  c['networks']['database_net']={'name':network,'driver':'bridge','internal':True}
  rt.save(P/env/'compose.json',c)
 except Exception:
  # Restore exact attachments/aliases without restarting database or changing data.
  for s,nets in before.items():
   cid=rt.container(env,s);current=rt.info(cid)['NetworkSettings']['Networks']
   if old in nets and old not in current:rt.run(['docker','network','connect','--alias',s,old,cid])
  raise
 rt.record('main-network-segmentation',{'status':'PASS','time':a.now(),'method':'Connect DB/web/exporter/phpMyAdmin to internal database_net, then detach DB/admin/exporter from application network; no database recreation','database_container_id':rt.container(env,'db'),'rollback':'Exact previous network metadata saved privately; reconnect old network aliases before detaching new network.'})
 print('PASS Main DB segmentation with unchanged DB/phpMyAdmin containers',flush=True)
def state_backup(env):
 assert env=='main'
 b=P/'m3/main';cid=rt.container(env,'grafana')
 assert not (b/'grafana-state.tar').exists(),'Refuse to overwrite the predeployment state backup'
 rt.dc(env,'stop','grafana')
 try:
  data=rt.run(['docker','run','--rm','--network','none','--volumes-from',cid+':ro','busybox:1.37.0-musl','tar','cf','-','-C','/var/lib/grafana','.'])
  f=b/'grafana-state.tar';f.write_bytes(data);f.chmod(0o600)
  with tarfile.open(f) as t:assert any(x.name.endswith('grafana.db') for x in t.getmembers())
 finally:rt.dc(env,'start','--wait','--wait-timeout','120','grafana')
 # Recover baseline Nginx source for a concrete Main rollback (bind path currently points at M3 source).
 f=b/'nginx-before.conf';f.write_bytes(rt.run(['git','-C',str(R),'show','HEAD:nginx/default.conf']));f.chmod(0o644)
 c=json.loads((b/'before-plan.json').read_text())
 for v in c['services']['nginx']['volumes']:
  if v['target']=='/etc/nginx/conf.d/default.conf':v['source']=str(f)
 rt.save(b/'before-plan.json',c)
 rt.record('main-state-backup',{'status':'PASS','time':a.now(),'grafana':'Brief controlled Grafana stop; full SQLite/plugins/config volume archive, readable grafana.db member; Grafana restarted healthy','prometheus':'Not modified/recreated; original persisted TSDB volume and container retained','rollback_nginx':'Exact HEAD baseline config stored privately, separate from M3 source bind','archive_bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()})
 print('PASS consistent Grafana state backup and concrete Nginx rollback config',flush=True)
if __name__=='__main__':globals()[sys.argv[1].replace('-','_')](sys.argv[2])
