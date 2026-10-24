"""Capture real Grafana Explore, datasource and dashboard after API checks.

No UI responses are mocked; screenshots never include login form credentials.
"""

if __name__ == "__main__":
 raise SystemExit("Retired QA/recovery harness. Use GreenShop-Official: docker compose up -d --build")
import importlib.util,json,os,sys,time,urllib.parse
from pathlib import Path
from playwright.sync_api import sync_playwright
R=Path(__file__).resolve().parents[2]
sp=importlib.util.spec_from_file_location('a',R/'tests/logging/acceptance.py');a=importlib.util.module_from_spec(sp);sp.loader.exec_module(a)
env=sys.argv[1];port=21300 if env=='qa' else 3000;url=f'http://localhost:{port}';E=a.E
pwd=json.loads((a.P/env/'passwords.json').read_text())['grafana']
with sync_playwright() as p:
 b=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_EXECUTABLE'));ctx=b.new_context(ignore_https_errors=True,viewport={'width':1600,'height':1200});page=ctx.new_page()
 page.goto(url+'/login');page.locator('input[name="user"]').fill('admin');page.locator('input[name="password"]').fill(pwd);page.get_by_role('button',name='Log in',exact=True).click();page.wait_for_url(lambda u:'/login' not in u,timeout=30000)
 for name,expr in [('application',f'{{environment="{env}",service="greenshop-web"}}'),('nginx',f'{{environment="{env}",service="nginx"}} | json | status >= 400 | __error__=""'),('mysql',f'{{environment="{env}",service="mysql"}}')]:
  assert a.entries(a.query(env,expr))
  panes={'A':{'datasource':'greenshop-loki','queries':[{'refId':'A','expr':expr,'queryType':'range','datasource':{'type':'loki','uid':'greenshop-loki'},'editorMode':'code'}],'range':{'from':'now-24h','to':'now'}}}
  page.goto(url+'/explore?schemaVersion=1&orgId=1&panes='+urllib.parse.quote(json.dumps(panes)))
  page.wait_for_function("document.body.innerText.includes('timestamp_utc') || document.body.innerText.includes('mysql_operational')",timeout=90000)
  body=page.locator('body').inner_text()
  if not ('timestamp_utc' in body or 'mysql_operational' in body):
   page.screenshot(path='/tmp/greenshop-m3-browser-debug.png',full_page=True);print('Explore URL:',page.url.split('?')[0],'body length',len(body),flush=True)
  assert 'No logs found' not in body and 'Error when running' not in body,body[-500:]
  # Ensure rendered log text (not only a query in the editor) is present.
  assert 'timestamp_utc' in body or 'mysql_operational' in body,body[-1000:]
  page.screenshot(path=str(E/(env+'-explore-'+name+'.png')),full_page=True)
 page.goto(url+'/connections/datasources/edit/greenshop-loki');page.wait_for_timeout(3000)
 # v13 uses UID in the datasource edit route.
 btn=page.get_by_role('button',name='Save & test',exact=False)
 if btn.count():btn.click();page.get_by_text('Data source successfully connected.',exact=False).wait_for(timeout=30000)
 page.screenshot(path=str(E/(env+'-loki-datasource.png')),full_page=True)
 page.goto(url+'/d/greenshop-logs?var-environment='+env+'&from=now-24h&to=now');page.get_by_text('Recent application events',exact=True).wait_for(timeout=30000);page.wait_for_timeout(7000)
 assert 'mysql_operational' in page.locator('body').inner_text()
 page.screenshot(path=str(E/(env+'-logs-dashboard.png')),full_page=True)
 b.close()
a.record(env+'-browser',{'status':'PASS','time':a.now(),'method':'Actual Chromium login; three Explore queries verified nonempty via API and rendered body; datasource and provisioned logs dashboard screenshots','screenshots':[env+'-explore-'+n+'.png' for n in ['application','nginx','mysql']]+[env+'-loki-datasource.png',env+'-logs-dashboard.png']})
print('PASS real Grafana Explore and Logs dashboard screenshots:',env,flush=True)
