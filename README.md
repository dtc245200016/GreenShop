# GreenShop — Docker Compose, Monitoring & Logging

Đồ án Triển khai và Quản trị Hệ thống Phần mềm: ASP.NET Core MVC, MySQL, Nginx HTTPS, Prometheus/Grafana và Loki/Promtail. Website có Customer/Admin riêng, danh mục/sản phẩm/upload, giỏ hàng, COD/đơn hàng, review, chat/SignalR và Excel export. Mã ứng dụng và migrations được giữ nguyên khi tinh gọn.

## Chạy trên Ubuntu VMware hiện có

```bash
cd /home/trung/GreenShop-Official
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

Một Compose duy nhất: `docker-compose.yml`; project cố định `dtc245200016_btl_tkqt_htpm`. Cả12 service chạy mặc định, không profiles, không QA stack hoặc Python deployment helper. Giữ `.env`, `secrets/` và `nginx/ssl/` hiện có; chúng chứa credentials/TLS riêng và được Git ignore. `.env.example` chỉ là mẫu cho cài mới, không dùng ghi đè cấu hình đang chạy.

Compose dùng đúng7 volumes và6 networks Main đã có qua `external` + tên đầy đủ, tránh tạo nhầm DB/storage trống. Đây là cấu hình của VM hiện hữu; không tuyên bố một bản clone trống chưa có secrets/TLS/volumes có thể tự khởi tạo mà không chuẩn bị.

| Thành phần | Vai trò / truy cập |
|---|---|
| `nginx`, `web_app` | `https://192.168.197.128`; HTTP80 chuyển HTTPS443 |
| `db`, `phpmyadmin` | MySQL loopback3306; phpMyAdmin `http://127.0.0.1:8080` |
| `prometheus` | `http://127.0.0.1:9090`;5 targets |
| `grafana` | `http://127.0.0.1:3000`;2 datasource,4 dashboard,4 rules |
| `mysql-exporter`, `nginx-exporter`, `cadvisor` | Metrics backend/container, không publish host ports |
| `loki`, `promtail` | Logs trong Grafana Explore, Loki không public3100 |
| `alert-receiver` | Webhook nội bộ cho demo GS-SEC-001, không email bên ngoài |

Windows: VS Code Remote SSH forward3000/9090/8080, mở Forwarded Address. Website dùng IP VM và chứng chỉ lab cho đúng IP trên. Grafana username `admin`; mật khẩu riêng đã rotate, lưu `secrets/grafana-password`. Mở riêng file bằng editor trên VM, không đưa giá trị lên slide/log/Git. Tài khoản website demo ở `secrets/demo-accounts.json`. MySQL root giữ theo lựa chọn của operator; không dùng chung Grafana nữa.

## Kiến trúc

```text
Browser → Nginx HTTPS → Web → MySQL
                         ↓ metrics
Exporters / cAdvisor → Prometheus → Grafana
Docker syslog → Promtail → Loki → Grafana Explore
Grafana alerts → alert-receiver
```

- app_net: Nginx/Web; database_net: Web/DB/exporter/PMA.
- monitoring_net: Prometheus/Web/Nginx/exporters/cAdvisor/receiver/Grafana.
- logging_net: Promtail/Loki/Grafana; admin_net: giao diện loopback và đường nhận syslog của Promtail.
- db_admin_net: giữ MySQL loopback access riêng; Nginx/Promtail không truy cập DB.

[Promtail config](monitoring/promtail/promtail.yml) dùng syslog RFC5424 từ Docker daemon qua **UDP127.0.0.1:1514**, không socket, không Docker log mounts, không generated targets hay CIDs. Service label lấy từ APP-NAME đã allowlist `nginx|greenshop-web|mysql`; các nhãn cố định environment=main, project=Main, job=greenshop, source=docker. Cùng parser an toàn loại raw payload/secrets trước Loki. Core driver có local cache rotation10m×3 và non-blocking buffer4m; UDP không ACK/replay, có thể mất centralized logs khi collector ngừng. `docker compose logs` vẫn đọc cache. Đây không phải zero-loss logging.

## Kiểm tra và demo

[Demo3–5 phút và8 query đã kiểm](docs/demo.md), [nghiệm thu hiện hành](docs/evidence/commit3/main-restoration.md), [monitoring config](monitoring/README.md).

```bash
docker compose ps
docker compose logs --tail 50 web_app nginx promtail
curl --cacert nginx/ssl/cert.pem https://192.168.197.128/health/ready
```

Trong Prometheus: `up{job="greenshop"}`, `mysql_up`, `nginx_up` phải =1; Targets5/5 UP. Public `/metrics` vẫn404 theo hardening; chỉ Prometheus mang metrics token mới scrape được nội bộ. Explore → GreenShop Loki → Last30m, chọn environment=main.

## Hardening và dữ liệu

Web UID1654, Loki/Promtail10001; cap_drop ALL/no-new-privileges trên dịch vụ tương thích; secrets RO trong thư mục0700; admin ports loopback; networks phân tách; HTTPS/headers nosniff/SAMEORIGIN/referrer. Nginx/PMA master root, MySQL worker999 và cAdvisor host/socket là ngoại lệ đã đánh giá, không ép USER phá image. Web dùng DB account riêng, exporter PROCESS-only; app giữ DDL trong schema để EF migrations hoạt động. Tất cả10 migrations hiện có được giữ; không reset DB.

Volumes giữ đúng dữ liệu MySQL, uploads, keys, Prometheus, Grafana, Loki và positions. Các bản backup cũ được bảo toàn; không tạo backup mới trong đợt này. Không dùng `down -v` để sửa lỗi. Các nguồn thử nghiệm cũ được giữ nguyên trong `tests/legacy/` để không mất uncommitted work, không dùng chúng khởi động Main. Workspace cũ vẫn bị Compose guard, không còn runtime mounts phụ thuộc nó.

## Bảo trì và Git

Chỉ còn3 script bảo trì tùy chọn: tạo cert lab, bootstrap DB user, tạo Admin đầu tiên; chúng không phải điều kiện khởi động hệ thống hiện có. Không chạy lại bootstrap trên DB đang hoạt động nếu không có nhu cầu thực.

47 harness/recovery sources được di chuyển nguyên vẹn vào legacy, không xóa công việc mã nguồn. Các evidence dư thừa được dọn sau khi đối chiếu Git/consolidation; ảnh grading chọn lọc được giữ và ghi rõ lịch sử. HEAD/index124 staged giữ nguyên, các sửa/xóa/di chuyển mới còn working tree; review và stage có chủ đích trước commit. Không tự commit/push.
