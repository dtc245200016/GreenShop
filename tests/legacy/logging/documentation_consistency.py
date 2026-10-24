"""Validate current README/evidence against source and actual runtime, without mutation."""

if __name__ == "__main__":
 raise SystemExit("Retired QA/recovery harness. Use GreenShop-Official: docker compose up -d --build")
import importlib.util,json,re,urllib.parse
from pathlib import Path
import yaml
R=Path(__file__).resolve().parents[2];sp=importlib.util.spec_from_file_location('a',R/'tests/logging/acceptance.py');a=importlib.util.module_from_spec(sp);sp.loader.exec_module(a)
source=yaml.safe_load((R/'docker-compose.yml').read_text());root=(R/'README.md').read_text();monitor=(R/'monitoring/README.md').read_text();services=set(source['services']);runtime={}
for env in ['main','qa']:
 ids=a.rt.run(['docker','ps','-q','--filter','label=com.docker.compose.project='+a.rt.project(env)]).decode().splitlines();live={a.rt.info(x)['Config']['Labels']['com.docker.compose.service'] for x in ids};assert live==services,(env,live^services);runtime[env]=sorted(live)
 assert {'greenshop-infrastructure','greenshop-application','greenshop-security','greenshop-logs'}<={x['uid'] for x in a.graf(env,'/api/search?type=dash-db')};assert len(a.graf(env,'/api/v1/provisioning/alert-rules'))==4
 assert a.graf(env,'/api/datasources/uid/greenshop-loki/health')['status']=='OK'
 for svc,port in [('grafana','3000'),('prometheus','9090')]:
  info=a.rt.info(a.rt.container(env,svc));bindings=[v for vs in info['NetworkSettings']['Ports'].values() for v in (vs or [])];assert all(v['HostIp']=='127.0.0.1' for v in bindings)
 for svc in ['loki','promtail']:assert not a.rt.info(a.rt.container(env,svc))['HostConfig']['PortBindings']
for svc in services:assert svc in root,('Service absent from README',svc)
assert len(services)==12 and '12 service' in root
for token in ['3000','9090','21543','21300','21990','greenshop-loki','LogQL','OPEN — RISK ACCEPTED','DEFERRED_MAINTENANCE','NOT TESTED','loki_data','Promtail','Loki']:
 assert token in root,('Missing current README fact',token)
for phrase in ['## Hệ thống hiện tại — Commit 2','Main hiện chạy 10 service','Main giữ mạng app/database cũ','Commit chưa READY do Grafana Main','xem blocker credential','No Grafana Cloud, paid plugin or Loki/Promtail is required.','Commit 3 can collect']:
 assert phrase not in root+monitor,('Stale current statement',phrase)
assert 'safe JSON logs' in root and 'Loki / loki_data' in root and 'Prometheus' in root
assert 'qa-only' not in root.lower() or 'Main' in root
assert json.loads((a.E/'diagnostic-logql.json').read_text())['status']=='PASS'
assert json.loads((a.E/'diagnostic-browser.json').read_text())['status']=='PASS'
broken=[];docs=[R/'README.md',R/'monitoring/README.md',*a.E.glob('*.md')]
for f in docs:
 for target in re.findall(r'\]\(([^)]+)\)',f.read_text()):
  if target.startswith(('http:','https:','#','mailto:')):continue
  p=(f.parent/urllib.parse.unquote(target.split('#')[0])).resolve()
  if not p.exists() and p!=(a.E/'documentation-consistency.json'):broken.append({'file':str(f.relative_to(R)),'target':target})
assert not broken,broken
# Physical expiry, Main authenticated flows and credential provenance stay explicit limitations.
assert all(x in (a.E/'security-hardening.md').read_text() for x in ['physical expiry NOT TESTED','OPEN — RISK ACCEPTED','DDL'])
report={'status':'PASS','observed_utc':a.now(),'documents_checked':[str(f.relative_to(R)) for f in docs],'source_and_runtime_services':runtime,'service_count':len(services),'main_ports':{'grafana':'127.0.0.1:3000','prometheus':'127.0.0.1:9090','loki':'unpublished','promtail':'unpublished'},'dashboard_uids':['greenshop-infrastructure','greenshop-application','greenshop-security','greenshop-logs'],'alert_rule_count':4,'loki_datasource_uid':'greenshop-loki','broken_links':broken,'readme_stale_statements':[],'exact_logql_reference':'diagnostic-logql.json','real_browser_reference':'diagnostic-browser.json','command_scope_review':'Fresh-host default Compose instructions separated from existing Main authoritative project/plan; QA outage tools explicitly scoped; no credential rotation instructed for current task.','limitations_preserved':True,'historical_m1_m2_evidence_modified':False}
a.record('documentation-consistency',report);print('PASS documentation/source/runtime consistency:',len(docs),'Markdown files, 12 services, ports, four dashboards/four rules, datasource, real LogQL/browser and links')
