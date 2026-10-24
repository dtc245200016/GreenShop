"""Real M3 checks. Only incident/regression commands write synthetic QA data.

All observations are recorded under commit3; historical M1/M2 evidence is immutable.
"""

if __name__ == "__main__":
 raise SystemExit("Retired QA/recovery harness. Use GreenShop-Official: docker compose up -d --build")
import argparse,datetime,hashlib,html,importlib.util,json,os,re,secrets,subprocess,sys,time
from pathlib import Path
import requests
R=Path(__file__).resolve().parents[2];P=Path.home()/'.local/share/greenshop-monitoring';E=R/'docs/evidence/commit3'
spec=importlib.util.spec_from_file_location('rt',R/'scripts/logging-runtime.py');rt=importlib.util.module_from_spec(spec);spec.loader.exec_module(rt)
spec=importlib.util.spec_from_file_location('m2',R/'tests/monitoring/acceptance.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.EVIDENCE=E
requests.packages.urllib3.disable_warnings()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def record(name,d):rt.record(name,d)
def graf(env,path,method='GET',**kw):
 port=21300 if env=='qa' else 3000;pw=json.loads((P/env/'passwords.json').read_text())['grafana']
 r=requests.request(method,f'http://127.0.0.1:{port}'+path,auth=('admin',pw),timeout=45,**kw);r.raise_for_status();return r.json()
def loki(env,path,params=None):
 return graf(env,'/api/datasources/proxy/uid/greenshop-loki'+path,params=params)
def query(env,expr,start=None,end=None,instant=False):
 t=time.time();params={'query':expr,'limit':5000}
 if instant:params['time']=str(end or t)
 else:params.update({'start':str(start or t-24*3600),'end':str(end or t),'direction':'forward'})
 d=loki(env,'/loki/api/v1/query' if instant else '/loki/api/v1/query_range',params);assert d['status']=='success';return d['data']['result']
def entries(result):return [(s['stream'],v) for s in result for v in s.get('values',[])]
def wait(fn,timeout=120):
 end=time.monotonic()+timeout;error=None
 while time.monotonic()<end:
  try:
   r=fn()
   if r:return r
  except (requests.RequestException,AssertionError,KeyError,ValueError) as e:error=type(e).__name__
  time.sleep(2)
 raise TimeoutError('Condition not observed; last error '+str(error))
def base(env):return 'https://localhost:'+('21543' if env=='qa' else '443')
def verify(env):
 for s in ['loki','promtail']:
  d=rt.info(rt.container(env,s));assert d['State']['Health']['Status']=='healthy',s
  assert not d['HostConfig']['Privileged'];assert d['HostConfig']['CapDrop']==['ALL'];assert d['Config']['User'].startswith('10001:')
  assert list(d['NetworkSettings']['Networks'])==[rt.project(env)+'_logging_net']
  assert not d['HostConfig']['PortBindings'];assert d['HostConfig']['ReadonlyRootfs']
  assert not any('docker.sock' in x['Source'] or x['Source']=='/var/lib/docker' for x in d['Mounts'])
 assert graf(env,'/api/datasources/uid/greenshop-loki/health')['status']=='OK'
 before=json.loads((P/'m3'/env/'rules-before.json').read_text());rules=graf(env,'/api/v1/provisioning/alert-rules');assert {r['uid']:{k:v for k,v in r.items() if k!='updated'} for r in rules}=={r['uid']:{k:v for k,v in r.items() if k!='updated'} for r in before},'M2 rule definition changed'
 dashboards=graf(env,'/api/search?type=dash-db');uids={x['uid'] for x in dashboards};assert {'greenshop-infrastructure','greenshop-application','greenshop-security','greenshop-logs'}<=uids
 checks=[]
 for name,expr in [('application',f'{{environment="{env}",service="greenshop-web"}}'),('nginx',f'{{environment="{env}",service="nginx"}}'),('mysql',f'{{environment="{env}",service="mysql"}}')]:
  if name=='nginx':requests.get(base(env)+'/m3-controlled-not-found?token=never-log-this-query',verify=False,timeout=15)
  result=wait(lambda:entries(query(env,expr)),60)
  for labels,value in result:
   assert set(labels)<=set(['environment','project','service','source','stream','job','service_name','detected_level']),labels
   assert labels['project']==rt.project(env);json.loads(value[1]);assert 'never-log-this-query' not in value[1]
  checks.append({'name':name,'expression':expr,'datasource_uid':'greenshop-loki','status':'PASS','query_utc':now(),'start_utc':datetime.datetime.fromtimestamp(time.time()-86400,datetime.timezone.utc).isoformat(),'end_utc':now(),'entries':len(result),'samples':[{'labels':x[0],'timestamp_ns':x[1][0],'line':json.loads(x[1][1])} for x in result[-2:]]})
 errors=entries(query(env,f'{{environment="{env}",service="nginx"}} | json | status >= 400 | __error__=""'))
 assert errors
 checks.append({'name':'nginx-errors','expression':f'{{environment="{env}",service="nginx"}} | json | status >= 400 | __error__=""','status':'PASS','entries':len(errors),'query_utc':now()})
 record(env+'-logql',{'status':'PASS','time':now(),'queries':checks,'health':'Loki/Promtail Docker health and Grafana datasource OK','m2_rules_unchanged':True,'dashboard_uids':sorted(uids)})
 print('PASS',env,'real application/Nginx/MySQL log ingestion, four LogQL queries, datasource and M2 preservation',flush=True)
def hardening(env):
 result=[]
 for cid in rt.run(['docker','ps','-q','--filter','label=com.docker.compose.project='+rt.project(env)]).decode().splitlines():
  d=rt.info(cid);s=d['Config']['Labels']['com.docker.compose.service'];top=rt.run(['docker','top',cid]).decode().splitlines()
  result.append({'service':s,'container':d['Name'].lstrip('/'),'container_user':d['Config']['User'] or 'root (default)','processes':top,'pid1_status':{line.split(':',1)[0]:line.split(':',1)[1].strip() for line in Path('/proc/'+str(d['State']['Pid'])+'/status').read_text().splitlines() if line.split(':',1)[0] in ['Uid','Gid','CapEff','NoNewPrivs','Seccomp']},'image':d['Config']['Image'],'image_id':d['Image'],'privileged':d['HostConfig']['Privileged'],'caps_add':d['HostConfig']['CapAdd'],'caps_drop':d['HostConfig']['CapDrop'],'security_options':d['HostConfig']['SecurityOpt'],'readonly_rootfs':d['HostConfig']['ReadonlyRootfs'],'networks':list(d['NetworkSettings']['Networks']),'ports':d['NetworkSettings']['Ports'],'mounts':[{k:x.get(k) for k in ['Type','Destination','Name','RW']} for x in d['Mounts']],'logging':d['HostConfig']['LogConfig'],'memory_bytes':d['HostConfig']['Memory'],'nano_cpus':d['HostConfig']['NanoCpus'],'restart_count':d['RestartCount'],'health':d['State'].get('Health',{}).get('Status')})
 web=rt.container(env,'web_app');uid=rt.run(['docker','exec',web,'id','-u']).decode().strip();assert uid=='1654'
 rt.run(['docker','exec',web,'sh','-c','test -r /run/secrets/metrics_token; test -w /app/keys; test -w /app/wwwroot/uploads/products; test -w /tmp'])
 headers=[]
 for path in ['/','/Account/Login','/Admin','/css/site.css','/metrics','/nginx_status','/Admin/SanPham/ThemSanPham']:
  r=requests.get(base(env)+path,verify=False,allow_redirects=False,timeout=20)
  for key,val in [('X-Frame-Options','SAMEORIGIN'),('X-Content-Type-Options','nosniff'),('Referrer-Policy','strict-origin-when-cross-origin')]:assert r.headers.get(key)==val,(path,key)
  if path in ['/metrics','/nginx_status']:assert r.status_code==404
  headers.append({'path':path,'status':r.status_code,'headers':{k:v for k,v in r.headers.items() if k.lower() in ['x-frame-options','x-content-type-options','referrer-policy','x-xss-protection','server','strict-transport-security']}})
 assert requests.get('http://localhost'+('' if env=='main' else ':21543'),verify=False,allow_redirects=False,timeout=10).status_code in ([301] if env=='main' else [400])
 # Actual network namespace probes; a missing DNS name alone is not proof of isolation.
 db=rt.info(rt.container(env,'db'));ip=db['NetworkSettings']['Networks'][rt.project(env)+'_database_net']['IPAddress']
 probe=['docker','run','--rm','--cap-drop','ALL','--security-opt','no-new-privileges','--network','container:']
 def connect(s):
  p=subprocess.run(probe[:-1]+['container:'+rt.container(env,s),'busybox:1.37.0-musl','nc','-z','-w','2',ip,'3306'],capture_output=True);return p.returncode==0
 positive=connect('web_app');negative=not connect('nginx');logging_negative=not connect('promtail')
 admin_ip=db['NetworkSettings']['Networks'].get(rt.project(env)+'_db_admin_net',{}).get('IPAddress')
 if admin_ip:
  ip=admin_ip;negative=negative and not connect('nginx');logging_negative=logging_negative and not connect('promtail')
 assert positive and logging_negative and negative
 # Exporter account: prove denial by executing non-mutating and zero-row statements.
 pw=json.loads((P/env/'passwords.json').read_text())['exporter'];dbname='greenshop_m2_qa' if env=='qa' else 'greenshop'
 def ex(q):return subprocess.run(['docker','exec','-i',db['Id'],'sh','-c','IFS= read -r MYSQL_PWD; export MYSQL_PWD; exec mysql --protocol=TCP -h 127.0.0.1 -ugreenshop_exporter -N -B'],input=(pw+'\n'+q).encode(),capture_output=True)
 grants=ex('SHOW GRANTS;');assert grants.returncode==0
 denied={}
 for name,q in [('select',f'SELECT * FROM {dbname}.Users LIMIT 0;'),('update',f'UPDATE {dbname}.Products SET StockQuantity=StockQuantity WHERE 1=0;'),('delete',f'DELETE FROM {dbname}.Products WHERE 1=0;'),('user_admin','SELECT User FROM mysql.user LIMIT 0;')]:denied[name]=ex(q).returncode!=0
 assert all(denied.values());assert ex('SHOW GLOBAL STATUS LIKE "Threads_connected";').returncode==0
 lengths={k:len(v) for k,v in json.loads((P/env/'passwords.json').read_text()).items()};assert all(n>=24 for k,n in lengths.items() if k!='grafana')
 record(env+'-hardening',{'status':'PASS' if negative else 'PARTIAL','time':now(),'services':result,'web_uid':uid,'web_writable_paths':'keys, product images, tmp; metrics secret readable','headers':headers,'network_probes':{'web_to_mysql_allowed':positive,'nginx_to_mysql_denied':negative,'promtail_to_mysql_denied':logging_negative},'exporter_grants':grants.stdout.decode().splitlines(),'exporter_denials':denied,'credential_lengths':lengths,'limitations':['Application DB account retains schema DDL for startup EF migrations.','cAdvisor retains existing host mounts/socket trust boundary.','Nginx/phpMyAdmin root masters are not classified as fully non-root.','Main customer/admin authenticated flows are not tested.']})
 print('PASS observed hardening, UID, exporter denials, headers; network denial:',negative,env,flush=True)
def incident(env):
 assert env=='qa'
 wait(lambda:m.scalar('greenshop_auth_login_failures_last_60s')==0 and m.alert_state()['state']=='inactive')
 accounts=json.loads((P/'qa/accounts.json').read_text());session=requests.Session();start=time.time();start_utc=now();before=m.scalar('greenshop_auth_login_failures_total')
 for _ in range(4):
  r=m.login(session,accounts['customer'][0],secrets.token_urlsafe(24));assert r.status_code==200 and 'không chính xác' in html.unescape(r.text)
 wait(lambda:m.scalar('greenshop_auth_login_failures_last_60s')==4,30);time.sleep(12);four=m.alert_state();assert four['state']=='inactive'
 assert m.login(session,accounts['customer'][0],secrets.token_urlsafe(24)).status_code==200
 assert time.time()-start<60
 firing=wait(lambda:(d if (d:=m.alert_state())['state']=='firing' else None),35)
 receipts=wait(lambda:[x for x in m.incidents('firing') if x['received_at']>=start_utc],25)
 expr='{environment="qa",service="greenshop-web"} | json | event="auth.login.failed" | incident="GS-SEC-001" | __error__=""'
 events=wait(lambda:(v if len(v:=entries(query('qa',expr,start=start-1)))==5 else None),45)
 assert m.scalar('greenshop_auth_login_failures_total')==before+5
 ids=[json.loads(v[1])['request_id'] for labels,v in events];assert len(set(ids))==5 and all(ids)
 count_expr='sum(count_over_time({environment="qa",service="greenshop-web"} | json | event="auth.login.failed" | __error__="" [1m]))'
 count=query('qa',count_expr,instant=True);assert float(count[0]['value'][1])==5
 record('gs-sec-001-firing',{'status':'PASS','start_utc':start_utc,'observed_utc':now(),'four_failures_rule':four,'fifth_rule':firing,'counter_before':before,'counter_after':before+5,'rolling_window':5,'logql_expression':expr,'count_expression':count_expr,'log_count':5,'distinct_request_ids':ids,'events':[{'timestamp_ns':v[0],'event':json.loads(v[1])} for labels,v in events],'notification':receipts[-1],'count_query_result':count,'scope':'real rejected QA fixture credentials, not an actual intrusion'})
 print('PASS GS-SEC-001: four Normal, fifth Firing, five unique Loki events, webhook received',flush=True)
 resolved=wait(lambda:(d if (d:=m.alert_state())['state']=='inactive' else None),110)
 recovery=wait(lambda:[x for x in m.incidents('resolved') if x['received_at']>=start_utc],35)
 record('gs-sec-001-resolved',{'status':'PASS','observed_utc':now(),'rule':resolved,'rolling_window':m.scalar('greenshop_auth_login_failures_last_60s'),'notification':recovery[-1]})
 print('PASS GS-SEC-001 automatically resolved; real resolved notification received',flush=True)
def persistence(env):
 assert env=='qa'
 expr='{environment="qa",service="greenshop-web"} | json | event="auth.login.failed" | __error__=""'
 end=time.time();before=entries(query(env,expr,end=end));assert before
 rt.dc(env,'restart','promtail');wait(lambda:rt.info(rt.container(env,'promtail'))['State']['Health']['Status']=='healthy',100)
 assert entries(query(env,expr,end=end))==before
 rt.dc(env,'stop','loki');requests.get(base(env)+'/m3-outage-recovery',verify=False,timeout=20);rt.dc(env,'start','loki')
 wait(lambda:rt.info(rt.container(env,'loki'))['State']['Health']['Status']=='healthy',100)
 assert entries(query(env,expr,end=end))==before
 # Recreate a real QA source; refresh is mandatory because container IDs changed.
 rt.dc(env,'up','-d','--no-deps','--force-recreate','--wait','--wait-timeout','180','nginx');rt.refresh(env);rt.dc(env,'up','-d','--no-deps','--wait','--wait-timeout','120','promtail')
 r=requests.get(base(env)+'/m3-recreated-source',verify=False,timeout=15);assert r.status_code==404
 wait(lambda:entries(query(env,'{environment="qa",service="nginx"} | json | status="404" | __error__=""',start=time.time()-60)),45)
 assert entries(query(env,expr,end=end))==before,'duplicates or missing persisted incident entries'
 d=rt.info(rt.container(env,'promtail'));assert any(x['Type']=='volume' and x['Destination']=='/positions' for x in d['Mounts'])
 record('qa-persistence',{'status':'PASS','time':now(),'incident_entries_before':len(before),'incident_entries_after':len(entries(query(env,expr,end=end))),'checks':['Promtail restart preserves positions and fixed-range event count','Loki stop/start retains real security events','Website serves during Loki outage','Nginx forced recreate + audited target refresh + new ingestion','No duplicate security events in fixed interval'],'limits':'Bounded in-memory retries; no guarantee of zero loss for long outages/rotation. Retention deletion over 72h is not time-travel tested.'})
 print('PASS QA collector/Loki restarts, source recreate, fixed-range persistence and bounded outage',flush=True)
def regression(env):
 assert env=='qa'
 spec=importlib.util.spec_from_file_location('reg',R/'tests/monitoring/regression.py');reg=importlib.util.module_from_spec(spec);spec.loader.exec_module(reg);reg.m.EVIDENCE=E;reg.regression()
 # Execute the existing engagement suite with its evidence destination redirected.
 source=(R/'tests/monitoring/engagement.py').read_text().replace("m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)","m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.EVIDENCE=R/'docs/evidence/commit3'")
 exec(compile(source,str(R/'tests/monitoring/engagement.py'),'exec'),{'__file__':str(R/'tests/monitoring/engagement.py'),'__name__':'__m3_engagement__'})
 print('PASS existing business + engagement + real browser/SignalR regression',flush=True)
def main_preservation(env):
 assert env=='main';before=json.loads((P/'m3/main/data-before.json').read_text());after=m.snapshot()
 assert before['tables']==after['tables'] and before['files']==after['files'] and before['tls']==after['tls'] and before['migrations']==after['migrations']
 old=json.loads((P/'m3/main/core-before.json').read_text())
 for s in ['db','phpmyadmin','prometheus','grafana']:assert rt.info(rt.container(env,s))['Id']==old[s]['Id'],s+' recreated'
 assert dict(v.split('=',1) for v in old['web_app']['Config']['Env'])==dict(v.split('=',1) for v in rt.info(rt.container(env,'web_app'))['Config']['Env'])
 record('main-preservation',{'status':'PASS','time':now(),'tables_compared':len(before['tables']),'business_table_hashes_equal':True,'uploads_keys_tls_hashes_equal':True,'migration_history_equal':True,'original_db_phpmyadmin_prometheus_grafana_container_ids_preserved':True,'application_environment_credentials_equal':True,'authenticated_main':'NOT TESTED; no credentials supplied; no Main account/order writes'})
 print('PASS Main data, files, credentials, TLS and migration history preserved',flush=True)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('action',choices=['verify','hardening','incident','persistence','regression','main-preservation']);a.add_argument('environment',choices=['qa','main']);o=a.parse_args();globals()[o.action.replace('-','_')](o.environment)
