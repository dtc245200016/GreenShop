"""Runtime known-secret scan and telemetry/config acceptance. Outputs no secrets."""

if __name__ == "__main__":
 raise SystemExit("Retired QA/recovery harness. Use GreenShop-Official: docker compose up -d --build")
import datetime,importlib.util,json,re,subprocess,time
from pathlib import Path
import requests,yaml
R=Path(__file__).resolve().parents[2]
sp=importlib.util.spec_from_file_location('a',R/'tests/logging/acceptance.py');a=importlib.util.module_from_spec(sp);sp.loader.exec_module(a)
rt=a.rt
def audit(env):
 pw=json.loads((a.P/env/'passwords.json').read_text());known=[v for v in pw.values() if len(v)>=8]
 w=rt.info(rt.container(env,'web_app'));db=rt.info(rt.container(env,'db'));values=dict(x.split('=',1) for x in db['Config']['Env'])
 for k in ['MYSQL_ROOT_PASSWORD','MYSQL_PASSWORD']:
  if values.get(k):known.append(values[k])
 webenv=dict(x.split('=',1) for x in w['Config']['Env'])
 for k in ['AiChat__ApiKey','GEMINI_API_KEY']:
  if webenv.get(k):known.append(webenv[k])
 tracked=rt.run(['git','-C',str(R),'ls-files','-z']).decode().split('\0')
 untracked=rt.run(['git','-C',str(R),'ls-files','--others','--exclude-standard','-z']).decode().split('\0')
 checked=0;findings=[]
 for name in set(tracked+untracked):
  if not name:continue
  p=R/name
  if not p.is_file() or p.suffix.lower() in ['.png','.jpg','.ico','.woff','.woff2','.ttf','.pdf']:continue
  data=p.read_bytes();checked+=1
  if any(v.encode() in data for v in known):findings.append(name)
 assert not findings,'Known credential found in repository files: '+str(findings)
 logs=a.entries(a.query(env,'{environment="'+env+'"}'))
 assert logs and not any(s in v[1] for labels,v in logs for s in known)
 assert not any('never-log-this-query' in v[1] for labels,v in logs)
 # Actual loaded Loki config + compactor metrics, no private HTTP exposure.
 port=21300 if env=='qa' else 3000
 root=f'http://127.0.0.1:{port}/api/datasources/proxy/uid/greenshop-loki'
 r=requests.get(root+'/config',auth=('admin',pw['grafana']),timeout=20);r.raise_for_status();cfg=yaml.safe_load(r.text)
 assert cfg['limits_config']['retention_period']=='3d' or cfg['limits_config']['retention_period']=='72h'
 assert cfg['compactor']['retention_enabled'] and cfg['compactor']['delete_request_store']=='filesystem'
 cid=rt.container(env,'loki');metrics=rt.run(['docker','exec',cid,'/bin/busybox','wget','-qO-','http://127.0.0.1:3100/metrics']).decode()
 compactor=[l for l in metrics.splitlines() if not l.startswith('#') and ('retention' in l or 'compact_tables_operation_total' in l)][:40]
 assert compactor,'No compactor metrics observed'
 # All five M2 targets and original Prometheus dashboard expressions return data.
 prom=21990 if env=='qa' else 9090
 targets=requests.get(f'http://127.0.0.1:{prom}/api/v1/targets',timeout=20).json()['data']['activeTargets'];assert len(targets)==5 and all(x['health']=='up' for x in targets)
 panels=[]
 for f in (R/'monitoring/grafana/dashboards').glob('*.json'):
  if f.stem=='greenshop-logs':continue
  for panel in json.loads(f.read_text())['panels']:
   for t in panel.get('targets',[]):
    expr=t['expr'].replace('$project',rt.project(env));d=requests.get(f'http://127.0.0.1:{prom}/api/v1/query',params={'query':expr},timeout=20).json();assert d['data']['result'],panel['title'];panels.append(panel['title'])
 assert requests.get(f'http://127.0.0.1:{port}/api/search',timeout=10).status_code==401
 assert requests.get(f'http://127.0.0.1:{port}/api/user',auth=('admin','admin'),timeout=10).status_code==401
 a.record(env+'-security-audit',{'status':'PASS','time':a.now(),'repository_text_files_scanned':checked,'runtime_known_secrets_scanned':len(known),'source_secret_findings':findings,'grafana_password_length':len(pw['grafana']),'grafana_password_strength_control':(json.loads((a.E/'grafana-password-audit.json').read_text()).get('decision','NOT AUDITED') if env=='main' and (a.E/'grafana-password-audit.json').exists() else 'Not certified from length alone; private credential and access isolation audited separately'),'safe_loki_entries_scanned':len(logs),'query_canary_not_disclosed':True,'grafana_anonymous_and_default_password_denied':True,'targets':[{'job':x['labels']['job'],'health':x['health']} for x in targets],'m2_panels_with_real_series':len(panels),'loaded_retention':cfg['limits_config']['retention_period'],'compactor_enabled':True,'compactor_metrics':compactor,'limits':['Known-secret/text audit is not a comprehensive image CVE audit.','72-hour age deletion not elapsed in this acceptance session; loaded config and running compactor verified.','Plaintext strength of existing Customer/Admin passwords cannot be inferred from hashes.']})
 print('PASS known-secret scan, M2 five targets/all panels, Grafana access restrictions and loaded retention:',env,flush=True)
if __name__=='__main__':audit(__import__('sys').argv[1])
