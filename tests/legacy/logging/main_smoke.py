
if __name__ == "__main__":
 raise SystemExit("Retired QA/recovery harness. Use GreenShop-Official: docker compose up -d --build")
import importlib.util,json,ssl,socket
from pathlib import Path
import requests
R=Path(__file__).resolve().parents[2]
sp=importlib.util.spec_from_file_location('a',R/'tests/logging/acceptance.py');a=importlib.util.module_from_spec(sp);sp.loader.exec_module(a)
pw=json.loads((a.P/'main/passwords.json').read_text());checks=[]
for url,code in [('https://localhost/',200),('https://localhost/health/ready',200),('https://localhost/SanPham/CuaHang',200),('https://localhost/Account/Login',200),('https://localhost/Admin/Account/Login',200),('http://127.0.0.1:8080/',200),('http://127.0.0.1:5000/metrics',404)]:
 r=requests.get(url,verify=False,timeout=20);assert r.status_code==code,url;checks.append({'url':url,'status':r.status_code})
for path in ['/metrics','/metrics/','/nginx_status']:
 r=requests.get('https://localhost'+path,verify=False,headers={'Authorization':'Bearer '+pw['metrics']},timeout=15);assert r.status_code==404
tls=[]
for version in [ssl.TLSVersion.TLSv1_2,ssl.TLSVersion.TLSv1_3]:
 c=ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT);c.check_hostname=False;c.verify_mode=ssl.CERT_NONE;c.minimum_version=version;c.maximum_version=version
 with socket.create_connection(('127.0.0.1',443),timeout=10) as raw:
  with c.wrap_socket(raw,server_hostname='localhost') as s:tls.append(s.version())
mysql=a.m.sql('greenshop_db','SELECT @@general_log,@@log_error_verbosity;')
assert mysql.startswith('0\t')
for env in ['qa','main']:
 cid=a.rt.container(env,'promtail')
 a.rt.run(['docker','exec',cid,'bash','-ec','for p in /logs/*/config.v2.json; do test ! -r "$p"; done'])
ids={s:a.rt.container('main',s) for s in ['db','phpmyadmin','web_app','nginx','grafana','prometheus','loki','promtail']}
a.record('main-smoke',{'status':'PASS','time':a.now(),'http_checks':checks,'valid_bearer_public_telemetry_denied':True,'tls_protocols':tls,'mysql_general_query_log_disabled':True,'mysql_error_verbosity':int(mysql.split('\t')[1]),'collector_cannot_read_container_environment_config':True,'container_ids':ids,'main_authenticated_workflows':'NOT TESTED; no Main customer/admin fixture or credential changes','migrations_added':False})
print('PASS Main HTTPS/phpMyAdmin/TLS 1.2+1.3/telemetry denial/general-log OFF and collector secret isolation',flush=True)
