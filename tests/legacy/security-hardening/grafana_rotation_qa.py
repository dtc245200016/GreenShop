"""Exercise Grafana password rotation and rollback only on the existing QA project."""

if __name__ == "__main__":
 raise SystemExit("Retired QA/recovery harness. Use GreenShop-Official: docker compose up -d --build")
import copy,importlib.util,json,os,secrets,time
from pathlib import Path
import requests
R=Path(__file__).resolve().parents[2]
s=importlib.util.spec_from_file_location('a',R/'tests/logging/acceptance.py');a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
rt=a.rt;env='qa';cid=rt.container(env,'grafana');d=rt.info(cid)
assert d['Config']['Labels']['com.docker.compose.project']=='greenshop-m2-qa'
root='http://127.0.0.1:21300';secretfile=Path(next(m['Source'] for m in d['Mounts'] if m['Destination']=='/run/secrets/grafana_password'))
passwords=a.P/'qa/passwords.json';before=passwords.read_bytes();state=json.loads(before);old=state['grafana'];new=secrets.token_urlsafe(32)
assert old!=new and secretfile.read_text().strip()==old
backup=a.P/'m3/final-hardening'/('qa-grafana-rotation-'+str(time.time_ns()));backup.mkdir(parents=True,mode=0o700)
for name,data in [('passwords-before.json',before),('grafana-password-before',secretfile.read_bytes())]:
 fd=os.open(backup/name,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
 with os.fdopen(fd,'wb') as f:f.write(data)
vol=next(m['Name'] for m in d['Mounts'] if m['Destination']=='/var/lib/grafana')
code='''import sqlite3,sys,os
src=sqlite3.connect('file:/state/grafana.db?mode=ro',uri=True)
dst=sqlite3.connect('/tmp/grafana-backup.db');src.backup(dst);dst.close();src.close()
sys.stdout.buffer.write(open('/tmp/grafana-backup.db','rb').read())
'''
db=rt.run(['docker','run','--rm','--network','none','--cap-drop','ALL','--security-opt','no-new-privileges','-v',vol+':/state:ro','python:3.12.10-alpine3.21','python','-c',code])
assert db.startswith(b'SQLite format 3\0')
fd=os.open(backup/'grafana.db',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'wb') as f:f.write(db)
def api(password,path,method='GET',**kw):
 r=requests.request(method,root+path,auth=('admin',password),timeout=30,**kw);r.raise_for_status();return r.json()
admin_id=api(old,'/api/user')['id']
def definitions(password):
 return {r['uid']:{k:v for k,v in r.items() if k!='updated'} for r in api(password,'/api/v1/provisioning/alert-rules')}
rules=definitions(old);dashboards={d['uid'] for d in api(old,'/api/search?type=dash-db')}
def sync(password):
 # Preserve inode because Docker uses a single-file bind for this secret.
 secretfile.chmod(0o600)
 try:
  with secretfile.open('w') as f:f.write(password);f.flush();os.fsync(f.fileno())
 finally:secretfile.chmod(0o444)
 updated=copy.deepcopy(state);updated['grafana']=password;rt.save(passwords,updated)
changed=False;proof={}
try:
 api(old,f'/api/admin/users/{admin_id}/password',method='PUT',json={'password':new});changed=True;sync(new)
 assert api(new,'/api/user')['id']==admin_id
 assert requests.get(root+'/api/user',auth=('admin',old),timeout=20).status_code==401
 assert definitions(new)==rules
 assert {x['uid'] for x in api(new,'/api/search?type=dash-db')}==dashboards
 rt.dc('qa','restart','grafana');a.wait(lambda:rt.info(cid)['State']['Health']['Status']=='healthy',120)
 assert api(new,'/api/user')['id']==admin_id
 assert rt.run(['docker','exec',cid,'cat','/run/secrets/grafana_password']).decode().strip()==new
 assert api(new,'/api/datasources/uid/greenshop-loki/health')['status']=='OK'
 assert api(new,'/api/datasources/uid/greenshop-prometheus/health')['status']=='OK'
 from playwright.sync_api import sync_playwright
 with sync_playwright() as p:
  b=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_EXECUTABLE'));page=b.new_page()
  page.goto(root+'/login');page.locator('input[name=user]').fill('admin');page.locator('input[name=password]').fill(new);page.get_by_role('button',name='Log in',exact=True).click();page.wait_for_url(lambda u:'/login' not in u,timeout=45000);b.close()
 logs=__import__('subprocess').run(['docker','logs','--since','20m',cid],capture_output=True)
 assert new.encode() not in logs.stdout+logs.stderr
 proof={'new_password_login_api_and_browser':True,'old_password_rejected':True,'restart_retains_new_password':True,'mounted_secret_and_private_state_synced':True,'dashboards_and_rule_definitions_preserved':True,'both_datasources_healthy':True,'temporary_password_absent_from_grafana_logs':True}
finally:
 if changed:
  api(new,f'/api/admin/users/{admin_id}/password',method='PUT',json={'password':old});sync(old)
  assert api(old,'/api/user')['id']==admin_id
  assert requests.get(root+'/api/user',auth=('admin',new),timeout=20).status_code==401
  assert definitions(old)==rules
 assert secretfile.read_text().strip()==old
 assert json.loads(passwords.read_text())==json.loads(before)
assert proof
a.record('grafana-rotation-qa',{'status':'PASS','observed_utc':a.now(),'scope':'QA only; Main credentials and containers unchanged','proof':proof,'rollback_verified':True,'qa_original_credentials_restored':True,'sqlite_online_backup_bytes':len(db),'private_backup_permissions':'0700 directory; 0600 files outside repository','main_rotation_performed':False,'method':'Authenticated Admin API + inode-preserving secret write + private JSON sync + restart + real browser login + API rollback; no user/volume reset'})
print('PASS QA Grafana rotation, browser/API/restart/provisioning and rollback; original QA credentials restored; Main unchanged.',flush=True)
