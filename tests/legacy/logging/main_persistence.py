"""Main logging-only restart smoke. No Main application/DB fault injection."""

if __name__ == "__main__":
 raise SystemExit("Retired QA/recovery harness. Use GreenShop-Official: docker compose up -d --build")
import importlib.util,time
from pathlib import Path
import requests
R=Path(__file__).resolve().parents[2]
sp=importlib.util.spec_from_file_location('a',R/'tests/logging/acceptance.py');a=importlib.util.module_from_spec(sp);sp.loader.exec_module(a)
end=time.time();expr='{environment="main",service="mysql"}';start=end-24*3600
before=a.entries(a.query('main',expr,start=start,end=end));assert before
for s in ['promtail','loki']:
 a.rt.dc('main','restart',s);a.wait(lambda:a.rt.info(a.rt.container('main',s))['State']['Health']['Status']=='healthy',120)
 assert requests.get(a.base('main')+'/health/ready',verify=False,timeout=15).status_code==200
assert a.entries(a.query('main',expr,start=start,end=end))==before
a.record('main-persistence',{'status':'PASS','time':a.now(),'method':'Restart Main Promtail then Loki only; fixed-range real MySQL log entries identical; website readiness 200 after each restart','entries_before':len(before),'entries_after':len(a.entries(a.query('main',expr,start=start,end=end))),'start_epoch':start,'end_epoch':end,'scope':'No Main DB/app stopped, no customer/admin mutations; logging restarts only.'})
print('PASS Main logging restart persistence; website remains ready',flush=True)
