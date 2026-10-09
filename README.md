# GreenShop - ASP.NET Core MVC E-Commerce Platform

Đồ án môn học / Bài tập lớn: **Triển khai Hệ thống Phần mềm**  
* **Họ và tên:** Đặng Quốc Trung  
* **Mã sinh viên (MSSV):** DTC245200016  
* **Trường:** Đại học Công nghệ Thông tin và Truyền thông Thái Nguyên (ICTU)  

---

## 1. Tổng quan dự án
**GreenShop** là ứng dụng thương mại điện tử chuyên kinh doanh cây cảnh và vật tư trang trí nội thất, được phát triển nhằm đáp ứng yêu cầu của bài tập lớn môn học. Hệ thống mô phỏng đầy đủ các tính năng cốt lõi của một hệ thống e-commerce thực tế:
* Hiển thị danh mục sản phẩm trực quan, tìm kiếm và phân loại cây cảnh.
* Giao diện trang chủ thân thiện, quản lý giỏ hàng linh hoạt.
* Kiến trúc hướng dịch vụ, bảo mật thông tin cấu hình tách biệt hoàn toàn với mã nguồn.

Toàn bộ ứng dụng được **container hóa 100% bằng Docker và Docker Compose**, chạy mượt mà trên môi trường Linux (Ubuntu/VMware), đảm bảo tính nhất quán giữa môi trường phát triển (Local) và môi trường triển khai (Production).

---

## 2. Công nghệ sử dụng (Tech Stack)
* **Backend:** .NET 8 (ASP.NET Core MVC)
* **Database & Management:** MySQL 8.0 kết hợp phpMyAdmin quản lý trực quan qua giao diện web.
* **Frontend:** Bootstrap 5, FontAwesome, HTML5, CSS3, JavaScript.
* **DevOps & Infrastructure:**
  * **Docker & Docker Compose:** Điều phối đa container (App, Database, DB Management).
  * **Nginx:** Đảm nhận vai trò Reverse Proxy, định tuyến lưu lượng truy cập, hỗ trợ HTTPS với chứng chỉ tự ký (Self-signed SSL).

---

## 3. Cấu trúc thư mục dự án
Mã nguồn được tổ chức theo mô hình chuẩn của các ứng dụng doanh nghiệp:

```text
.
├── backend/                     # Mã nguồn chính của ứng dụng .NET 8 MVC
│   ├── Controllers/             # Xử lý luồng nghiệp vụ và điều hướng (HomeController,...)
│   ├── Models/                  # Các entity dữ liệu và ViewModels
│   ├── Views/                   # Giao diện Razor Templates (Home/Index, Shared/_Layout)
│   ├── Dockerfile               # File đa giai đoạn (multi-stage) để build Docker image cho .NET
│   └── GreenShop.Web.csproj     # Tệp cấu hình dự án .NET
├── nginx/                       # Phân vùng cấu hình Web Server & Proxy
│   ├── default.conf             # Cấu hình Reverse Proxy & SSL chuyển hướng HTTP sang HTTPS
│   └── ssl/                     # Thư mục chứa Private Key & Self-signed Certificate
├── .env.example                 # File mẫu khai báo biến môi trường (không chứa mật khẩu thật)
├── docker-compose.yml           # Tệp thiết lập và điều phối multi-container hệ thống
└── README.md                    # Tài liệu giới thiệu dự án