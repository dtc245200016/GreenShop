"""Read-only historical Main connection-event investigation; never export raw payloads."""

if __name__ == "__main__":
 raise SystemExit("Retired QA/recovery harness. Use GreenShop-Official: docker compose up -d --build")
import collections,datetime,hashlib,importlib.util,json,re,subprocess,time
from pathlib import Path
R=Path(__file__).resolve().parents[2];sp=importlib.util.spec_from_file_location('a',R/'tests/logging/acceptance.py');a=importlib.util.module_from_spec(sp);sp.loader.exec_module(a)
def stamp(s):return datetime.datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()
start='2026-10-16T17:24:00Z';end='2026-10-16T17:30:00Z'
raw=subprocess.run(['docker','logs',a.rt.container('main','web_app')],capture_output=True);observations=[];error_events=[]
for line in (raw.stdout+raw.stderr).decode(errors='replace').splitlines():
 try:d=json.loads(line)
 except ValueError:continue
 cat=d.get('Category');eid=d.get('EventId');ts=d.get('Timestamp')
 if not ts:continue
 if cat=='Microsoft.EntityFrameworkCore.Database.Connection' and eid==20004:
  scope=[x for x in d.get('Scopes',[]) if isinstance(x,dict)];request=next((x.get('RequestId') for x in scope if x.get('RequestId')),None);path=next((x.get('RequestPath') for x in scope if x.get('RequestPath')),None);trace=next((x.get('TraceId') for x in scope if x.get('TraceId')),None)
  error_events.append({'timestamp_utc':ts,'category':cat,'event_id':eid,'level':d.get('LogLevel'),'known_fixed_message_matches':d.get('Message')=="An error occurred using the connection to database 'greenshop' on server 'db'.",'request_id':request if re.fullmatch(r'[0-9A-V]{13}:[0-9A-F]{8}',request or '') else '', 'trace_id':trace if re.fullmatch(r'[0-9a-f]{32}',trace or '') else '', 'route_group':'health' if path=='/health/ready' else 'other','raw_exception_present':bool(d.get('Exception')),'raw_sha256':hashlib.sha256(line.encode()).hexdigest()})
 if start<=ts<=end and (cat=='Microsoft.Hosting.Lifetime' or cat=='Microsoft.EntityFrameworkCore.Migrations'):
  observations.append({'timestamp_utc':ts,'category':cat,'event_id':eid,'level':d.get('LogLevel'),'known_migrations_up_to_date':d.get('Message')=='No migrations were applied. The database is already up to date.'})
api_rows=a.entries(a.query('main','{environment="main",service="greenshop-web"} | json | category="Microsoft.EntityFrameworkCore.Database.Connection"',stamp(start),stamp(end)))
before=[{'timestamp_ns':v[0],'line':json.loads(v[1])} for _,v in api_rows]
db=a.rt.info(a.rt.container('main','db'));web=a.rt.info(a.rt.container('main','web_app'))
p=subprocess.run(['docker','logs','--since',start,'--until',end,db['Id']],capture_output=True);dbraw=p.stdout+p.stderr
p=subprocess.run(['docker','events','--since',start,'--until',end,'--format','{{json .}}'],capture_output=True,timeout=20)
# No unfiltered event attributes, log lines, command text or healthcheck output enter evidence.
events=[]
for line in p.stdout.splitlines():
 d=json.loads(line);attr=d.get('Actor',{}).get('Attributes',{});events.append({'time_ns':d.get('timeNano'),'type':d.get('Type'),'action':d.get('Action'),'name':attr.get('name')})
ds=next(x for x in a.graf('main','/api/datasources') if x['type']=='prometheus');metrics={}
for expr in ['mysql_up','up{job="mysql"}']:
 metrics[expr]=a.graf('main','/api/datasources/proxy/uid/'+ds['uid']+'/api/v1/query_range',params={'query':expr,'start':stamp(start),'end':stamp(end),'step':'15'})['data']['result']
health=[]
for _ in range(3):
 r=a.requests.get(a.base('main')+'/health/ready',verify=False,timeout=15);health.append({'observed_utc':a.now(),'status':r.status_code});time.sleep(1)
assert all(x['status']==200 for x in health)
segment=json.loads((a.E/'main-network-segmentation.json').read_text());original=[x for x in error_events if x['timestamp_utc']=='2026-10-16T17:26:26.305Z'];assert len(original)==1 and before
later=[x for x in error_events if x['timestamp_utc']>'2026-10-16T17:26:26.305Z']
report={'status':'PASS','investigation_verdict':'INCONCLUSIVE','current_active_issue':bool(later) or any(x['status']!=200 for x in health),'observed_utc':a.now(),'historical_event':original[0],'timeline':observations,'rollout_segmentation':segment,'db_container':{'id':db['Id'],'started_at':db['State']['StartedAt'],'restart_count':db['RestartCount'],'health':db['State']['Health']['Status'],'retained_health_history':[{'start':x['Start'],'end':x['End'],'exit_code':x['ExitCode']} for x in db['State']['Health']['Log']]},'web_started_at':web['State']['StartedAt'],'historical_db_log_lines_in_interval':len(dbraw.splitlines()),'historical_db_codes':dict(collections.Counter(re.findall(r'\[MY-\d+\]',dbraw.decode(errors='replace')))),'retained_docker_events':events,'event_buffer_limit':'Bounded historical Docker event buffer; no returned events does not prove no network changes.','historical_prometheus_metrics':metrics,'main_connection_error_events_since_current_container_start':error_events,'later_connection_errors':len(later),'current_readiness_checks':health,'current_sql_select_1':a.m.sql(db['Id'],'SELECT 1')=='1','root_cause':'INCONCLUSIVE: original EventId 20004 has no exception/socket error; bounded Docker events no longer retain rollout actions.','best_supported_hypothesis':'Transient old pooled connection or DNS/network transition around Main database segmentation; completion evidence is approximately 3 seconds before readiness failure. Temporal correlation alone does not prove this mechanism.','alternatives':['Startup-only timing is less consistent with migrations completed and application listening ~39 seconds earlier.','No observed DB restart, crash code, persistent authentication failure or current readiness failure. mysql_up sampled 1 around event; sampling cannot exclude a sub-scrape outage.','Exact socket error, timeout versus connection-pool invalidation, and DNS details cannot be recovered from retained evidence.'],'repair':'No Main application/DB repair or retries/timeouts/schema changes justified by retained evidence. Improve safe diagnostic metadata only; monitor new db.connection.failed events.','qa_reproduction_reference':'diagnostic-runtime-qa.json','changes_to_main_db':'NONE'}
a.record('database-connection-investigation',report)
a.record('logging-diagnostic-investigation',{'status':'PASS','observed_utc':a.now(),'original_stdout_keys':['Timestamp','EventId','LogLevel','Category','Message','State','Scopes'],'stdout_event':original[0],'loki_stored_original_line':before[0],'cause':'Promtail output source safe replaces the line. V1 allowlist omits Message and looks only for security-event scope request_id/route, ignoring framework RequestId/RequestPath/TraceId.','not_grafana_presentation_only':True,'qa_main_pipeline_source':'Same source bind monitoring/promtail/promtail.yml, identical stages; per-environment targets/labels differ.','resolution':'Schema v2 closed diagnostic messages/codes; validated framework request/trace IDs and route group. Never export raw Message/State/Scopes/Exception.','historical_policy':'Historical v1 entries unchanged. No volume reset or whole-history re-ingestion.'})
print('PASS investigation completed; MYSQL_ERROR_INVESTIGATION=INCONCLUSIVE; current active issue:',report['current_active_issue'],'; Main historical connection error count:',len(error_events))
