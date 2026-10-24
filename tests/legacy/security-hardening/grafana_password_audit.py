"""Read-only Grafana threat-model audit. Never outputs passwords or their hashes."""

if __name__ == "__main__":
 raise SystemExit("Retired QA/recovery harness. Use GreenShop-Official: docker compose up -d --build")
import datetime,hmac,importlib.util,ipaddress,json,os,re,stat,subprocess
from pathlib import Path
import requests
R=Path('/home/trung/GreenShop-Official')
sp=importlib.util.spec_from_file_location('a',R/'tests/logging/acceptance.py');a=importlib.util.module_from_spec(sp);sp.loader.exec_module(a)
P=a.P
def mode(p):
 s=p.stat();return {'mode':oct(stat.S_IMODE(s.st_mode)),'uid':s.st_uid,'gid':s.st_gid,'group_write':bool(s.st_mode&stat.S_IWGRP),'other_write':bool(s.st_mode&stat.S_IWOTH),'other_execute':bool(s.st_mode&stat.S_IXOTH)}
pw=json.loads((P/'main/passwords.json').read_text())
secret=pw['grafana'];d=a.rt.info(a.rt.container('main','grafana'))
env=dict(v.split('=',1) for v in d['Config']['Env'])
root='http://127.0.0.1:3000'
session=requests.Session();session.auth=('admin',secret)
r=session.get(root+'/api/admin/settings',timeout=30);r.raise_for_status();settings=r.json()
auth=settings.get('auth.anonymous',{});security=settings.get('security',{})
known_defaults={'admin','admin123','password','password123','123456','1234567890','changeme','letmein','grafana'}
low=secret.casefold()
guessable=any(w in low for w in ['password','qwerty','letmein','greenshop','grafana','123456','abcdef']) or len(set(low))<4 or bool(re.fullmatch(r'(.{1,3})\1{2,}',low))
others={}
for k,v in pw.items():
 if k!='grafana':others['main_'+k]=v
qp=json.loads((P/'qa/passwords.json').read_text())
others.update({'qa_'+k:v for k,v in qp.items()})
for envname in ['main','qa']:
 db=a.rt.info(a.rt.container(envname,'db'));de=dict(v.split('=',1) for v in db['Config']['Env'])
 for k in ['MYSQL_ROOT_PASSWORD','MYSQL_PASSWORD']:
  if de.get(k):others[envname+'_'+k]=de[k]
 accounts=P/envname/'accounts.json'
 if accounts.exists():
  for k,v in json.loads(accounts.read_text()).items():
   if isinstance(v,list) and len(v)>1 and isinstance(v[1],str):others[envname+'_fixture_'+str(k)]=v[1]
reused=[k for k,v in others.items() if hmac.compare_digest(secret,v)]
ports=[p for values in (d['NetworkSettings']['Ports'] or {}).values() for p in (values or [])]
loopback=bool(ports) and all(ipaddress.ip_address(p['HostIp']).is_loopback for p in ports)
anonymous=session.get(root+'/api/user',auth=('', ''),timeout=20).status_code
anon=requests.get(root+'/api/search',timeout=20).status_code
default=requests.get(root+'/api/user',auth=('admin','admin'),timeout=20).status_code
valid=session.get(root+'/api/user',timeout=20);valid.raise_for_status()
mount=next(x for x in d['Mounts'] if x['Destination']=='/run/secrets/grafana_password')
f=Path(mount['Source']);ancestry=[{'path':str(p),'permissions':mode(p)} for p in [P,P/'main',f.parent,f]]
secret_matches=hmac.compare_digest(f.read_text().strip(),secret)
leaks=[];text_count=0
files=set(a.rt.run(['git','-C',str(R),'ls-files','-z']).decode().split('\0')+a.rt.run(['git','-C',str(R),'ls-files','--others','--exclude-standard','-z']).decode().split('\0'))
for name in sorted(files):
 if not name:continue
 p=R/name
 if not p.is_file() or p.suffix.lower() in ['.png','.jpg','.jpeg','.ico','.pdf','.ttf','.woff','.woff2']:continue
 text_count+=1
 if secret.encode() in p.read_bytes():leaks.append(name)
central=a.entries(a.query('main','{environment="main"}'));central_leak=any(secret in value[1] for labels,value in central)
# Inspect actual Grafana stdout/stderr only in memory; do not export raw logs.
raw=subprocess.run(['docker','logs','--since','24h',d['Id']],capture_output=True)
runtime_leak=secret.encode() in raw.stdout or secret.encode() in raw.stderr
actual_secret_path_readonly=not mount['RW']
checks={'authenticated_api_works':valid.status_code==200,'nondefault_password':low not in known_defaults and default==401,'no_reuse_in_inspected_deployment_and_fixture_secrets':not reused,'no_common_guessable_pattern':not guessable,'source_evidence_no_plaintext_match':not leaks,'grafana_runtime_logs_no_plaintext_match':not runtime_leak,'centralized_logs_no_plaintext_match':not central_leak,'loopback_published_ports_only':loopback,'anonymous_api_denied':anon==401,'anonymous_config_disabled':str(auth.get('enabled','')).lower()=='false','secret_file_matches_private_state':secret_matches,'secret_mount_readonly':actual_secret_path_readonly,'private_parent_is_0700':all(stat.S_IMODE(p.stat().st_mode)==0o700 for p in [P,P/'main',f.parent]),'secret_not_group_or_other_writable':not (f.stat().st_mode & (stat.S_IWGRP|stat.S_IWOTH)),'brute_force_protection_enabled':str(security.get('disable_brute_force_login_protection','false')).lower()=='false'}
mysql_root_login_verified=a.m.sql(a.rt.container('main','db'),'SELECT 1')=='1'
data={'mysql_root_readonly_login_verified':mysql_root_login_verified,'status':'PASS' if all(checks.values()) else 'PARTIAL','observed_utc':a.now(),'scope':'Read-only main Grafana assessment; no password changes, no bulk login guesses, no service restart','password_length':len(secret),'checks':checks,'random_generation_provenance':'NOT VERIFIED: no auditable generator record for current operator-selected credential','entropy_estimate':'NOT INFERRED from length or character variety','reuse_role_matches':reused,'reuse_scope':'Only locally inspected Main/QA deployment credentials and QA fixture passwords; external reuse unknown','public_exposure_scope':'Docker host bind is loopback only; external SSH forwarding/proxies outside inspected configuration not independently ruled out','secret_metadata':ancestry,'grafana_ports':ports,'files_scanned':text_count,'source_plaintext_findings':leaks,'centralized_entries_scanned':len(central),'anonymous_api_status':anon,'default_password_status':default,'valid_password_api_status':valid.status_code,'limitations':['Heuristics can identify some easy patterns but cannot prove randomness or resistance to offline guessing.','No external breach database queried; no password/hash sent to any third party.','Historical screenshots are not OCR-scanned; newly generated audit evidence contains no password.'],'decision':('ROTATION_REQUIRED' if reused or guessable or not checks['nondefault_password'] else ('VERIFIED' if all(checks.values()) else 'BLOCKED')),'reference':'https://grafana.com/docs/grafana/latest/setup-grafana/configure-access/configure-authentication/grafana/'}
risk=json.loads((R/'docs/evidence/commit3/accepted-security-risk.json').read_text())
independent=[k for k,v in checks.items() if not v and k!='no_reuse_in_inspected_deployment_and_fixture_secrets']
accepted=(risk['finding']=='GRAFANA_MYSQL_ROOT_CREDENTIAL_REUSE' and risk['disposition']=='ACCEPTED_RISK' and risk['status']=='OPEN — RISK ACCEPTED')
if reused and accepted and not independent:
 data['decision']='ACCEPTED_RISK';data['accepted_risk']=risk;data['status']='PARTIAL'
data['independent_failed_checks']=independent
data['password_rotation_performed']=False
target=R/'docs/evidence/commit3/grafana-password-audit.json';target.write_text(json.dumps(data,indent=2)+'\n')
print(json.dumps({'status':data['status'],'checks':checks,'random_generation_provenance':data['random_generation_provenance'],'secret_disclosed':False},indent=2))
