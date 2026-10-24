"""Targeted diagnostic schema rollout. Fault injection is locked to isolated QA.

Main applies only a tested Promtail config restart, with unchanged IDs/volumes.
"""

if __name__ == "__main__":
 raise SystemExit("Retired QA/recovery harness. Use GreenShop-Official: docker compose up -d --build")
import datetime,hashlib,importlib.util,json,subprocess,sys,time
from pathlib import Path
import requests,yaml,html,re
R=Path(__file__).resolve().parents[2];sp=importlib.util.spec_from_file_location('a',R/'tests/logging/acceptance.py');a=importlib.util.module_from_spec(sp);sp.loader.exec_module(a)
def fields(env,code,start):return a.entries(a.query(env,'{environment="'+env+'",service="greenshop-web"} | json | schema_version="2" | diagnostic_code="'+code+'" | __error__=""',start=start))
def safe_entries(rows):return [{'timestamp_ns':v[0],'line':json.loads(v[1])} for _,v in rows]
def apply(env):
 baseline={s:a.rt.info(a.rt.container(env,s)) for s in ['web_app','db','nginx','phpmyadmin','prometheus','grafana','loki','promtail']}
 p=a.P/'m3'/env/'diagnostic-v2';p.mkdir(mode=0o700,exist_ok=True)
 backup=p/'promtail-v1.yml'
 if not backup.exists():backup.write_bytes(Path('/tmp/promtail-v1-backup.yml').read_bytes());backup.chmod(0o600)
 # Parse with the exact current binary, then restart only the existing collector.
 d=baseline['promtail'];config=next(m for m in d['Mounts'] if Path(m['Source']).resolve()==(R/'monitoring/promtail/promtail.yml').resolve())
 assert Path(config['Source']).resolve()==(R/'monitoring/promtail/promtail.yml').resolve()
 a.rt.run(['docker','run','--rm','--network','none','--user','10001:0','--cap-drop','ALL','--security-opt','no-new-privileges','-v',str(R/'monitoring/promtail/promtail.yml')+':/etc/promtail/config.yml:ro','grafana/promtail:3.6.11','-config.file=/etc/promtail/config.yml','-check-syntax'])
 fixed_end=time.time();fixed_start=fixed_end-86400;expr='{environment="'+env+'",service="mysql"}';old=a.entries(a.query(env,expr,fixed_start,fixed_end));assert old
 if '--resume-verification' not in sys.argv:a.rt.dc(env,'restart','promtail')
 a.wait(lambda:a.rt.info(d['Id'])['State']['Health']['Status']=='healthy',100)
 assert a.entries(a.query(env,expr,fixed_start,fixed_end))==old
 actual=a.rt.run(['docker','run','--rm','--network','container:'+d['Id'],'--cap-drop','ALL','--security-opt','no-new-privileges','busybox:1.37.0-musl','wget','-qO-','http://127.0.0.1:9080/config']).decode()
 match=re.search(r'<pre id="config_yaml">(.*?)</pre>',actual,re.S)
 if match:actual=html.unescape(match.group(1))
 loaded=yaml.safe_load(actual);desired=yaml.safe_load((R/'monitoring/promtail/promtail.yml').read_text())
 for index in [1,2,3]:
  assert loaded['scrape_configs'][0]['pipeline_stages'][index]['match']['stages'][1]['template']==desired['scrape_configs'][0]['pipeline_stages'][index]['match']['stages'][1]['template']
 for s,b in baseline.items():
  after=a.rt.info(a.rt.container(env,s));assert after['Id']==b['Id'] and sorted(after['Mounts'],key=lambda m:m['Destination'])==sorted(b['Mounts'],key=lambda m:m['Destination']);assert after['Image']==b['Image']
 return {'runtime_templates_equal_source':True,'collector_id_preserved':True,'all_service_ids_images_mounts_preserved':True,'historical_mysql_entries_preserved':len(old),'restart_only':'promtail','private_config_backup':True,'rollback':'Restore private diagnostic-v2/promtail-v1.yml to original source bind and restart Promtail only; never reset positions or Loki storage.'}
def qa():
 start=time.time();rollout=apply('qa');db=a.rt.container('qa','db');web=a.rt.container('qa','web_app');schema='greenshop_m2_qa'
 def hashdb():
  tables=a.m.sql(db,'SHOW TABLES',db=schema).splitlines();return {t:hashlib.sha256(a.m.sql(db,'SELECT * FROM `'+t+'` ORDER BY '+('MigrationId' if t=='__EFMigrationsHistory' else '1'),db=schema).encode()).hexdigest() for t in tables}
 before=hashdb();network=a.rt.project('qa')+'_database_net';net=a.rt.info(web)['NetworkSettings']['Networks'][network];request_status={}
 a.rt.save(a.P/'m3/qa/diagnostic-v2/network-before.json',net)
 # Controlled network loss on QA web only: real application logger and exception middleware.
 a.rt.run(['docker','network','disconnect',network,web]);failure_start=time.time()
 try:
  r=requests.get(a.base('qa')+'/health/ready',verify=False,timeout=15);request_status['/health/ready']=r.status_code
  # Direct QA namespace request avoids Nginx 60s timeout cancelling EF's existing bounded retries.
  p=subprocess.run(['docker','run','--rm','--network','container:'+web,'--cap-drop','ALL','--security-opt','no-new-privileges','busybox:1.37.0-musl','wget','-S','-T','300','-O','/dev/null','http://127.0.0.1:8080/SanPham/CuaHang'],capture_output=True,timeout=320)
  assert b'500 Internal Server Error' in p.stderr,p.stderr[-300:]
  request_status['/SanPham/CuaHang_direct_qa_namespace']=500
  assert request_status['/health/ready']==503
  a.wait(lambda:fields('qa','http.request.exception',failure_start),60)
 finally:
  args=['docker','network','connect']
  for alias in net.get('Aliases') or []:args+=['--alias',alias]
  a.rt.run(args+[network,web])
 a.wait(lambda:requests.get(a.base('qa')+'/health/ready',verify=False,timeout=10).status_code==200,120)
 # Real auth, with credentials loaded privately; never print requests, cookies or forms.
 accounts=json.loads((a.P/'qa/accounts.json').read_text());session=requests.Session()
 assert a.m.login(session,*accounts['customer']).status_code==302
 assert '/Login' not in session.get(a.base('qa')+'/Account/ThongTin',verify=False,timeout=20).url
 assert a.m.login(requests.Session(),accounts['customer'][0],'M3_fake_invalid_credential_for_QA_only').status_code==200
 assert a.m.login(requests.Session(),*accounts['admin'],path='/Admin/Account/Login').status_code==302
 results={}
 for code in ['db.connection.failed','http.request.exception','auth.login.failed','auth.login.succeeded']:
  rows=a.wait(lambda:fields('qa',code,start),90);results[code]=safe_entries(rows)
 for code in ['db.connection.failed','http.request.exception']:
  assert any(x['line']['request_id'] and x['line']['trace_id'] and x['line']['route'] in ['health','catalog'] for x in results[code]),code
 assert before==hashdb(),'QA business tables changed by diagnostic test'
 # New fixed interval: collector checkpoint and existing Loki storage across collector restart.
 end=time.time();expr='{environment="qa",service="greenshop-web"} | json | schema_version="2" | __error__=""';frozen=a.entries(a.query('qa',expr,start,end));assert frozen
 time.sleep(7);a.rt.dc('qa','restart','promtail');a.wait(lambda:a.rt.info(a.rt.container('qa','promtail'))['State']['Health']['Status']=='healthy',90);time.sleep(5)
 assert a.entries(a.query('qa',expr,start,end))==frozen,'Duplicate or missing fixed-range entries after restart'
 a.verify('qa');a.hardening('qa')
 a.record('diagnostic-runtime-qa',{'status':'PASS','observed_utc':a.now(),'start_epoch':start,'failure_start_epoch':failure_start,'rollout':rollout,'real_fault':'Temporarily disconnect ONLY QA web from internal database network; restore original aliases in finally. No DB stop/recreate/schema change.','request_status':request_status,'recovered_readiness':200,'same_business_table_hashes':True,'tables_compared':len(before),'new_diagnostic_samples':results,'new_schema_fixed_range_entries':len(frozen),'fixed_range_entries_equal_after_restart':True,'authentication_admin_customer':'PASS, real QA forms and CSRF; auth success and failure use schema v2','business_scope':'Historical full business/upload/SignalR/AI fixture evidence retained; no application image or business code changed.'})
 print('PASS QA real DB failure + middleware exception; recovered network, data, auth and v2 correlation; collector restart no duplicates',flush=True)
def main():
 proof=json.loads((a.E/'diagnostic-runtime-qa.json').read_text());assert proof['status']=='PASS';assert json.loads((a.E/'diagnostic-pipeline-tests.json').read_text())['status']=='PASS'
 # Real Main migrations/lifecycle logs after original deployment remain historical v1;
 # no Main fault or application restart is used to manufacture a diagnostic event.
 start=time.time();rollout=apply('main');requests.get(a.base('main')+'/',verify=False,timeout=20)
 # A safe known framework information event may not occur naturally. Health/stored
 # collector config, new Nginx ingestion and absence of parser errors are verified.
 for _ in range(2):assert requests.get(a.base('main')+'/health/ready',verify=False,timeout=15).status_code==200
 a.wait(lambda:a.entries(a.query('main','{environment="main",service="nginx"}',start=start)),60)
 a.verify('main');a.hardening('main');a.main_preservation('main')
 raw=subprocess.run(['docker','logs','--since',datetime.datetime.fromtimestamp(start,datetime.timezone.utc).isoformat(),a.rt.container('main','promtail')],capture_output=True)
 assert b'failed to create pipeline' not in raw.stderr+raw.stdout
 a.record('diagnostic-runtime-main',{'status':'PASS','observed_utc':a.now(),'rollout':rollout,'pipeline_sha256':hashlib.sha256((R/'monitoring/promtail/promtail.yml').read_bytes()).hexdigest(),'readiness':200,'main_fault_injection':False,'new_main_db_failure':'NOT TESTED; no Main failure manufactured','new_main_authenticated_events':'NOT TESTED; no Main account credentials used','historical_records':'Unchanged schema v1. No re-ingestion/reset; v2 applies to newly emitted entries only.','qa_diagnostic_test_reference':'diagnostic-runtime-qa.json'})
 print('PASS Main tested Promtail-only rollout; all original IDs/volumes/images preserved, website and ingestion healthy',flush=True)
if __name__=='__main__':{'qa':qa,'main':main}[sys.argv[1]]()
