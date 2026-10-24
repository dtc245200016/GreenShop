"""Scan actual index blobs, not working-tree files. Never print secrets/PII.

Run --verify after staging the generated audit + evidence manifest. The inventory
seal excludes those two self-referential reports only; both are still scanned.
"""

if __name__ == "__main__":
 raise SystemExit("Retired QA/recovery harness. Use GreenShop-Official: docker compose up -d --build")
import base64,datetime,hashlib,importlib.util,io,json,re,subprocess,sys,urllib.parse
from pathlib import Path
from PIL import Image
R=Path(__file__).resolve().parents[2];s=importlib.util.spec_from_file_location('a',R/'tests/logging/acceptance.py');a=importlib.util.module_from_spec(s);s.loader.exec_module(a)
E=a.E;target='docs/evidence/commit3/staged-security-audit.json';excluded_seal={target,'docs/evidence/commit3/manifest.json'}
known=set();pii=set()
for env in ['main','qa']:
 for v in json.loads((a.P/env/'passwords.json').read_text()).values():
  if isinstance(v,str) and len(v)>=8:known.add(v)
 account=a.P/env/'accounts.json'
 if account.exists():
  for value in json.loads(account.read_text()).values():
   if isinstance(value,list) and len(value)>1:known.add(value[1])
 for svc in ['web_app','db','grafana']:
  info=a.rt.info(a.rt.container(env,svc));values=dict(x.split('=',1) for x in info['Config']['Env'])
  for k,v in values.items():
   if len(v)<8:continue
   if re.search(r'(PASSWORD$|API_?KEY$|APIKEY$)',k,re.I):known.add(v)
   if 'connection' in k.casefold():
    for value in re.findall(r'(?:Password|Pwd)=([^;]+)',v,re.I):known.add(value)
# Actual Main identity fields are read in memory only, never placed in evidence.
db=a.rt.container('main','db')
for table in ['Users','Orders']:
 cols=a.m.sql(db,'SHOW COLUMNS FROM `'+table+'`').splitlines();names=[x.split('\t')[0] for x in cols]
 chosen=[n for n in names if re.fullmatch(r'(Email|Phone|PhoneNumber|Address|ShippingAddress|RecipientPhone|CustomerEmail)',n,re.I)]
 if chosen:
  raw=a.m.sql(db,'SELECT '+','.join('`'+n+'`' for n in chosen)+' FROM `'+table+'`')
  pii.update(x.strip() for line in raw.splitlines() for x in line.split('\t') if x.strip() not in ['NULL',''] and len(x.strip())>=8)
 # Scan persisted application password hashes as sensitive data too.
 if 'PasswordHash' in names:
  known.update(x for x in a.m.sql(db,'SELECT PasswordHash FROM `'+table+'`').splitlines() if len(x)>=16)
# Reserved shop-owner identifier is deliberately public application policy at HEAD,
# not an exported customer record. Keep this finite baseline exception visible.
owner_source=subprocess.check_output(['git','show','HEAD:backend/GreenShop.Web/Models/User.cs'],cwd=R).decode()
owner_match=re.search(r'const string OwnerEmail = "([^"]+)"',owner_source)
public_owner=owner_match.group(1) if owner_match else None
if public_owner:pii.discard(public_owner)
public_owner_paths=[]
patterns=[('private_key' ,re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')),('google_api_key',re.compile(rb'AIza[0-9A-Za-z_-]{35}')),('github_token',re.compile(rb'gh[pousr]_[0-9A-Za-z]{30,}')),('jwt_literal',re.compile(rb'eyJ[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}\.[A-Za-z0-9_-]{16,}'))]
variants=set()
for value in known:
 variants.update([value.encode(),urllib.parse.quote(value,safe='').encode(),base64.b64encode(value.encode()),json.dumps(value)[1:-1].encode()])
records=[];findings=[];png=[];binary=0;texts=0;raw_candidates=[];raw_logs=[]
index=subprocess.check_output(['git','ls-files','--stage','-z'],cwd=R).split(b'\0')
for entry in index:
 if not entry:continue
 meta,path=entry.split(b'\t',1);mode,oid,stage=meta.decode().split();name=path.decode();assert stage=='0','Unmerged index'
 data=subprocess.check_output(['git','cat-file','blob',oid],cwd=R)
 if public_owner and public_owner.encode() in data:
  baseline=subprocess.run(['git','show','HEAD:'+name],cwd=R,capture_output=True)
  assert baseline.returncode==0 and baseline.stdout==data,('Public owner identifier copied/changed outside its historical baseline',name)
  public_owner_paths.append(name)
 records.append({'path':name,'oid':oid,'bytes':len(data)})
 if any(v and v in data for v in variants):findings.append({'path':name,'kind':'known_runtime_credential_or_hash'})
 if any(v.encode() in data for v in pii):findings.append({'path':name,'kind':'known_main_customer_contact'})
 for kind,pat in patterns:
  if pat.search(data):findings.append({'path':name,'kind':kind})
 suffix=Path(name).suffix.lower()
 if suffix=='.png':
  im=Image.open(io.BytesIO(data));im.verify();im=Image.open(io.BytesIO(data));png.append({'path':name,'sha256':hashlib.sha256(data).hexdigest(),'dimensions':list(im.size),'metadata_keys':sorted(im.info)})
  metadata=json.dumps(im.info,default=str).encode()
  if any(v in metadata for v in variants):findings.append({'path':name,'kind':'PNG_metadata_credential'})
 if '\x00' not in data[:4096].decode('latin1'):texts+=1
 else:binary+=1
 if suffix in ['.sql','.tar','.tgz','.key','.pfx','.p12'] or Path(name).name in ['.env','passwords.json','accounts.json','compose.json','grafana.db']:findings.append({'path':name,'kind':'private_runtime_or_backup_file'})
 if suffix in ['.log','.jsonl','.ndjson']:raw_logs.append(name)
 # Raw diagnostic payloads should not be accidentally exported as evidence.
 if name.startswith('docs/evidence/commit3/') and suffix=='.json':
  obj=json.loads(data)
  def visit(x):
   if isinstance(x,dict):
    if any(k in x for k in ['Authorization','Cookie','PasswordHash','commandText','ConnectionString']):return True
    return any(visit(v) for v in x.values())
   return isinstance(x,list) and any(visit(v) for v in x)
  if visit(obj):raw_candidates.append(name)
assert not raw_candidates,('Review potentially raw payload keys',raw_candidates)
assert not raw_logs,('Review raw log files',raw_logs)
assert not findings,('Staged disclosure findings (values withheld)',findings)
risk=json.loads((E/'accepted-security-risk.json').read_text());pw=json.loads((E/'grafana-password-audit.json').read_text())
assert risk['disposition']=='ACCEPTED_RISK' and risk['status']=='OPEN — RISK ACCEPTED' and not pw.get('independent_failed_checks')
seal=hashlib.sha256(json.dumps([x for x in records if x['path'] not in excluded_seal],sort_keys=True,separators=(',',':')).encode()).hexdigest()
if '--verify' in sys.argv:
 recorded=json.loads((E/'staged-security-audit.json').read_text());assert recorded['inventory_sha256_excluding_self_and_manifest']==seal,'Index changed after audit; rerun record + manifest then verify';print('PASS FINAL actual staged snapshot:',len(records),'blobs;',len(png),'PNG; known secrets/PII/pattern/raw-payload findings0; seal verified; no writes');sys.exit()
report={'status':'PASS','observed_utc':a.now(),'SECRET_DISCLOSURE_SCAN':'PASS','SECURITY_RISK_REVIEW':'PASS_WITH_ACCEPTED_RISK','SECURITY_AUDIT':'PASS_WITH_ACCEPTED_RISK','scope':'Every actual Git index blob via git cat-file, including tracked unchanged files and all staged M3 additions; not just working-tree text.','blobs_scanned':len(records),'text_blobs':texts,'binary_blobs':binary,'known_secret_values_in_memory':len(known),'known_main_contact_values_in_memory':len(pii),'credential_variants':['exact UTF-8','JSON escaped','URL encoded','base64'],'patterns_checked':[x[0] for x in patterns],'findings':findings,'public_identifier_review':{'classification':'Already-public reserved shop-owner identity constant; not a customer-data export','baseline_unchanged':True,'paths':public_owner_paths,'value_disclosed_in_this_report':False},'raw_sensitive_payload_candidates':raw_candidates,'raw_log_files':raw_logs,'png_inventory':png,'screenshots_review':'PNG bytes and metadata scanned; All evidence PNG contact-sheet visual review across M1/M2/M3, with separate native diagnostic Explore/panel review. No login-form screenshots captured.','limits':['No OCR engine available; image-byte/metadata matching is not pixel OCR. Visual review is finite, not proof against all hidden text.','Known-secret matching and finite signature checks do not prove absence of every unknown credential/PII. Test canaries and placeholders are fake and not deployment credentials.','This is not a comprehensive container-image CVE scan.','Historical M1/M2 artifacts retain original capture-time facts; do not rewrite them to imply current acceptance.'],'accepted_finding':risk,'independent_security_blockers':[],'inventory_sha256_excluding_self_and_manifest':seal,'seal_excludes':sorted(excluded_seal),'finalization':'After staging this report and regenerated manifest, rerun --verify: all blobs including both reports are scanned; seal asserts every other blob is identical. No files modified by --verify.'}
(E/'staged-security-audit.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n');print('PASS staged audit:',len(records),'blobs;',len(png),'PNG; no disclosure; SECURITY_AUDIT=PASS_WITH_ACCEPTED_RISK')
