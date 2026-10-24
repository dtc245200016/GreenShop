"""A second real QA incident cycle for time-accurate UI screenshots."""

if __name__ == "__main__":
 raise SystemExit("Retired QA/recovery harness. Use GreenShop-Official: docker compose up -d --build")
import importlib.util,json,os,secrets,time,urllib.parse
from pathlib import Path
from playwright.sync_api import sync_playwright
import requests
R=Path(__file__).resolve().parents[2]
sp=importlib.util.spec_from_file_location('a',R/'tests/logging/acceptance.py');a=importlib.util.module_from_spec(sp);sp.loader.exec_module(a)
m=a.m;E=a.E;url='http://localhost:21300';acc=json.loads((a.P/'qa/accounts.json').read_text());pw=json.loads((a.P/'qa/passwords.json').read_text())['grafana']
a.wait(lambda:m.scalar('greenshop_auth_login_failures_last_60s')==0 and m.alert_state()['state']=='inactive')
with sync_playwright() as p:
 b=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_EXECUTABLE'));c=b.new_context(viewport={'width':1600,'height':1100});page=c.new_page()
 page.goto(url+'/login');page.locator('input[name=user]').fill('admin');page.locator('input[name=password]').fill(pw);page.get_by_role('button',name='Log in',exact=True).click();page.wait_for_url(lambda u:'/login' not in u)
 page.goto(url+'/alerting/grafana/gs-sec-001/view');page.get_by_text('Normal',exact=True).first.wait_for(timeout=60000);page.screenshot(path=str(E/'qa-incident-before.png'),full_page=True)
 start=time.time();start_utc=a.now();before=m.scalar('greenshop_auth_login_failures_total');session=requests.Session()
 for i in range(4):assert m.login(session,acc['customer'][0],secrets.token_urlsafe(24)).status_code==200
 a.wait(lambda:m.scalar('greenshop_auth_login_failures_last_60s')==4,25);time.sleep(12);assert m.alert_state()['state']=='inactive'
 assert m.login(session,acc['customer'][0],secrets.token_urlsafe(24)).status_code==200;assert time.time()-start<60
 a.wait(lambda:m.alert_state()['state']=='firing',35);a.wait(lambda:[x for x in m.incidents('firing') if x['received_at']>=start_utc],25)
 page.reload();page.get_by_text('Firing',exact=True).first.wait_for(timeout=30000);page.screenshot(path=str(E/'qa-incident-firing.png'),full_page=True)
 expr='{environment="qa",service="greenshop-web"} | json | incident="GS-SEC-001" | __error__=""'
 events=a.wait(lambda:(v if len(v:=a.entries(a.query('qa',expr,start=start-1)))==5 else None),25)
 pane={'A':{'datasource':'greenshop-loki','queries':[{'refId':'A','expr':expr,'queryType':'range','editorMode':'code'}],'range':{'from':str(int((start-1)*1000)),'to':str(int(time.time()*1000))}}}
 page.goto(url+'/explore?schemaVersion=1&orgId=1&panes='+urllib.parse.quote(json.dumps(pane)))
 page.wait_for_function("document.body.innerText.includes('invalid_credentials')",timeout=90000);page.screenshot(path=str(E/'qa-incident-loki.png'),full_page=True)
 a.wait(lambda:m.alert_state()['state']=='inactive',100);resolved=a.wait(lambda:[x for x in m.incidents('resolved') if x['received_at']>=start_utc],35)
 page.goto(url+'/alerting/grafana/gs-sec-001/view');page.get_by_text('Normal',exact=True).first.wait_for(timeout=45000);page.screenshot(path=str(E/'qa-incident-resolved.png'),full_page=True)
 receiver=a.rt.info(a.rt.container('qa','qa-alert-receiver'));ip=next(iter(receiver['NetworkSettings']['Networks'].values()))['IPAddress'];page.goto('http://'+ip+':8080/notifications');page.screenshot(path=str(E/'qa-incident-notifications.png'),full_page=True)
 b.close()
a.record('gs-sec-001-ui-cycle',{'status':'PASS','start_utc':start_utc,'resolved_observed_utc':a.now(),'real_failed_logins':5,'logql_entries':len(events),'counter_before':before,'counter_after':m.scalar('greenshop_auth_login_failures_total'),'request_ids':[json.loads(v[1])['request_id'] for x,v in events],'resolved_notification':resolved[-1],'screenshots':['qa-incident-before.png','qa-incident-firing.png','qa-incident-loki.png','qa-incident-resolved.png','qa-incident-notifications.png'],'note':'Second independent real QA cycle; first API acceptance retained separately. No Main invalid login attempts.'})
print('PASS second QA incident: genuine Normal/Firing/Loki/Resolved/notification screenshots',flush=True)
