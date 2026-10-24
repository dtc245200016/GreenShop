"""Historical one-shot rollout. Main now uses logging-runtime.py."""

if __name__ == "__main__":
 raise SystemExit("Retired QA/recovery harness. Use GreenShop-Official: docker compose up -d --build")
if __name__ == "__main__":
 raise SystemExit("Retired: use logging-runtime.py plan/status/update main; obtain approval before changing Main.")

def historical_additive_rollout():
 raise RuntimeError("Historical Main rollout retired; use logging-runtime.py after separate approval")
 import importlib.util,json
 from pathlib import Path
 R=Path('/home/trung/GreenShop-Official')
 sp=importlib.util.spec_from_file_location('rt',R/'scripts/logging-runtime.py');rt=importlib.util.module_from_spec(sp);sp.loader.exec_module(rt)
 env='main';b=rt.P/'m3'/env
 assert json.loads((b/'core-before.json').read_text())['web_app']['Id']==rt.info(rt.container(env,'web_app'))['Id'],'One-shot additive rollout must precede core rollout'
 for name in ['qa-acceptance','backup-restore','main-state-backup']:
  assert json.loads((rt.E/(name+'.json')).read_text())['status']=='PASS',name
 old=json.loads((rt.P/env/'compose.json').read_text());new=json.loads((b/'proposed-plan.json').read_text())
 for s in ['loki','promtail']:old['services'][s]=new['services'][s]
 old['services']['grafana']['networks']['logging_net']=None
 old['services']['grafana']['mem_limit']=536870912;old['services']['grafana']['memswap_limit']=805306368
 old['networks']['logging_net']=new['networks']['logging_net']
 for v in ['loki_data','promtail_positions']:old['volumes'][v]=new['volumes'][v]
 rt.save(rt.P/env/'compose.json',old);rt.logging(env)
 print('PASS additive Main logging rollout; original web/DB/phpMyAdmin still running.',flush=True)
