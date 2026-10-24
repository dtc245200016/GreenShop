"""Query real new diagnostic records and existing LogQL schema through Grafana."""

if __name__ == "__main__":
 raise SystemExit("Retired QA/recovery harness. Use GreenShop-Official: docker compose up -d --build")
import datetime,importlib.util,json,time
from pathlib import Path
R=Path(__file__).resolve().parents[2];s=importlib.util.spec_from_file_location('a',R/'tests/logging/acceptance.py');a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
qa=json.loads((a.E/'diagnostic-runtime-qa.json').read_text());start=qa['start_epoch'];end=time.time();queries=[]
def iso(t):return datetime.datetime.fromtimestamp(t,datetime.timezone.utc).isoformat()
for env,name,expr,lo in [('qa','safe DB diagnostic','{environment="qa",service="greenshop-web"} | json | schema_version="2" | diagnostic_code="db.connection.failed" | __error__=""',start),('qa','controlled exception','{environment="qa",service="greenshop-web"} | json | schema_version="2" | diagnostic_code="http.request.exception" | __error__=""',start),('qa','failed authentication','{environment="qa",service="greenshop-web"} | json | schema_version="2" | event="auth.login.failed" | __error__=""',start),('qa','successful authentication','{environment="qa",service="greenshop-web"} | json | schema_version="2" | event="auth.login.succeeded" | __error__=""',start),('main','application','{environment="main",service="greenshop-web"}',end-86400),('main','nginx','{environment="main",service="nginx"}',end-600),('main','mysql','{environment="main",service="mysql"}',end-86400)]:
 rows=a.entries(a.query(env,expr,lo,end));assert rows,(env,name)
 queries.append({'status':'PASS','environment':env,'name':name,'expression':expr,'start_utc':iso(lo),'end_utc':iso(end),'query_utc':a.now(),'entries':len(rows),'safe_samples':[json.loads(v[1]) for _,v in rows[:2]]})
# Count at a fixed timestamp containing the targeted QA failures, not the old 5-event incident.
expr='sum(count_over_time({environment="qa",service="greenshop-web"} | json | schema_version="2" | event="auth.login.failed" | __error__="" [15m]))';results=a.query('qa',expr,end=end,instant=True);assert results and float(results[0]['value'][1])>=1
queries.append({'status':'PASS','environment':'qa','name':'v2 targeted failure count','expression':expr,'query_utc':a.now(),'evaluation_epoch':end,'range':'15m','value':float(results[0]['value'][1]),'scope':'Targeted schema failures; not the retained exact-five GS-SEC-001 incident.'})
a.record('diagnostic-logql',{'status':'PASS','observed_utc':a.now(),'queries':queries,'dashboard_uid':'greenshop-logs','new_diagnostic_panel_id':6,'original_queries_compatible':True})
print('PASS eight real diagnostic/compatible LogQL queries and count',flush=True)
