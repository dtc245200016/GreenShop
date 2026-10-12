# GreenShop — Nghiệm thu M1 / Commit 1

**Verdict: M1 READY — workspace và runtime Ubuntu VMware đã nghiệm thu; chưa commit/push.**

Báo cáo chốt ngày 13/10/2026 theo thời gian phiên làm việc. Timestamp bên trong screenshot/log phản ánh đồng hồ VM khi thu thập; không chỉnh sửa ngày hoặc dữ liệu để tạo minh chứng.

## Phạm vi và môi trường

- Ubuntu 26.04 LTS, Docker Engine 29.7.2, Docker Compose plugin 5.4.0, SDK .NET 8.0.407, OpenSSL 3.5.5.
- Runtime Nginx 1.31.6, MySQL 8.0.46; IP VM đã kiểm tra trực tiếp: `192.168.197.128`.
- Bốn service M1: `db`, `web_app`, `nginx`, `phpmyadmin`; không thêm Prometheus/Grafana/Loki/Promtail.
- Main: `greenshop`; các phép ghi kiểm thử chỉ trong `greenshop_order_qa`, project `greenshop-m1-qa`, MySQL tmpfs và keys/images/cert riêng.
- Source code/remote hiện có: `https://github.com/dtc245200016/GreenShop`. Báo cáo này mô tả thay đổi local chưa push, không tuyên bố remote đã nhận chúng.

## Kết quả các issue

| Issue | Trạng thái | Giải pháp và bằng chứng |
|---|---|---|
| M1-01 README | PASS | Hướng dẫn tiếng Việt: prerequisites, cây thư mục thật, env, cert, DB user, Admin ban đầu, startup, backup, verification, troubleshooting, M2/M3 |
| M1-02 HTTPS | PASS | Script IP/DNS/IPv6 đúng SAN, key 600, key/cert khớp, từ chối overwrite ngầm và host sai; cert/key Main hiện có được giữ nguyên |
| M1-03 Legacy | PASS | Bỏ hai file legacy không được tham chiếu; Compose vẫn dùng `backend/GreenShop.Web/Dockerfile` và `nginx/default.conf`, upstream 8080 |
| M1-04 DB privileges | PASS trong M1 | Web dùng `greenshop_app`, chỉ quyền trong `greenshop.*`; root password không đổi. DDL vẫn cần cho startup migrations; runtime chỉ DML được hoãn |
| M1-05 Ports | PASS | 80/443 là entry point; 3306/5000/8080 bind 127.0.0.1. phpMyAdmin trên trình duyệt VM hoạt động |
| M1-06 Baseline | PASS trong M1 | Secret scan, ignore runtime secrets/data, image build excludes runtime files, TLS/headers, readiness có truy vấn DB; tồn tại non-root/network/firewall ghi rõ bên dưới |
| M1-07 Runtime | PASS | Build, cold start, migrations, SQL, phpMyAdmin, auth/business, persistence, recreate và IP-change recovery đều kiểm thử thật |

## Build và hạ tầng

| Kiểm tra | Kết quả thực tế |
|---|---|
| `docker compose config --quiet` | PASS |
| Host restore/build Release | PASS; 0 warnings, 0 errors; [log](build-release.txt) |
| Docker build/publish | PASS; 0 warnings, 0 errors; image nghiệm thu triển khai đúng image QA |
| EF pending model changes | PASS; không thay đổi model/schema, không thêm migration |
| Bốn service Main | PASS; tất cả running/healthy; [trạng thái](compose-services.txt) |
| Nginx syntax/version/DNS | PASS; version hỗ trợ `resolve`; [nginx -t](nginx-validation.txt) |
| HTTP → HTTPS | PASS; 301, giữ path và query; không redirect loop |
| TLS/SAN/key | PASS; cert khớp IP VM, chưa hết hạn, public key khớp; `curl --cacert nginx/ssl/cert.pem https://192.168.197.128/` trả 200, không dùng `-k` cho phép thử này |
| Headers trên response thật | PASS; nosniff, SAMEORIGIN, strict-origin-when-cross-origin, Server nginx không version; [response đã bỏ cookies](https-response.txt) |
| MySQL / migrations | PASS; 6 migrations, schema tồn tại; app user truy vấn được |
| phpMyAdmin | PASS; Main PHP/mysqli truy vấn MySQL thật trả đúng migration count; GUI QA đăng nhập và xem schema thành công |
| Readiness | PASS; QA DB pause → endpoint 503 và CLI probe nonzero dù web process còn sống; unpause → tự trở lại 200 |
| Cold start | PASS; MySQL tmpfs rỗng → schema, singleton shipping defaults và web; không seed dữ liệu bán hàng |
| Bootstrap | PASS; DB wrapper idempotent; app không đọc `mysql.user`, tạo user hoặc database khác; Admin mới chỉ khi Users rỗng, repeat không thay đổi dữ liệu; shell/TTY giấu password được thử thật |
| QA IP-change recovery | PASS; web chuyển từ IP Docker cấp sang `172.30.250.200`, Nginx giữ nguyên container/start time; HTTPS phục hồi, cả hai cookie vẫn đúng và mọi bảng QA không đổi |
| Main web recreate | PASS; chỉ recreate web, không restart/reload Nginx, không recreate DB để thử proxy; HTTPS 200 và dữ liệu giữ nguyên |
| Persistence Main | PASS; so hash toàn bộ 8 bảng nghiệp vụ trước/sau, ảnh/keys/cert/key và danh tính 3 named volumes giống nhau; 6 migrations không reset |
| Runtime logs | PASS; logs startup đã đọc, không có critical/unhandled exception; logs thô giữ riêng vì có thể chứa metadata vận hành |

## Hồi quy ứng dụng

Các test dưới đây chạy trên dữ liệu **synthetic QA**, không tạo/hủy/sửa/đánh dấu Paid đơn hàng thật.

- Storefront: danh mục, tìm kiếm, pagination, category không hoạt động/rỗng, product details, giá/stock live, HTML escaping.
- Auth: register/login/returnUrl, Admin-only, CSRF/POST-only, ownership, cookie không nâng quyền khi đổi tên; revoke/lock không làm hỏng portal còn lại.
- Cart/checkout: giỏ theo user, merge/update/remove, chống overposting, giá server, số lượng/stock, idempotency và hai khách tranh sản phẩm cuối.
- Orders/Admin: vòng đời 0→3→4→5→1, giá snapshot lịch sử, COD audit, CAS, hủy/hoàn kho đúng một lần, rollback multi-item, thiếu tham chiếu và dữ liệu tổng sai được chặn.
- Payment: cấu hình ngân hàng giả, VietQR render, customer notify vẫn unpaid, Admin xác nhận thủ công đúng actor, shipping 30k/ngưỡng 300k và XLSX download. Không có giao dịch tiền thật; không kiểm thử quét app ngân hàng.
- UI/browser: Admin orders/CRUD/upload/replacement, hộp xác nhận/focus/keyboard, print; customer home/catalog/auth/cart/checkout/history/receipt ở 320/360/768/1440 px; không tràn ngang/JS error trong kiểm thử.
- Main chỉ đọc: trang chủ/catalog/login/assets, HTTPS/header/challenges, SQL/schema, ảnh thật, volume/hash và public screenshots.

Các entry point kiểm thử được đọc trước khi chạy và gắn vào QA độc lập. `tests/m1_acceptance.py` tái sử dụng fixtures/suite hiện có. Dữ liệu giả hiển thị trong screenshot Admin/checkout/phpMyAdmin **không phải dữ liệu kinh doanh Main**.

## Minh chứng ảnh thật

| File | Nguồn và nội dung |
|---|---|
| [Storefront](storefront-main.png) | Main, public GET; ảnh/sản phẩm thật của catalogue, không đăng nhập |
| [Products](products-main.png) | Main, public GET; danh mục/sản phẩm thật |
| [Admin Dashboard](admin-dashboard-qa.png) | QA; tài khoản/tổng đơn và số liệu synthetic |
| [Checkout](checkout-qa.png) | QA; thông tin người nhận/địa chỉ synthetic, chưa submit trong lúc chụp |
| [phpMyAdmin](phpmyadmin-qa.png) | GUI đã đăng nhập vào DB QA; chín bảng gồm migration history, không có form password |

Ảnh được tạo trực tiếp bằng Chromium/Playwright, không dựng mockup hoặc đổi dữ liệu hiển thị để giả PASS. Không lưu `.env`, token, cookie, password, private key, dump hay dữ liệu khách hàng Main trong evidence. Backup, credential test, configs QA có secret và logs thô chỉ ở `/tmp/greenshop-m1`, không đưa vào Git.

## Security và giới hạn còn lại

- PASS: các file tracked/pending public không chứa hai password DB thật; cert/key/env/runtime uploads không tracked. Không reset root/Admin password, đổi role người dùng thật hay xoá volume/data.
- Web chạy root; keys hiện hữu `0:0/700`. Chuyển non-root cần migration ownership có kiểm soát và thử ghi keys/images; không `chown -R` dữ liệu thật trong M1.
- App DB user đã bỏ quyền global của root, nhưng vẫn có DDL schema để EF migrations; tách credentials migration/runtime và runtime DML-only làm ở hardening sau.
- Một bridge `app_net`; chưa tách frontend/backend. Các data/debug ports chỉ loopback.
- Firewall host: NOT TESTED đầy đủ do phiên này không có quyền sudo để đọc rules; không tự thay firewall hoặc dịch vụ host khác.
- SSH tunnel/Windows: NOT TESTED end-to-end; SSH reachable nhưng không có chứng thực tự động, không sửa authorized_keys/password host. Demo phpMyAdmin bằng browser VM đã PASS; hướng dẫn tunnel trong README cho bước kiểm tra từ Windows khi có tài khoản SSH.
- Tự ký là TLS demo/private VM, không phải cấu hình TLS public production. Không thêm CSP/HSTS mạnh hoặc stack monitoring/logging mới.

**Không còn blocker P0 trong phạm vi M1 chạy trên Ubuntu VM đã nghiệm thu.** Các giới hạn trên là hardening/demo bổ sung, không được báo là đã hoàn thành.

## Git và mốc tiếp theo

Branch `main`. Không commit, push, reset, checkout, stash hoặc clean. Bảo toàn các thay đổi UI/business chưa commit từ trước; chỉ chỉnh những file hạ tầng/documentation liên quan và phần deployment/readiness của Program.

Người dùng duyệt thay đổi và tự chốt Commit 1. Mốc tiếp theo được đề xuất: **M2 — Prometheus + Grafana**; chưa triển khai M2/M3 trong lần này.
