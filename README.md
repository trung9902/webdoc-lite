# WebDoc Lite

Bản WebDoc rút gọn, dùng cho bài tập "Hệ tích hợp Agent – Sandbox cho WebDoc". Chỉ gồm những phần bài tập cần kế thừa: đăng nhập, người dùng, tổ chức, phòng ban, vai trò và quyền (RBAC), thuộc tính theo phường (ABAC), danh sách tài liệu có lọc theo phạm vi xem. Toàn bộ dữ liệu là dữ liệu giả lập.

Cố ý **không** có: thanh toán, workflow, bình luận và thông báo, OCR, tìm kiếm AI, tải tệp lên, tích hợp bên ngoài. Bài tập thêm phân hệ "Hỏi đáp và phân tích" vào đây; phân hệ đó chưa được viết sẵn.

## Chạy nhanh

Cần Java 21 và Node 18 trở lên. Không cần cài cơ sở dữ liệu (mặc định dùng H2 lưu thành tệp trong `backend/data/`).

```bash
# Cửa sổ 1: backend (cổng 8098)
cd backend
./gradlew bootRun          # Windows: gradlew.bat bootRun

# Cửa sổ 2: giao diện (cổng 5173)
cd frontend
npm install
npm run dev
```

Mở http://localhost:5173. Lần chạy đầu tiên backend tự nạp dữ liệu mẫu; muốn nạp lại từ đầu thì dừng backend và xoá thư mục `backend/data/`.

## Tài khoản

Mật khẩu tài khoản demo: `Demo@123`. Tài khoản khởi tạo: `admin` / `Admin@123`. Đổi bằng biến môi trường `WEBDOC_DEMO_PASSWORD` và `WEBDOC_ADMIN_PASSWORD` trước lần chạy đầu tiên.

| Tài khoản | Vai trò | Phường | MFA | Quyền gaa.* |
|---|---|---|---|---|
| qtkt.gd2 | Quản trị viên | – | có | tất cả, gồm `gaa.table.khach_hang` |
| qtdl.gd2 | Quản lý tổ chức | – | có | search, analytics, run_code, export, view_proposed, restricted |
| capnhat.ht | Thành viên | Hạc Thành | không | search, analytics, run_code, và `view_proposed` (quyền bổ sung riêng) |
| doichieu.ds | Thành viên | Đông Sơn | không | search, analytics, run_code |
| khaithac.so | Thành viên | không giới hạn | không | search, analytics, run_code |

Đổi quyền ở **Phân quyền** (theo vai trò) hoặc **Quản lý người dùng → Quyền bổ sung** (theo người). Thay đổi có hiệu lực ngay ở yêu cầu kế tiếp, không cần đăng nhập lại.

Muốn tự tạo các tài khoản và quyền bằng tay thay vì dùng dữ liệu mẫu: đặt `WEBDOC_SEED_DEMO=false` rồi xoá `backend/data/`. Khi đó chỉ còn tài khoản `admin`, 3 vai trò và 7 quyền `gaa.*` chưa gán cho ai.

## Cấu trúc

```
backend/    Spring Boot 3.2, Java 21
  config/   bảo mật, JWT đăng nhập, xử lý lỗi
  domain/   các bảng dữ liệu
  repo/     truy vấn
  service/  nghiệp vụ (PermissionService, DocumentService là hai lớp phân hệ mới nên dùng lại)
  web/      các API (controller) và kiểu dữ liệu vào/ra (Dtos)
  seed/     dữ liệu mẫu
frontend/   React 18, Vite, Ant Design 5 (giao diện theo bản WebDoc đầy đủ: sidebar có menu con, theme đỏ rượu)
  menu.jsx  danh sách trang duy nhất: sinh cả menu lẫn đường dẫn
  theme/    màu, 4 giao diện (đổi ở menu tài khoản), CSS chung
docs/       API.md, công cụ kiểm thử giao diện (docs/e2e)
```

## Thêm một trang mới (ví dụ "Hỏi đáp và phân tích")

1. Viết component trong `frontend/src/pages/`.
2. Thêm một phần tử vào mảng `pages` trong `frontend/src/menu.jsx`, ví dụ:
   ```jsx
   { path: '/agent', label: 'Hỏi đáp và phân tích', icon: <RobotOutlined />, element: <AgentPage />,
     visible: (me, can) => can('gaa.search') || can('gaa.analytics') }
   ```
   `visible` vừa ẩn menu vừa chặn người gõ thẳng đường dẫn (hiện trang 403). Thêm `group: 'admin'` hoặc `group: 'org'` để mục nằm trong menu con "Quản trị viên" / "Đơn vị của tôi".
3. Gọi API qua `api` trong `frontend/src/api/client.js` (đã gắn token và tự làm mới khi hết hạn).

Ẩn menu chỉ để tiện dùng. **Quyền thật luôn do backend kiểm tra.**

## Thêm một API mới

- **Mọi đường dẫn đều phải đăng nhập theo mặc định** (xem `SecurityConfig`), kể cả đường dẫn không bắt đầu bằng `/api/v1`. API mới như `/api/agent/**` hay `/api/webdoc/**` tự được bảo vệ, không cần khai báo thêm.
- Lấy người đang gọi bằng `CurrentUser.username()`, không bao giờ nhận tên người dùng từ tham số yêu cầu.
- Lấy quyền hiệu lực bằng `PermissionService.effective(user)`; lấy tài liệu người đó được xem bằng `DocumentService.search(...)`. Đừng tự truy vấn bảng `documents`, vì sẽ bỏ qua phạm vi xem.
- Cần quyền cho cả phương thức: `@PreAuthorize("hasAuthority('gaa.analytics')")`.

Chi tiết các API, quy tắc xem tài liệu và định dạng lỗi: xem [docs/API.md](docs/API.md).

## Kiểm thử

```bash
cd backend && ./gradlew test        # 15 ca tích hợp: đăng nhập, quyền, thu hồi quyền, phạm vi tài liệu...
cd docs/e2e && node t_lite_ui.js    # giao diện: menu theo vai trò, cột Hành động, ma trận phân quyền
cd docs/e2e && node t_lite_matrix.js
```
Hai tệp trong `docs/e2e` cần Node 22 trở lên (dùng WebSocket có sẵn) và điều khiển Chrome (đường dẫn mặc định `C:/Program Files/Google/Chrome/Application/chrome.exe`, đổi bằng biến `CHROME_PATH`) và cần backend, frontend đang chạy. Lưu ý: `t_lite_matrix.js` tạm bỏ rồi trả lại một quyền của vai trò Thành viên.

## Cấu hình (biến môi trường)

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `WEBDOC_JWT_SECRET` | chuỗi dev | Khoá ký token, từ 32 ký tự. **Bắt buộc đổi khi triển khai thật** |
| `WEBDOC_DB_URL`, `WEBDOC_DB_USER`, `WEBDOC_DB_PASSWORD` | H2 dạng tệp | Muốn dùng PostgreSQL thì đặt URL `jdbc:postgresql://...` |
| `WEBDOC_CORS_ORIGINS` | localhost:5173, 5174 | Các địa chỉ giao diện được gọi API |
| `WEBDOC_SEED_DEMO` | `true` | Nạp tài khoản demo và tài liệu mẫu |
| `VITE_API_URL` (frontend) | `http://localhost:8098` | Địa chỉ backend |

Không commit khoá, mật khẩu thật hay dữ liệu thật vào repo này.
