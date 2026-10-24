"""Generate current M3 docs from observed evidence, keeping M1/M2 history immutable."""

if __name__ == "__main__":
 raise SystemExit("Retired QA/recovery harness. Use GreenShop-Official: docker compose up -d --build")
import datetime,json
from pathlib import Path
R=Path(__file__).resolve().parents[2];E=R/'docs/evidence/commit3'
def read(n):
 p=E/(n+'.json');return json.loads(p.read_text()) if p.exists() else {}
def ok(n):return read(n).get('status')=='PASS'
def write(name,s):
 p=R/name;p.write_text(s.strip()+'\n')
rows=[]
def row(id,title,proof,method,limit='',partial=False):
 rows.append({'id':id,'criterion':title,'status':('PARTIAL' if partial else 'PASS') if all(ok(p) for p in proof) else 'FAIL','method':method,'observed_result':'See measured values in referenced evidence','evidence':[p+'.json' for p in proof],'limitation':limit})
for id,title in [('LOG-01','Loki and Promtail health / datasource'),('LOG-02','Application, Nginx and MySQL ingestion'),('LOG-03','At least three executable LogQL queries')]:row(id,title,['qa-logql','main-logql'],'Docker health, authenticated Grafana proxy, actual LogQL results and low-cardinality labels')
row('LOG-04','Safe diagnostic templates and nested correlation',['diagnostic-pipeline-tests','diagnostic-runtime-qa','diagnostic-runtime-main'],'Exact pinned Promtail stages; real QA DB fault, exception and authentication; QA-first collector rollout','Historical schema v1 is unchanged; no Main failure or authenticated event manufactured.')
row('LOG-05','Secret redaction / malformed JSON / duplicates / retry',['diagnostic-pipeline-tests'],'40 application + 9 Nginx + 2 MySQL fixtures; 16 fake secret classes; real 500→204 client retry','Closed templates, never raw Message/State/Scopes/Exception. Known-format IDs are validated, not proof against deliberately forged secret-looking IDs.')
row('LOG-06','Persistent storage and collector checkpoints',['qa-persistence','main-persistence','diagnostic-runtime-qa','diagnostic-runtime-main'],'Historical fixed-range comparisons after restarts; new v2 interval unchanged after QA collector restart','Bounded retries are not an exactly-once/zero-loss guarantee.')
row('LOG-07','Retention configured, loaded, compactor active',['qa-security-audit','main-security-audit'],'Loaded 72h config and actual compactor counters','Physical 72h expiry + 2h grace NOT TESTED.')
row('INC-01','GS-SEC-001 exact threshold, logs and notifications',['gs-sec-001-firing','gs-sec-001-resolved','gs-sec-001-ui-cycle'],'Retained real QA cycles: first four Normal, fifth Firing, five unique request IDs, real Firing/Resolved receipts','New schema auth failure/success verified separately; metrics/rule/auth logic unchanged. No Main incident.')
for c in read('rubric-acceptance').get('controls',[]):
 rows.append({'id':c['id'],'criterion':c['measure'],'status':c['status'],'method':'Runtime control checks and rubric mapping','observed_result':c['status'],'evidence':c['evidence'],'limitation':c['scope_and_limits']})
row('SEC-01','System-wide non-root scope',['process-privileges-final','qa-hardening','main-hardening'],'Actual PID1/children UIDs, GIDs, capabilities and NoNewPrivs','Web 1654; Loki/Promtail 10001. Nginx/PMA root masters, non-root workers; mysqld 999; cAdvisor root.',True)
row('SEC-02','Least privilege overall',['qa-hardening','main-hardening'],'Capability restrictions and live exporter permission denials','cAdvisor host/socket trust and app schema DDL remain.',True)
rows.append({'id':'SEC-03','criterion':'Credential reuse reviewed','status':'PARTIAL','method':'Read-only live secret equality and operator decision','observed_result':'OPEN — RISK ACCEPTED','evidence':['accepted-security-risk.json','grafana-password-audit.json'],'limitation':'Local academic VMware only; reassess before public/production or more operators. Randomness provenance NOT VERIFIED.'})
row('OPS-01','Main preservation',['main-preservation','diagnostic-runtime-main'],'15 table hashes, keys/uploads/TLS/migrations, original IDs and mounts','Main Customer/Admin authenticated workflows NOT TESTED.')
row('OPS-02','M2 monitoring regression',['qa-security-audit','main-security-audit','qa-logql','main-logql'],'Five UP targets, 28 original panel queries, three M2 dashboards plus logs, four unchanged rule definitions')
row('OPS-03','QA business regression',['business-regression','engagement-regression','qa-upload-session','build-and-ai-tests','diagnostic-runtime-qa'],'Retained real business/upload/SignalR/AI fixture evidence plus targeted auth/DB/correlation checks','No new application image/business/auth/migration changes. Live Gemini NOT TESTED.')
row('OPS-04','Backup/restore and rollback',['backup-restore','qa-rollback','main-state-backup'],'Retained isolated QA restore, table equality and actual M2↔M3 rollback')
row('OPS-05','Historical MySQL connection failure investigated',['database-connection-investigation'],'Original stdout/API, historical metrics, rollout and retained event-buffer audit','Root cause INCONCLUSIVE; currently healthy, one historical Main error, no recurrence observed.')
rotation=read('docker-log-rotation-final');risk=read('accepted-security-risk');audit=read('staged-security-audit');doc=read('documentation-consistency')
required=lambda names: all(ok(n) for n in names)
verdict={
 'REQUIREMENT_5':'PASS' if all(x['status']=='PASS' for x in rows if x['id'].startswith(('LOG','INC'))) else 'FAIL',
 'REQUIREMENT_6_RUBRIC':read('rubric-acceptance').get('REQUIREMENT_6_RUBRIC','FAIL'),
 'LOKI_DEPLOYMENT':'PASS' if ok('main-logql') and ok('qa-logql') else 'FAIL',
 'PROMTAIL_DEPLOYMENT':'PASS' if ok('diagnostic-runtime-main') and ok('diagnostic-runtime-qa') else 'FAIL',
 'LOGQL_QUERIES':'PASS' if required(['qa-logql','main-logql','diagnostic-runtime-qa']) else 'FAIL',
 'LOKI_DIAGNOSTIC_LOGGING':'PASS' if required(['diagnostic-pipeline-tests','diagnostic-runtime-qa','diagnostic-runtime-main']) else 'FAIL',
 'LOGGING_SECRET_REDACTION':'PASS' if ok('diagnostic-pipeline-tests') and audit.get('SECRET_DISCLOSURE_SCAN')=='PASS' else 'FAIL',
 'MYSQL_ERROR_INVESTIGATION':read('database-connection-investigation').get('investigation_verdict','INCONCLUSIVE'),
 'NON_ROOT_HARDENING':'PARTIAL','NETWORK_ISOLATION':'PASS' if required(['qa-hardening','main-hardening']) else 'FAIL','LEAST_PRIVILEGE':'PARTIAL','NGINX_SECURITY_HEADERS':'PASS' if required(['qa-hardening','main-hardening','main-smoke']) else 'FAIL',
 'GRAFANA_CREDENTIAL_REUSE':'ACCEPTED_RISK' if risk.get('status')=='OPEN — RISK ACCEPTED' else 'FAIL','SECURITY_HARDENING_OVERALL':'PARTIAL',
 'DOCKER_LOG_ROTATION_SOURCE':'PASS' if rotation.get('final_states',{}).get('SOURCE_CONFIGURED') else 'FAIL',
 'DOCKER_LOG_ROTATION_QA':'PASS' if rotation.get('final_states',{}).get('QA_RUNTIME_APPLIED') and rotation.get('qa_verification',{}).get('status')=='PASS' else 'FAIL',
 'DOCKER_LOG_ROTATION_MAIN':rotation.get('final_states',{}).get('main_verdict','FAIL'),
 'M2_REGRESSION':'PASS' if required(['qa-security-audit','main-security-audit','qa-logql','main-logql']) else 'FAIL',
 'QA_REGRESSION':'PASS' if required(['business-regression','engagement-regression','qa-upload-session','qa-acceptance','build-and-ai-tests','diagnostic-runtime-qa','diagnostic-pipeline-tests']) else 'FAIL',
 'MAIN_PRESERVATION':'PASS' if required(['main-preservation','diagnostic-runtime-main']) else 'FAIL',
 'DOCUMENTATION_SYNC':doc.get('status','FAIL'),'README_SYNC':doc.get('status','FAIL'),
 'SECRET_DISCLOSURE_SCAN':audit.get('SECRET_DISCLOSURE_SCAN','FAIL'),'SECURITY_AUDIT':audit.get('SECURITY_AUDIT','FAIL'),
 'GIT_DIFF_CHECK':'PASS' if ok('git-hygiene') else 'FAIL','COMMIT_3_READY':'NO'}
blockers=[]
for k in ['REQUIREMENT_5','REQUIREMENT_6_RUBRIC','LOKI_DEPLOYMENT','PROMTAIL_DEPLOYMENT','LOGQL_QUERIES','LOKI_DIAGNOSTIC_LOGGING','LOGGING_SECRET_REDACTION','NETWORK_ISOLATION','NGINX_SECURITY_HEADERS','DOCKER_LOG_ROTATION_SOURCE','DOCKER_LOG_ROTATION_QA','M2_REGRESSION','QA_REGRESSION','MAIN_PRESERVATION','DOCUMENTATION_SYNC','README_SYNC','SECRET_DISCLOSURE_SCAN','GIT_DIFF_CHECK']:
 if verdict[k]!='PASS':blockers.append(k+' lacks passing evidence')
if verdict['SECURITY_AUDIT']!='PASS_WITH_ACCEPTED_RISK':blockers.append('Security audit has not cleared independent blockers with explicit accepted risk')
if read('database-connection-investigation').get('current_active_issue',True):blockers.append('Active Main DB connection issue')
if verdict['GRAFANA_CREDENTIAL_REUSE']!='ACCEPTED_RISK':blockers.append('Credential finding lacks explicit scoped operator acceptance')
if verdict['DOCKER_LOG_ROTATION_MAIN'] not in ['PASS','DEFERRED']:blockers.append('Main rotation status or disk pressure requires review')
verdict['COMMIT_3_READY']='NO' if blockers else 'YES'
limits=['OPEN — RISK ACCEPTED: Grafana/MySQL root reuse, local academic VMware only.','Nginx/phpMyAdmin root masters and cAdvisor host/socket trust remain.','Application schema DDL retained for EF startup migrations.','Main DB/phpMyAdmin Docker rotation deferred; desired plan differs from runtime.','Authenticated Main Customer/Admin flows and live Gemini NOT TESTED.','Loki physical 72h deletion NOT TESTED; loaded retention/compactor verified.','Historical MySQL root cause INCONCLUSIVE; current health recovered, no recurrent error observed.']
report={'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'repository':str(R),'branch':'main','head':'5b55ae826d513692e60b5e9e9f69656f0abf7a44','criteria':rows,'verdict':verdict,'blockers':blockers,'nonblocking_limitations':limits,'accepted_risk_reference':'accepted-security-risk.json'}
write('docs/evidence/commit3/verification.json',json.dumps(report,indent=2,ensure_ascii=False))
matrix='\n'.join('| '+x['id']+' | '+x['criterion']+' | '+x['status']+' | '+', '.join('['+f+']('+f+')' for f in x['evidence'])+' | '+(x['limitation'] or '—')+' |' for x in rows)
write('docs/evidence/commit3/README.md',f'''# GreenShop Commit 3 — nghiệm thu

Cập nhật UTC `{report['generated_utc']}`. Branch `main`, HEAD `{report['head']}`; source/evidence staged, chưa Git commit/push. Main project `dtc245200016_btl_tkqt_htpm`; QA `greenshop-m2-qa`; authoritative Main plan `/home/trung/.local/share/greenshop-monitoring/main/compose.json`.

```text
{chr(10).join(k+': '+v for k,v in verdict.items())}
```

Blockers: {('; '.join(blockers) if blockers else 'không còn blocker nghiêm trọng theo phạm vi nghiệm thu đã thống nhất')}. [Risk acceptance](accepted-security-risk.json) giữ finding mở; không có rotation credential trong đợt hoàn thiện này. Root masters/DDL, Main rotation deferred và các luồng NOT TESTED được ghi riêng, không biến thành PASS.

| ID | Tiêu chí | Trạng thái | Evidence | Giới hạn |
|---|---|---|---|---|
{matrix}

[Method và kết quả máy đọc](verification.json), [manifest SHA-256](manifest.json), [diagnostic tests](diagnostic-pipeline-tests.json), [QA runtime](diagnostic-runtime-qa.json), [MySQL investigation](database-connection-investigation.md), [hardening](security-hardening.md), [LogQL](logql-queries.md), [GS-SEC-001](gs-sec-001-investigation.md), [remediation cuối](final-hardening.md).

Demo: VS Code Remote SSH forward 3000 → Grafana OSS → Explore → GreenShop Loki; chọn đúng environment và time range. Dùng evidence QA cho incident, không tạo failed-login Main. Ảnh cũ giữ thời điểm/schema cũ; ảnh diagnostic mới có tên riêng. Không re-ingest lịch sử hoặc reset positions/volumes.
''')
rubric=read('rubric-acceptance');controls='\n'.join('| '+c['id']+' | '+c['measure']+' | '+c['status']+' | '+c['scope_and_limits']+' |' for c in rubric.get('controls',[]))
proc=[]
for env in ['qa','main']:
 for svc in read(env+'-hardening').get('services',[]):
  pid=svc.get('pid1_status',{});proc.append('| '+env+' | '+svc['service']+' | '+pid.get('Uid','?').split()[0]+' | '+pid.get('Gid','?').split()[0]+' | '+str(svc.get('caps_drop'))+' | '+pid.get('NoNewPrivs','?')+' |')
write('docs/evidence/commit3/security-hardening.md',f'''# Security Hardening Matrix

## Rubric và hardening tổng thể

`REQUIREMENT_6_RUBRIC={verdict['REQUIREMENT_6_RUBRIC']}`; `SECURITY_HARDENING_OVERALL=PARTIAL`. Dùng ngưỡng bốn biện pháp theo rubric 3–4 mà người dùng cung cấp; hiện {rubric.get('verified_measure_count',0)} biện pháp có bằng chứng. Không tìm thấy PDF giảng viên độc lập trong repo. Không thay tiêu chí và không tính password non-reuse là PASS.

| ID | Biện pháp | Kết quả | Phạm vi/giới hạn |
|---|---|---|---|
{controls}

[Rubric/grants thực](rubric-acceptance.json), [QA](qa-hardening.json), [Main](main-hardening.json), [PID1/children](process-privileges-final.json).

## UID/GID và least privilege

| Env | Service | PID1 UID | PID1 GID | CapDrop | NoNewPrivs |
|---|---|---|---|---|---|
{chr(10).join(proc)}

Web UID 1654 có upload/session regression thật; Loki/Promtail UID 10001, read-only rootfs, CapEff=0. Promtail GID0 để đọc log root:root 0640 không phải UID root hay Docker admin. Chỉ thư mục ba source container được cho group read để watch; Docker config.v2.json 0600 không đọc được. Không mount Docker socket/toàn log root vào collector. Nginx master root/worker101, phpMyAdmin master root/worker33, mysqld999; root healthcheck/exec helper không phải mysqld worker. cAdvisor root với host mounts/socket là residual host trust; socket `:ro` không hạn chế Docker API.

## Network và access control

Web→DB được phép, Nginx/Promtail→cả hai DB IP bị chặn bằng TCP probes, không chỉ DNS. DB trên internal database_net và bridge quản trị riêng để giữ loopback3306; phpMyAdmin trên database+admin, loopback8080. Web giữ app_net cho outbound Gemini; live Gemini chưa thử. Grafana/Prometheus loopback3000/9090; Loki/Promtail không publish3100/9080; logging_net internal, Grafana→Loki và collector→Loki hoạt động. Main IDs/volumes giữ nguyên. QA real SignalR/WebSocket/upload có evidence.

App giữ schema-scoped ALL/DDL cho EF startup migrations, không quyền global/user administration. Exporter PROCESS-only, SELECT/UPDATE/DELETE business và mysql.user bị từ chối. Tách migration identity là cải tiến production; không thu hồi DDL nóng khi thiếu quy trình thay thế.

## Grafana audit và accepted risk

[GRAFANA_MYSQL_ROOT_CREDENTIAL_REUSE](accepted-security-risk.json): `ACCEPTED_RISK`, scope `Local academic VMware deployment`, status **OPEN — RISK ACCEPTED**. Operator có chủ đích dùng chung, đã chấp nhận rủi ro tăng impact khi lộ credential. Không RESOLVED, không best practice; đánh giá lại trước public/production hoặc thêm operator. Không đổi Grafana Main/MySQL root, không rotation trong đợt này. Plaintext disclosure hoặc finding độc lập khác không được risk acceptance che phủ.

[Audit đa yếu tố](grafana-password-audit.json): nondefault, chưa thấy pattern dễ đoán trong heuristic hữu hạn; không thấy plaintext trong phạm vi text/log đã quét; loopback, anonymous401/configfalse, brute-force protection, private parents0700 và secret RO. Độ dài10 không tự chứng minh mạnh/yếu; nguồn sinh ngẫu nhiên NOT VERIFIED, không suy diễn entropy. Historical QA rotation/rollback evidence vẫn giữ ở [grafana-rotation-qa.json](grafana-rotation-qa.json), không chạy lại theo yêu cầu mới. `SECRET_DISCLOSURE_SCAN` tách khỏi `SECURITY_RISK_REVIEW`; tổng hợp chỉ có thể `PASS_WITH_ACCEPTED_RISK` khi không còn blocker độc lập.

## Headers và filesystem

HTTPS redirect/TLS1.2/1.3, SAMEORIGIN/nosniff/referrer policy, server_tokens off, public /metrics và /nginx_status404 đã kiểm bằng response thật. Không thêm CSP/HSTS mới chưa thử trên self-signed lab. Keys mode700/600 giữ nguyên; ownership web có private manifest/rollback QA; hash uploads/keys/TLS không đổi. Secret values/DB dump/private plans không nằm trong Git.

## Residual risks / production improvements

- Root masters, cAdvisor host access và schema DDL: cần nhánh QA tương thích trước khi giảm thêm quyền.
- Grafana/MySQL root reuse: risk chấp nhận chỉ cho local academic VMware.
- Main DB/PMA rotation: source và plan10m×3, runtime chưa áp dụng, **DEFERRED_MAINTENANCE**. QA applied+verified policy/data/session; physical rollover DB/PMA NOT TESTED, driver rollover đã thử trên QA Nginx.
- Loki72h +2h grace load/compactor active; physical expiry NOT TESTED. Filesystem retention không phải disk quota.
- Promtail EOL: giữ đúng rubric lab, chuyển Alloy trước môi trường ngoài lab. Retry hữu hạn/checkpoint không bảo đảm exactly once/zero loss.
- Main authenticated business, live Gemini NOT TESTED; không suy từ QA sang Main. Historical DB cause INCONCLUSIVE, health hiện tốt; xem investigation.

Blockers hiện tại: {('; '.join(blockers) if blockers else 'không có độc lập nghiêm trọng trong phạm vi đã kiểm')}. [Staged snapshot audit](staged-security-audit.json) ghi rõ số blob, PNG và giới hạn của scan.
''')
# Append current schema/query guidance to original measured LogQL evidence.
queries=[]
for env in ['qa','main']:
 for q in read(env+'-logql').get('queries',[]):queries.append(f"- `{env}` / {q['name']}: `{q['expression']}` — {q['status']}, {q['entries']} entries, query UTC {q.get('query_utc')}; range/sample trong [{env}-logql.json]({env}-logql.json).")
write('docs/evidence/commit3/logql-queries.md','''# LogQL — observed results

Chọn **GreenShop Loki** / UID `greenshop-loki`; URL nội bộ `http://loki:3100`. Grafana Main và QA dùng Loki riêng. Stream labels: environment, project, service, source, stream; Loki có service_name/detected_level. `| json` tạo parsed query fields, không có nghĩa request_id/category đã được index làm stream label.

```logql
{environment="qa",service="greenshop-web"} | json | schema_version="2" | diagnostic_code="db.connection.failed" | __error__=""
```

```logql
{environment="qa",service="greenshop-web"} | json | event="auth.login.failed" | incident="GS-SEC-001" | __error__=""
```

```logql
sum(count_over_time({environment="qa",service="greenshop-web"} | json | event="auth.login.failed" | __error__="" [1m]))
```

```logql
{environment="main",service="nginx"} | json | status >= 400 | __error__=""
```

```logql
{environment="main",service="mysql"}
```

Các query v1 tiếp tục tương thích schema v2. Diagnostic DB/exception và auth v2 thực tế có trong [QA runtime](diagnostic-runtime-qa.json); [diagnostic LogQL evidence](diagnostic-logql.json) ghi exact expression/range/count/sample. First4 Normal/fifth Firing, count5 và notification vẫn dựa vào [incident metric+logs thật](gs-sec-001-firing.json), không thay rolling metric bằng LogQL count.

'''+ '\n'.join(queries)+'''

Chọn time range chứa thời điểm JSON evidence: Main startup MySQL có thể cần24h hoặc absolute range; recent30m có thể rỗng. V1 không tự có message mới. Không reset/re-ingest để đổi schema. Unknown events giữ diagnostic generic, không raw payload. Query numeric Nginx phải đặt __error__ filter sau comparison. Physical retention và UI screenshots cũ giữ timestamp quan sát riêng.
''')
inc=read('gs-sec-001-firing');res=read('gs-sec-001-resolved')
write('docs/evidence/commit3/gs-sec-001-investigation.md',f'''# GS-SEC-001 — metrics và logs

Rule không đổi: `sum(greenshop_auth_login_failures_last_60s) >= bool 5`. Authentication/rate limiter/60s window giữ nguyên. API run bắt đầu `{inc.get('start_utc')}`, Firing `{inc.get('observed_utc')}`, recovery `{res.get('observed_utc')}`. Bốn lần sai thật giữ Normal; lần năm Firing, counter tăng5; Loki5 event/năm request ID, count query5, receiver nhận Firing/Resolved. [API firing](gs-sec-001-firing.json), [resolved](gs-sec-001-resolved.json), [UI cycle độc lập](gs-sec-001-ui-cycle.json). Hai cửa sổ riêng, không cộng gộp thành một incident.

[Before](qa-incident-before.png) · [Firing](qa-incident-firing.png) · [Loki](qa-incident-loki.png) · [Recovery](qa-incident-resolved.png) · [Receipts](qa-incident-notifications.png).

Schema mới giữ event/request_id/route/reason_code/incident; bổ sung fixed diagnostic_message/code/trace_id. [QA mới](diagnostic-runtime-qa.json) kiểm auth success/failure thật qua cùng pipeline; [fixtures](diagnostic-pipeline-tests.json) kiểm canary. Không chạy lại năm failed-login trên Main. Full business/auth logic không đổi nên evidence exact threshold cũ được giữ hợp lệ; không overwrite ảnh/timeline cũ. Grafana dashboard M2 annotation lịch sử giữ nguyên theo yêu cầu bảo toàn rule; hướng dẫn mới tại đây.

Correlate UTC + request_id + incident và trace_id mới. Không giữ user/email/IP/raw form/password/cookie; không suy cùng attacker hay có compromise. LogQL count có ingestion/checkpoint/retry delay, không thay exact rolling Prometheus gauge. Clock đã đồng bộ trước các incident; [time-sync](time-sync.json). Bounded retry không bảo đảm exactly once.
''')
db=read('database-connection-investigation');event=db.get('historical_event',{})
write('docs/evidence/commit3/database-connection-investigation.md',f'''# Main MySQL connection event — investigation

`MYSQL_ERROR_INVESTIGATION={db.get('investigation_verdict','INCONCLUSIVE')}`. Trạng thái hiện tại: active issue `{db.get('current_active_issue')}`, SELECT1/readiness liên tiếp200, MySQL healthy/restart0. Không sửa code/retry/timeout/schema khi không có active defect được xác định.

| UTC 16/10/2026 | Việt Nam 17/10 | Evidence |
|---|---|---|
| 17:25:46 | 00:25:46 | Migrations up to date |
| 17:25:47 | 00:25:47 | Application listening/start |
| 17:26:23.317 | 00:26:23.317 | [Network segmentation completion](main-network-segmentation.json) |
| 17:26:26.305 | 00:26:26.305 | Readiness /health/ready EF20004 |

Actual fixed message verified in Docker stdout: `An error occurred using the connection to database 'greenshop' on server 'db'.` Category Microsoft.EntityFrameworkCore.Database.Connection, EventId20004, RequestId `{event.get('request_id','')}`, trace `{event.get('trace_id','')}`. Không có Exception trong bản ghi gốc; [safe parsed evidence](database-connection-investigation.json) có SHA256 để đối chiếu, không dump raw State/Scopes/payload.

Historical Prometheus mysql_up và up job=mysql đều có samples bằng1 trong cửa sổ17:24–17:30; sampling không loại trừ mất kết nối rất ngắn. DB stdout interval không có dòng crash/restart; inspect giữ original DB ID, restart0 và StartedAt trước event. Chỉ tìm thấy một EF connection error trong logs của current Main web; không có event cùng loại sau đó. Health history Docker chỉ giữ các lần gần nhất, không dùng nó để suy health lịch sử.

Docker events cũ trả rỗng do buffer hữu hạn, không chứng minh không có network operation. Temporal correlation mạnh nhất là đổi network khoảng3s trước error, có thể pooled connection/DNS route cũ; chưa có socket errno/timeout/connection-pool evidence để xác nhận cơ chế. Startup timing ít phù hợp hơn vì migrations/start đã xong39s trước. Không có bằng chứng credential sai, MySQL crash hoặc mất dữ liệu. **Root cause vẫn INCONCLUSIVE**, không đổi thành transient root-cause verified chỉ vì hiện đã phục hồi.

[QA reproduction](diagnostic-runtime-qa.json) ngắt riêng web→database network, tạo real DB failure/exception rồi phục hồi; chứng minh pipeline chẩn đoán mới giữ code/category/route/request/trace. Đây là test tính hữu ích và khả năng phục hồi, không chứng minh nguyên nhân Main lịch sử giống hệt. [Pipeline investigation](logging-diagnostic-investigation.json) xác nhận output allowlist v1 làm mất diagnostic fields trước Loki; schema v2 fixed templates đã QA trước Main, chỉ restart collector, không re-ingest lịch sử.

Theo dõi `diagnostic_code="db.connection.failed"` theo UTC/request ID; nếu tái diễn thì thu thập socket/network/metrics cùng thời điểm và tái lập QA trước repair. Main DB/PMA không recreate; dữ liệu15 tables/keys/uploads/TLS/migrations bảo toàn. Uncertainty: causal network event không còn trong buffer, log gốc không exception, metric sampling không liên tục.
''')
write('docs/evidence/commit3/final-hardening.md',f'''# Final hardening remediation và acceptance

Hai kết luận độc lập: rubric `{verdict['REQUIREMENT_6_RUBRIC']}` với sáu biện pháp có runtime proof; toàn hệ thống `PARTIAL` do residual risks. [Security matrix](security-hardening.md) và [rubric](rubric-acceptance.json) giữ đúng scope của mỗi phép kiểm, không yêu cầu mọi container/root master tuyệt đối non-root.

## Thay đổi trong đợt hoàn thiện này

1. Promtail schema v2: closed diagnostic templates; validated framework RequestId/TraceId và route group, auth fields tương thích v1. Raw Message/Exception/State/Scopes không chuyển tiếp. [51 fixture cases và retry](diagnostic-pipeline-tests.json), [real QA DB/exception/auth](diagnostic-runtime-qa.json), [Main collector-only rollout](diagnostic-runtime-main.json).
2. MySQL Main event được điều tra chỉ đọc: `{verdict['MYSQL_ERROR_INVESTIGATION']}` nguyên nhân, hiện healthy và không recurrence. [Report](database-connection-investigation.md), không sửa business/retry/schema thiếu căn cứ.
3. Ghi `GRAFANA_MYSQL_ROOT_CREDENTIAL_REUSE`, `ACCEPTED_RISK`, scope local academic VMware, `OPEN — RISK ACCEPTED`. Không rotate credentials. [Audit](grafana-password-audit.json) và [risk](accepted-security-risk.json) tách reuse khỏi disclosure. Historical QA rotation evidence giữ nguyên, không chạy lại.
4. Rotation source/Main plan10m×3; QA applied/verified giữ bằng chứng. Main DB/PMA `{verdict['DOCKER_LOG_ROTATION_MAIN']}`, không recreate/truncate; [disk/rotation consistency](docker-log-rotation-final.json). Physical DB/PMA rollover NOT TESTED; QA Nginx driver rollover đã quan sát.
5. Root/monitoring README và toàn evidence cập nhật schema/risk/limits, kiểm staged blobs/PNG/links/config/manifest. [Audit](staged-security-audit.json), [docs validation](documentation-consistency.json), [changes](changes.json).

## Giới hạn và quyết định

{chr(10).join('- '+x for x in limits)}

Không có credential rotation, Main app/DB/Nginx/Grafana/Prometheus/Loki restart hay image/schema thay đổi trong đợt này; chỉ Main Promtail restart sau QA. Lỗi harness QA trước đó (mount ordering và client timeout) được sửa đúng thực tế; không thay retry/timeout/logic ứng dụng để qua test. Full QA business/SignalR/upload/AI fixture, original GS-SEC-001 thresholds và Main preservation evidence được giữ, bổ sung kiểm thử đúng phạm vi collector.

`SECRET_DISCLOSURE_SCAN={verdict['SECRET_DISCLOSURE_SCAN']}`, `SECURITY_AUDIT={verdict['SECURITY_AUDIT']}`, `COMMIT_3_READY={verdict['COMMIT_3_READY']}`. Blockers: {('; '.join(blockers) if blockers else 'none in agreed academic scope')}. Stage còn nguyên để operator tự commit; không commit/push/reset Git.
''')
# Root and monitoring footers share only core facts; detailed runbook is monitoring-specific.
footer=f'''## Commit 3: centralized logging đã triển khai trên runtime hiện hữu

Loki3.6.18/Promtail3.6.11 pinned images: Docker json-file Web/Nginx/MySQL → Promtail → Loki → Grafana Explore. UID web1654, Loki/Promtail10001; không public3100/9080 hoặc Docker socket collector. Volume riêng Loki/positions, retention72h + delete grace2h, physical expiry NOT TESTED. Prometheus lưu numeric metrics/đánh giá threshold; Loki lưu sanitized log events để điều tra theo UTC/request ID.

Kết quả hiện tại: Requirement5 `{verdict['REQUIREMENT_5']}`, Requirement6 rubric `{verdict['REQUIREMENT_6_RUBRIC']}`, hardening tổng thể PARTIAL, Commit3 ready `{verdict['COMMIT_3_READY']}`. Đây là trạng thái runtime/source chuẩn bị commit, chưa commit/push. Grafana/MySQL root credential reuse là [accepted risk](docs/evidence/commit3/accepted-security-risk.json), **OPEN — RISK ACCEPTED**, chỉ local academic VMware; không phải best practice và phải đánh giá lại trước public/production/thêm operator. `SECURITY_AUDIT={verdict['SECURITY_AUDIT']}` tách với secret disclosure scan.

Mở Grafana qua VS Code Remote SSH forward3000, Prometheus9090; Explore chọn **GreenShop Loki** UID `greenshop-loki`, time range24h hoặc absolute range trong evidence. Main HTTPS `https://192.168.197.128/` dùng SAN/chứng chỉ tự ký hiện có; QA HTTPS21543, Grafana21300, Prometheus21990 qua loopback/forward. Không cần Grafana Cloud; Promtail không có UI quản trị riêng.

```logql
{{environment="qa",service="greenshop-web"}} | json | diagnostic_code="db.connection.failed" | __error__=""
{{environment="qa",service="greenshop-web"}} | json | event="auth.login.failed" | incident="GS-SEC-001" | __error__=""
{{environment="main",service="nginx"}} | json | status >= 400 | __error__=""
{{environment="main",service="mysql"}}
```

Schema v2 giữ diagnostic message/code cố định, category/event ID, validated request/trace ID và route class. Không chuyển raw message/exception/SQL/scopes/body/identity/token; unknown events dùng template generic. V1 lịch sử không đổi. [LogQL thực thi](docs/evidence/commit3/logql-queries.md), [diagnostic QA](docs/evidence/commit3/diagnostic-runtime-qa.json), [MySQL investigation](docs/evidence/commit3/database-connection-investigation.md), [GS-SEC-001](docs/evidence/commit3/gs-sec-001-investigation.md), [hardening](docs/evidence/commit3/security-hardening.md), [nghiệm thu](docs/evidence/commit3/README.md).

Sáu controls: non-root các service phù hợp, network segmentation đã TCP-probe, HTTPS/security headers, capability/NoNewPrivs, DB schema/exporter role limits và telemetry/secrets isolation. Nginx/PMA root masters, cAdvisor host trust và app DDL vẫn residual; không tuyên bố mọi service non-root. Main DB/PMA log rotation source/plan configured10m×3, runtime **DEFERRED_MAINTENANCE**, QA applied/verified. Main authenticated flows và live Gemini NOT TESTED. Local VMware/self-signed HTTPS không đại diện production.

Main authoritative plan `/home/trung/.local/share/greenshop-monitoring/main/compose.json`, project `dtc245200016_btl_tkqt_htpm`; QA `greenshop-m2-qa`. Fresh installation dùng hướng dẫn cài mới trên host riêng; Main hiện có chỉ dùng private plan giữ volume identity, credentials, TLS và backups. Không chạy prepare/core rollout lại trên deployment này. Xem runbook trong [monitoring](monitoring/README.md#vận-hành-diagnostic-logging-m3).

Promtail đã EOL; giữ cho rubric lab, chuyển Alloy sau QA tương thích trước môi trường ngoài lab ([Grafana](https://grafana.com/docs/loki/latest/send-data/)). Không dùng physical expiry chưa quan sát hoặc known-secret scan hữu hạn như bảo đảm tuyệt đối.
'''
marker='\n## Commit 3: centralized logging đã triển khai trên runtime hiện hữu'
f=R/'README.md';s=f.read_text().split(marker)[0];f.write_text(s.rstrip()+'\n\n'+footer)
f=R/'monitoring/README.md';s=f.read_text().split(marker)[0];short='''## Commit 3: centralized logging đã triển khai trên runtime hiện hữu

M2 metrics + M3 logs đang hoạt động trên cùng Main/QA project. Loki3.6.18/Promtail3.6.11, datasource `greenshop-loki`, dashboard `greenshop-logs` bổ sung ba M2 dashboards/four unchanged alert rules. Logging qua internal logging_net, volumes Loki/positions riêng. Web/Nginx/MySQL selected log directories RO, không Docker socket collector và không host3100/9080. Grafana512MiB; Loki256MiB/.4CPU, Promtail96MiB/.2CPU. Loaded retention72h, grace2h; physical expiry NOT TESTED.

[Trạng thái nghiệm thu](../docs/evidence/commit3/README.md), [LogQL exact expressions/ranges/results](../docs/evidence/commit3/logql-queries.md), [diagnostic schema/tests](../docs/evidence/commit3/diagnostic-runtime-qa.json), [MySQL investigation](../docs/evidence/commit3/database-connection-investigation.md), [security matrix](../docs/evidence/commit3/security-hardening.md), [accepted risk](../docs/evidence/commit3/accepted-security-risk.json). Credential reuse vẫn OPEN — RISK ACCEPTED, local academic VMware only; không rotation/reset. Root masters/cAdvisor/DDL, Main DB/PMA rotation deferred, Main auth/live Gemini/physical expiry NOT TESTED được giữ rõ. Promtail EOL, migration Alloy trước production.

### Vận hành diagnostic logging M3

Explore → GreenShop Loki → chọn đúng environment và absolute UTC range; Main/QA có Loki riêng. Xem app, failed-login, Nginx status>=400 và MySQL bằng queries trong LogQL guide. V2 chỉ có trên event phát sinh mới; không reset positions hoặc re-ingest lịch sử. Fixed diagnostic templates thay raw Message/Exception/State/Scopes, bounded IDs không làm stream labels. Malformed/unknown event vẫn có generic diagnostic metadata.

Sau source container recreation, refresh đúng môi trường bằng `python3 scripts/logging-runtime.py refresh qa` hoặc `main`, rồi dùng **existing project + authoritative plan** up --no-deps promtail; không compose mặc định từ repo. Current Main project dtc245200016_btl_tkqt_htpm, plan /home/trung/.local/share/greenshop-monitoring/main/compose.json; QA greenshop-m2-qa, plan ở private qa/compose.json. Docker rotation cùng container đã test180/180 Nginx entries; DB/PMA QA policy/persistence verified, chưa ép physical rollover. Main DB/PMA desired plan10m×3 chưa runtime applied, maintenance cần fresh backup/rollback và phê duyệt riêng, không truncate.

Chỉnh collector: backup config vào private m3/<env>/diagnostic-v2/, chạy `tests/logging/diagnostic_pipeline_test.py` (không ingest fixture vào Loki), chạy QA targeted fault suite theo guard, xác minh data/auth/correlation/positions, rồi restart riêng Main Promtail. Config bind không hot reload tự động. Rollback schema: khôi phục promtail-v1.yml từ private backup về source bind và restart đúng Promtail; không đổi positions/Loki volume. Không chạy QA outage/incident scripts đồng thời.

Backups core/data/keys/uploads/TLS/Grafana và rollback metadata có trong private m3/main/, mode0700/0600, ngoài Git. Main DB/PMA/Grafana/Prometheus IDs và credentials giữ nguyên. Core rollback phải theo plan/ownership/network snapshot trước đó; không tự restore data lên Main đang có writes. Full backup/restore/QA rollback evidence liên kết từ acceptance.

Mỗi ngày `python3 scripts/check-logging-storage.py main` hoặc qa, đọc df/disk usage và compactor counters; disk>85% cần theo dõi, free<1GiB là critical. Retention không phải quota; không prune/delete chunks/logs thủ công. Collector batch256KiB, timeout10s, retries20/backoff0.5–10s; memory retries/checkpoint không bảo đảm exactly once/zero loss khi outage dài. Runbook này không cho phép rotate credential theo nhiệm vụ hiện tại.
''';f.write_text(s.rstrip()+'\n\n'+short)
print('Generated current M3 report; READY='+verdict['COMMIT_3_READY']+'; independent blockers='+str(len(blockers)))
