"""Capture real QA diagnostic Explore and a fully rendered diagnostic panel."""

if __name__ == "__main__":
 raise SystemExit("Retired QA/recovery harness. Use GreenShop-Official: docker compose up -d --build")
import importlib.util,json,os,urllib.parse
from pathlib import Path
from playwright.sync_api import sync_playwright
R=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('a',R/'tests/logging/acceptance.py')
a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
qa=json.loads((a.E/'diagnostic-runtime-qa.json').read_text())
expr='{environment="qa",service="greenshop-web"} | json | schema_version="2" | diagnostic_code="db.connection.failed" | __error__=""'
rows=a.entries(a.query('qa',expr,start=qa['start_epoch']));assert rows
with sync_playwright() as p:
 browser=p.chromium.launch(executable_path=os.environ['CHROMIUM_EXECUTABLE'])
 context=browser.new_context(ignore_https_errors=True,viewport={'width':1680,'height':1150})
 page=context.new_page();url='http://localhost:21300'
 page.goto(url+'/login')
 page.locator('input[name="user"]').fill('admin')
 page.locator('input[name="password"]').fill(json.loads((a.P/'qa/passwords.json').read_text())['grafana'])
 page.get_by_role('button',name='Log in',exact=True).click()
 page.wait_for_url(lambda u:'/login' not in u,timeout=30000)
 panes={'A':{'datasource':'greenshop-loki','queries':[{'refId':'A','expr':expr,'queryType':'range','datasource':{'type':'loki','uid':'greenshop-loki'},'editorMode':'code'}],'range':{'from':str(int(qa['start_epoch']*1000)),'to':'now'}}}
 page.goto(url+'/explore?schemaVersion=1&orgId=1&panes='+urllib.parse.quote(json.dumps(panes)))
 page.wait_for_function("document.body.innerText.includes('Database connection failed.') && document.body.innerText.includes('trace_id')",timeout=90000)
 assert 'Error when running' not in page.locator('body').inner_text()
 page.screenshot(path=str(a.E/'qa-diagnostic-explore.png'),full_page=True)
 page.goto(url+'/d/greenshop-logs?var-environment=qa&from='+str(int(qa['start_epoch']*1000))+'&to=now')
 heading=page.get_by_text('Safe database and request diagnostics',exact=True)
 heading.wait_for(timeout=60000)
 page.wait_for_timeout(5000)
 page.screenshot(path=str(a.E/'qa-diagnostic-dashboard.png'),full_page=True)
 heading.evaluate("e=>e.scrollIntoView({block:'start'})")
 panel=page.get_by_test_id('logs-panel-6')
 if panel.count()!=1:
  print('Panel ancestry metadata:',heading.evaluate("e=>{const a=[];for(let p=e;p&&a.length<8;p=p.parentElement)a.push({tag:p.tagName,id:p.id,testid:p.getAttribute('data-testid'),role:p.getAttribute('role')});return a;}"),flush=True)
 assert panel.count()==1
 panel.get_by_text('Database connection failed.',exact=False).first.wait_for(timeout=90000)
 assert 'db.connection.failed' in panel.inner_text() and 'trace_id' in panel.inner_text()
 page.screenshot(path=str(a.E/'qa-diagnostic-panel.png'),full_page=True)
 browser.close()
a.record('diagnostic-browser',{'status':'PASS','observed_utc':a.now(),'method':'Real Chromium login; actual Explore message/trace_id; specifically wait for diagnostic message/code/trace_id inside panel6 container after scrolling.','expression':expr,'start_epoch':qa['start_epoch'],'entries':len(rows),'screenshots':['qa-diagnostic-explore.png','qa-diagnostic-dashboard.png','qa-diagnostic-panel.png'],'credential_form_captured':False})
print('PASS rendered diagnostic Explore and panel6 message/code/trace_id',flush=True)
