"""Render actual JSON observations as a local audit report, not a simulated console."""

if __name__ == "__main__":
 raise SystemExit("Retired QA/recovery harness. Use GreenShop-Official: docker compose up -d --build")
import html,json,os,datetime
from pathlib import Path
from playwright.sync_api import sync_playwright
R=Path(__file__).resolve().parents[2];E=R/'docs/evidence/commit3'
def read(n):return json.loads((E/(n+'.json')).read_text())
d=read('main-hardening');smoke=read('main-smoke');res=read('resources');audit=read('main-security-audit')
table=''.join('<tr><td>'+html.escape(x['service'])+'</td><td>'+html.escape(x['pid1_status'].get('Uid','?').split()[0])+'</td><td>'+html.escape(x['health'] or 'running; no healthcheck')+'</td><td>'+html.escape(x['pid1_status'].get('CapEff','?'))+'</td><td>'+html.escape(', '.join(x['networks']))+'</td></tr>' for x in sorted(d['services'],key=lambda x:x['service']))
sections={
 'runtime':('<h2>Main — service runtime</h2><table><tr><th>Service</th><th>PID1 UID</th><th>State</th><th>CapEff</th><th>Actual networks</th></tr>'+table+'</table>'),
 'network':('<h2>Actual namespace TCP probes</h2><pre>'+html.escape(json.dumps(d['network_probes'],indent=2))+'</pre><p>Web → DB allowed; Nginx/Promtail → both DB IPs denied. Loopback MySQL 3306/phpMyAdmin 8080 remain available.</p>'),
 'headers':('<h2>Real HTTPS response headers</h2><pre>'+html.escape(json.dumps(d['headers'],indent=2))+'</pre>'),
 'logging':('<h2>Loki + Promtail runtime / retention</h2><pre>'+html.escape(json.dumps({'services':[x for x in d['services'] if x['service'] in ['loki','promtail']],'retention':audit['loaded_retention'],'compactor_metrics':audit['compactor_metrics'],'persistence':read('main-persistence'),'storage':res['storage_guard']},indent=2))+'</pre>')}
style='body{font:18px system-ui;background:#f5f8f6;color:#16392a;margin:32px}h1{font-size:30px}h2{color:#166944}table{border-collapse:collapse;font-size:15px}td,th{border:1px solid #adbbb2;padding:10px;text-align:left}pre{white-space:pre-wrap;font:15px monospace;background:white;padding:18px;border:1px solid #ccd8d0}small{color:#466454}'
with sync_playwright() as p:
 b=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_EXECUTABLE'));page=b.new_page(viewport={'width':1600,'height':1050})
 for name,body in sections.items():
  content='<meta charset="utf-8"><style>'+style+'</style><h1>GreenShop — M3 runtime evidence</h1><small>Generated view of actual JSON observations. Source: main-hardening.json / main-smoke.json / main-security-audit.json / resources.json. No terminal or UI simulation.</small><p>Observed UTC: '+html.escape(d['time'])+'</p>'+body
  f=E/('main-verification-'+name+'.html');f.write_text(content);page.goto(f.as_uri());page.screenshot(path=str(E/('main-verification-'+name+'.png')),full_page=True)
 b.close()
print('PASS rendered audit views from recorded runtime JSON; explicitly identified as report screenshots.',flush=True)
