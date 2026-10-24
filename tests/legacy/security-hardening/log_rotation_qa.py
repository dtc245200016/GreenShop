"""Reconcile DB/phpMyAdmin logging; apply only on the existing isolated QA project."""

if __name__ == "__main__":
 raise SystemExit("Retired QA/recovery harness. Use GreenShop-Official: docker compose up -d --build")
import copy,hashlib,importlib.util,json,os,time
from pathlib import Path
import requests,yaml
R=Path(__file__).resolve().parents[2]
s=importlib.util.spec_from_file_location('a',R/'tests/logging/acceptance.py');a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
rt=a.rt;source=yaml.safe_load((R/'docker-compose.yml').read_text());policy={'driver':'json-file','options':{'max-size':'10m','max-file':'3'}}
def observation(env,service):
 plan=json.loads((a.P/env/'compose.json').read_text());d=rt.info(rt.container(env,service));actual=d['HostConfig']['LogConfig']
 return {'source_configured':source['services'][service].get('logging')==policy,'authoritative_plan_configured':plan['services'][service].get('logging')==policy,'runtime_applied':actual=={'Type':'json-file','Config':policy['options']},'runtime':actual,'container_id':d['Id'],'volume_names':[m['Name'] for m in d['Mounts'] if m['Type']=='volume']}
before={env:{service:observation(env,service) for service in ['db','phpmyadmin']} for env in ['qa','main']}
assert all(v['source_configured'] and v['authoritative_plan_configured'] for services in before.values() for v in services.values())
project=rt.project('qa');db=rt.container('qa','db');assert rt.info(db)['Config']['Labels']['com.docker.compose.project']==project
backup=a.P/'m3/final-hardening'/('qa-db-rotation-'+str(time.time_ns()));backup.mkdir(parents=True,mode=0o700)
plan=json.loads((a.P/'qa/compose.json').read_text());rt.save(backup/'forward-plan.json',plan)
rollback=copy.deepcopy(plan)
for service in ['db','phpmyadmin']:
 old=before['qa'][service]['runtime'];rollback['services'][service]['logging']={'driver':old['Type'],'options':old['Config']}
rt.save(backup/'rollback-plan.json',rollback)
def sql(query):return a.m.sql(rt.container('qa','db'),query,db='greenshop_m2_qa')
def hashes():
 return {t:hashlib.sha256(sql('SELECT * FROM `'+t+'` ORDER BY '+('MigrationId' if t=='__EFMigrationsHistory' else '1')).encode()).hexdigest() for t in sql('SHOW TABLES').splitlines()}
acc=json.loads((a.P/'qa/accounts.json').read_text());customer=requests.Session();admin=requests.Session()
assert a.m.login(customer,*acc['customer']).status_code==302
assert a.m.login(admin,*acc['admin'],path='/Admin/Account/Login').status_code==302
old_hashes=hashes();old_keys=rt.run(['docker','exec',rt.container('qa','web_app'),'sh','-c','find /app/keys /app/wwwroot/uploads/products -type f -exec sha256sum {} +'])
dump=rt.run(['docker','exec',db,'sh','-c','MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysqldump -uroot --single-transaction --routines --triggers --events --no-tablespaces --set-gtid-purged=OFF greenshop_m2_qa'])
fd=os.open(backup/'mysql.sql',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
with os.fdopen(fd,'wb') as f:f.write(dump)
start=time.time()
rt.dc('qa','up','-d','--no-deps','--wait','--wait-timeout','180','db','phpmyadmin')
after={env:{service:observation(env,service) for service in ['db','phpmyadmin']} for env in ['qa','main']}
assert all(v['runtime_applied'] for v in after['qa'].values())
for service in ['db','phpmyadmin']:
 assert before['main'][service]['container_id']==after['main'][service]['container_id']
 assert before['qa'][service]['volume_names']==after['qa'][service]['volume_names']
assert hashes()==old_hashes
assert old_keys==rt.run(['docker','exec',rt.container('qa','web_app'),'sh','-c','find /app/keys /app/wwwroot/uploads/products -type f -exec sha256sum {} +'])
assert customer.get(a.base('qa')+'/ThanhToan/DonHangCuaToi',verify=False,allow_redirects=False,timeout=20).status_code==200
assert admin.get(a.base('qa')+'/Admin/SanPham/QuanLySanPham',verify=False,allow_redirects=False,timeout=20).status_code==200
rt.refresh('qa');rt.dc('qa','up','-d','--no-deps','--wait','--wait-timeout','120','promtail')
events=a.wait(lambda:a.entries(a.query('qa','{environment="qa",service="mysql"}',start=start)),60)
health=rt.info(rt.container('qa','phpmyadmin'))['State']['Health']['Status'];assert health=='healthy'
out={'status':'PARTIAL','observed_utc':a.now(),'before':before,'after':after,'qa_verification':{'status':'PASS','business_table_hashes_equal':True,'tables_compared':len(old_hashes),'key_upload_hashes_equal':True,'existing_admin_customer_sessions_work':True,'mysql_log_ingestion_after_recreate':len(events),'phpmyadmin_health':health,'same_named_volumes':True,'private_dump_created':True,'private_rollback_plan_created':True},'main_changed':False,'classification':{'qa':'CONFIGURED + RUNTIME_APPLIED + VERIFIED (policy, persistence, real ingestion)','main':'CONFIGURED only for DB/phpMyAdmin; existing unbounded json-file runtime intentionally retained'},'limits':['No forced 10 MiB log flood on DB or phpMyAdmin; physical file rollover was previously verified on QA Nginx with the same json-file driver.','No Main DB/phpMyAdmin recreation, log truncation or volume deletion.','Main rollout requires a planned maintenance with fresh backups and explicit operator decision; private rollback plan is prepared.']}
a.record('docker-log-rotation-final',out)
print('PASS QA DB/phpMyAdmin rotation policy, persistence, sessions and real MySQL ingestion; Main CONFIGURED only.',flush=True)
