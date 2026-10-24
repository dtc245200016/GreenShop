"""Separate the course rubric from exhaustive production hardening."""

if __name__ == "__main__":
 raise SystemExit("Retired QA/recovery harness. Use GreenShop-Official: docker compose up -d --build")
import importlib.util,json,re
from pathlib import Path
R=Path(__file__).resolve().parents[2];E=R/'docs/evidence/commit3'
s=importlib.util.spec_from_file_location('a',R/'tests/logging/acceptance.py');a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
def read(n):return json.loads((E/(n+'.json')).read_text())
hard={env:read(env+'-hardening') for env in ['qa','main']};controls=[]
def add(id,name,passed,evidence,limits):controls.append({'id':id,'measure':name,'status':'PASS' if passed else 'FAIL','evidence':evidence,'scope_and_limits':limits})
services={env:{r['service']:r for r in h['services']} for env,h in hard.items()}
def uid(env,s):return int(services[env][s]['pid1_status']['Uid'].split()[0])
add('R6-01','Meaningful services run non-root',all(uid(env,'web_app')==1654 and uid(env,'loki')==10001 and uid(env,'promtail')==10001 for env in hard),['qa-hardening.json','main-hardening.json','qa-upload-session.json'],'Web upload/session compatibility tested; not a claim every container/master is non-root.')
add('R6-02','Network segmentation with positive and negative connectivity',all(all(h['network_probes'].values()) for h in hard.values()),['qa-hardening.json','main-hardening.json'],'Web→DB allowed; Nginx/Promtail denied both DB IPs; operator loopback ports retained.')
headers=all(all(r['headers'].get('X-Frame-Options')=='SAMEORIGIN' and r['headers'].get('X-Content-Type-Options')=='nosniff' and r['headers'].get('Referrer-Policy')=='strict-origin-when-cross-origin' for r in h['headers']) for h in hard.values())
add('R6-03','Effective security headers and HTTPS',headers and read('main-smoke')['status']=='PASS',['qa-hardening.json','main-hardening.json','main-smoke.json'],'Real responses and TLS1.2/1.3; no incompatible CSP or stronger new HSTS imposed on self-signed lab.')
least=all(services[env][s]['caps_drop']==['ALL'] and services[env][s]['pid1_status']['CapEff']=='0000000000000000' and services[env][s]['pid1_status']['NoNewPrivs']=='1' for env in hard for s in ['web_app','loki','promtail'])
add('R6-04','Linux privileges restricted on app and logging services',least,['qa-hardening.json','main-hardening.json'],'cap_drop ALL + no-new-privileges; collector no Docker socket; legacy root masters retain their required privileges.')
grants={}
for env in hard:
 db=a.rt.container(env,'db');schema='greenshop_m2_qa' if env=='qa' else 'greenshop'
 app=a.m.sql(db,"SHOW GRANTS FOR 'greenshop_app'@'%'",db=schema)
 exporter=a.m.sql(db,"SHOW GRANTS FOR 'greenshop_exporter'@'%'",db=schema)
 assert 'IDENTIFIED' not in app+exporter
 lines=[re.sub(r'\\+_','_',line) for line in app.splitlines()]
 scoped=all(line.startswith('GRANT USAGE ON *.*') or f' ON `{schema}`.* TO ' in line for line in lines) and all('WITH GRANT OPTION' not in line for line in lines)
 grants[env]={'app_grants_raw_batch_serialization':app.splitlines(),'app_grants':lines,'exporter_grants':exporter.splitlines(),'application_schema_scoped':scoped,'exporter_business_denials':hard[env]['exporter_denials']}
db_pass=all(g['application_schema_scoped'] and 'PROCESS ON *.*' in '\n'.join(g['exporter_grants']) and all(g['exporter_business_denials'].values()) for g in grants.values())
add('R6-05','Database rights restricted to each role',db_pass,['rubric-acceptance.json','qa-hardening.json','main-hardening.json'],'Application schema DDL retained for EF migrations; exporter PROCESS-only cannot read/write application tables; not a claim DML-only runtime identity.')
add('R6-06','Telemetry access and secrets isolated',all(read(env+'-security-audit')['grafana_anonymous_and_default_password_denied'] and not read(env+'-security-audit')['source_secret_findings'] for env in hard),['qa-security-audit.json','main-security-audit.json','main-smoke.json'],'Metrics token enforced, public metrics denied, Loki unpublished, read-only per-service secrets; password non-reuse assessed separately and not counted as PASS.')
count=sum(c['status']=='PASS' for c in controls)
out={'status':'PASS' if count>=4 else 'FAIL','observed_utc':a.now(),'rubric_source':'User-provided course requirement on 2026-10-17: at least 3–4 effective measures; examples include non-root, isolation, strong passwords, headers and DB restrictions. Earlier supplied assignment summary lists system hardening. No standalone lecturer PDF found in this repository.','required_measure_count':4,'verified_measure_count':count,'controls':controls,'db_grants':grants,'REQUIREMENT_6_RUBRIC':'PASS' if count>=4 else 'FAIL','SECURITY_HARDENING_OVERALL':'PARTIAL','password_measure_counted':False,'test_criteria_changed':False,'residual_risks_not_automatically_rubric_blockers':['Image-compatible root master/entrypoint processes; cAdvisor host trust.','Schema-scoped application DDL pending a complete EF migration alternative.','72h physical expiry not elapsed; compactor operation verified.','DB/phpMyAdmin Main rotation configured but not runtime applied; no unauthorized recreate.'],'separate_security_finding':'GRAFANA_MYSQL_ROOT_CREDENTIAL_REUSE: OPEN — RISK ACCEPTED. Explicit operator acceptance scoped to local academic VMware; reassess before public/production or more operators. Finding remains open; never counted as a passed password control.'}
a.record('rubric-acceptance',out)
print('REQUIREMENT_6_RUBRIC:',out['REQUIREMENT_6_RUBRIC'],';',count,'verified measures; SECURITY_HARDENING_OVERALL: PARTIAL',flush=True)
