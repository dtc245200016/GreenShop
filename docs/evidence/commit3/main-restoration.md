# Main duy nhất — nghiệm thu GreenShop M1+M2+M3

Một nguồn `docker-compose.yml` trong GreenShop-Official; lệnh khởi động `docker compose up -d --build`. Không QA hoặc runtime Python/private plan. [README](../../../README.md), [demo8 query](../../demo.md), [acceptance thực tế](acceptance.json).

| Hạng mục | Kết quả |
|---|---|
| Compose config/up và12 services | PASS |
| HTTPS, MySQL/PMA, Customer/Admin, upload, cart/COD/idempotency, SignalR negotiation | PASS |
| Prometheus5/5 +3 gauges=1, Grafana dashboards/2 datasource/4 rules | PASS |
| Logs Web/Nginx/MySQL và events mới, không CIDs | PASS |
| Web force-recreate giữ session/network/volumes, syslog tự theo | PASS |
| GS-SEC-0014 Normal/5 Firing,5 logs, webhook Firing/Resolved | PASS — [timeline](restoration-restart-incident.json) |
| Hardening rubric >=4 nhóm | PASS |
| Hardening tổng thể | PARTIAL — cAdvisor/socket, root masters, app schema DDL, root credential provenance và syslog UDP loss window |
| Data, uploads, keys, TLS và Git index | Xem fingerprints/runtime audit trong acceptance.json |

Grafana đã rotate sang random credential riêng. Theo lựa chọn operator, không đổi root MySQL. Không reset DB, không tạo backup mới, không commit/push. Driver cache core10m×3 và PHP json-file10m×3 đã áp dụng qua Compose; không ép physical rollover. Không claim full browser/WebSocket/live Gemini/CVE/VM reboot hoặc retention-expiry mới.

Đã gỡ27 QA containers +1 receiver cũ,10 networks,15 volumes,20 image tags QA không dùng Main.47 source harnesses giữ nguyên trong tests/legacy;130 evidence dư thừa đã có bản byte-identical trong index được dọn. Bản backup cũ và workspace cũ có source/Git riêng không xóa; workspace cũ bị Compose guard và không còn mounts Main. Các ảnh giữ lại là historical grading captures, không phải ảnh chụp UI của lần triển khai mới.

Main chỉ dùng Official .env/secrets/TLS đã ignore. No Docker socket/log mounts vào Promtail; UDP1514 chỉ loopback. Label service từ syslog APP-NAME allowlist; environment main/project/job/source tĩnh. Quy trình không cần generated targets, refresh script hoặc chmod Docker directories nữa.
