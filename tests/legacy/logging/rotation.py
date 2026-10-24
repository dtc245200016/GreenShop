"""Bounded real Docker json-file rotation test on QA Nginx only."""

if __name__ == "__main__":
 raise SystemExit("Retired QA/recovery harness. Use GreenShop-Official: docker compose up -d --build")
import importlib.util,json,time
from pathlib import Path
import requests
R=Path(__file__).resolve().parents[2]
sp=importlib.util.spec_from_file_location('a',R/'tests/logging/acceptance.py');a=importlib.util.module_from_spec(sp);sp.loader.exec_module(a)
rt=a.rt;env='qa';f=a.P/env/'compose.json';original=json.loads(f.read_text())['services']['nginx']['logging']
def change(config):
 c=json.loads(f.read_text());c['services']['nginx']['logging']=config;rt.save(f,c)
 rt.dc(env,'up','-d','--no-deps','--wait','--wait-timeout','120','nginx');rt.refresh(env);rt.dc(env,'up','-d','--no-deps','--wait','--wait-timeout','120','promtail')
try:
 change({'driver':'json-file','options':{'max-size':'16k','max-file':'3'}})
 start=time.time();n=180
 for i in range(n):
  r=requests.get(a.base(env)+'/m3-rotation-check',verify=False,timeout=10);assert r.status_code==404;time.sleep(.04)
 end=time.time()
 expr='{environment="qa",service="nginx"} | json | status="404" | __error__=""'
 events=a.wait(lambda:(v if len(v:=a.entries(a.query(env,expr,start=start,end=end)))==n else None),50)
 cid=rt.container(env,'nginx');log=Path(rt.info(cid)['LogPath'])
 stats=rt.run(['docker','run','--rm','--network','none','-v',str(log.parent)+':/selected:ro','busybox:1.37.0-musl','sh','-c','ls /selected/*-json.log* | wc -l']).decode().strip();assert int(stats)>=2
 a.record('qa-log-rotation',{'status':'PASS','time':a.now(),'requests':n,'logql_entries':len(events),'start_epoch':start,'end_epoch':end,'rotated_files_observed':int(stats),'temporary_qa_logging':{'max-size':'16k','max-file':'3'},'restored_logging':original,'method':'Real HTTP requests, Docker size rotation, exact LogQL count in fixed time range; directory mounts + non-root watcher survive rotation.'})
 print('PASS actual QA Docker rotation; all',n,'404 responses ingested once',flush=True)
finally:change(original)
