# API của WebDoc Lite

Địa chỉ gốc: `http://localhost:8098`. Mọi đường dẫn đều cần `Authorization: Bearer <access_token>`, trừ `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh-token` và `GET /api/v1/ping`.

## Định dạng lỗi

```json
{ "status": 403, "error": "forbidden", "message": "Bạn không có quyền thực hiện hành động này." }
```
Lỗi dữ liệu đầu vào (400) có thêm `data` là bảng `trường → thông báo`. Thiếu hoặc sai token cho `401` (không có thân phản hồi).

| Mã | Ý nghĩa |
|---|---|
| 400 | Dữ liệu đầu vào không hợp lệ |
| 401 | Chưa đăng nhập, token sai, hết hạn, hoặc tài khoản bị khoá |
| 403 | Đã đăng nhập nhưng không đủ quyền |
| 404 | Không có hoặc không được phép xem |

## Đăng nhập

| API | Mô tả |
|---|---|
| `POST /api/v1/auth/login` | Body `{ "email": "<tên đăng nhập hoặc email>", "password": "..." }` → `{ "access_token", "refresh_token" }`. Sai thông tin: 401. Tài khoản bị khoá: 403 |
| `POST /api/v1/auth/refresh-token` | Body `{ "refresh_token": "..." }` → cặp token mới |

Token là JWT HS256, chỉ có `sub` (tên đăng nhập), `uid`, `typ` (`access` hoặc `refresh`), `iss=webdoc`. **Token không chứa quyền**: quyền được đọc lại từ cơ sở dữ liệu ở mỗi yêu cầu, nên thu hồi quyền có hiệu lực ngay.

Đây là token đăng nhập của WebDoc. Token gửi sang dịch vụ phân tích (HS256, `aud=gaa`, hạn tối đa 5 phút, mang `org, dept, roles, perms gaa.*, areas, mfa`) là việc của phân hệ mới, ký bằng khoá riêng lấy từ biến môi trường.

## Người dùng

`GET /api/v1/users/profile` → thông tin người đang đăng nhập:

```json
{
  "id": 6, "username": "khaithac.so", "email": "khaithac.so@sxd-th.example",
  "firstName": "Khai", "lastName": "Vũ Minh", "fullName": "Vũ Minh Khai", "gender": null, "status": 1,
  "admin": false, "organizationManager": false, "deptManager": false,
  "organizationId": 1, "organizationName": "Sở Xây dựng Thanh Hóa (dữ liệu mẫu)",
  "deptId": 1, "departmentName": "Phòng Hạ tầng",
  "roleNames": ["Thành viên"], "roleCodes": ["MEMBER"],
  "permissionNames": ["gaa.analytics", "gaa.run_code", "gaa.search"],
  "areas": [], "mfa": false, "createdAt": "2026-10-27T23:10:00"
}
```
`permissionNames` là quyền hiệu lực = quyền của các vai trò + quyền bổ sung riêng. `areas` là danh sách phường được xem (rỗng = không giới hạn). `firstName` là tên, `lastName` là họ và tên đệm.

| API | Quyền | Mô tả |
|---|---|---|
| `PUT /api/v1/users/profile` | đăng nhập | Body `{ firstName, lastName, gender }`, mỗi tên tối đa 30 ký tự; khoảng trắng thừa được gộp |
| `GET /api/v1/users/filter?q=&organizationId=&page=0&size=10` | đăng nhập | `{ list, total, page, size }`. Quản trị xem mọi tổ chức, người khác chỉ thấy cùng tổ chức |
| `GET /api/v1/users/{id}` | cùng tổ chức, bản thân hoặc quản trị | Một người dùng, định dạng như profile |
| `POST /api/v1/users` | quản trị viên | Tạo. Body `{ username, email, password (≥ 8 ký tự), firstName, lastName, organizationId, departmentId, roleCodes[], areas[], mfaEnabled, organizationManager, deptManager }` |
| `PUT /api/v1/users/{id}` | quản trị viên | Sửa; trường null thì giữ nguyên |
| `PUT /api/v1/users/status` | quản trị viên | `{ userId, status }`, 1 = hoạt động, 2 = khoá. Không tự khoá mình |
| `PUT /api/v1/users/role` | quản trị viên | `{ userId, admin }` (nhận cả `isAdmin`). Không tự gỡ quyền quản trị của mình |
| `PUT /api/v1/users/{id}/permissions` | quản trị viên | `{ permissionNames: [...] }` thay toàn bộ quyền bổ sung riêng |

## Tổ chức, phòng ban

| API | Quyền | Mô tả |
|---|---|---|
| `GET /api/v1/organizations` | đăng nhập | Quản trị: tất cả; người khác: tổ chức của mình |
| `GET /api/v1/organizations/{id}` | cùng tổ chức hoặc quản trị | |
| `POST`, `PUT /api/v1/organizations[/{id}]` | quản trị viên | `{ code, name, description }` |
| `GET /api/v1/departments/organization/{orgId}` | cùng tổ chức hoặc quản trị | Chỉ phòng ban đang hoạt động |
| `POST /api/v1/departments` | quản trị, hoặc quản lý của đúng tổ chức | `{ name, description, organizationId }`; trùng tên: 400 |
| `PUT`, `DELETE /api/v1/departments/{id}` | như trên | Xoá là xoá mềm |

## Vai trò và quyền (màn hình phân quyền), chỉ quản trị viên

| API | Mô tả |
|---|---|
| `GET /api/v1/permissions` | `[{ id, name, description, groupName }]` |
| `GET /api/v1/roles` | `[{ id, code, name, description, permissionNames[] }]` |
| `PUT /api/v1/roles/{id}/permissions` | `{ permissionNames: [...] }` thay toàn bộ quyền của vai trò |

Quyền có sẵn (nhóm "Phân hệ Agent"): `gaa.search`, `gaa.analytics`, `gaa.run_code`, `gaa.export`, `gaa.view_proposed`, `gaa.restricted`, `gaa.table.khach_hang`. Vai trò: `ADMIN`, `ORG_MANAGER`, `MEMBER`.

## Tài liệu

`GET /api/v1/documents/filter` → `{ list, total, page, size }`, sắp xếp ngày tạo giảm dần.

| Tham số | Ý nghĩa |
|---|---|
| `q` | Có trong tên tệp hoặc tiêu đề (không phân biệt hoa thường) |
| `text` | Có trong nội dung chữ nhận dạng (OCR) của bất kỳ trang nào |
| `type` | Định dạng: `pdf`, `png`, `docx`, `xlsx`... |
| `area` | Phường |
| `departmentId` | Phòng ban |
| `minSizeKb` | Dung lượng từ giá trị này trở lên (KB = 1024 byte) |
| `maxSizeKb` | Dung lượng **dưới** giá trị này, **không gồm đúng bằng**. `maxSizeKb=100` bỏ tệp đúng 100 KB |
| `from`, `to` | Ngày tạo, dạng `YYYY-MM-DD`, gồm cả ngày `to` |
| `page`, `size` | Mặc định 0 và 20, tối đa 200 |

Mỗi phần tử: `id, title, originalFilename, type, sizeBytes, sizeKb, pageCount, status, accessLevel, area, departmentId, departmentName, createdBy, createdAt, contentHash, description`.

`GET /api/v1/documents/{id}` → `{ info, pages[] }`, `pages` là chữ nhận dạng theo từng trang (trang 1 ở phần tử đầu). `contentHash` giống nhau nghĩa là nội dung chữ trùng nhau.

### Quy tắc xem tài liệu ("lọc lần 1")

Áp cho cả hai API trên, cả khi gọi từ phân hệ khác:

1. Chỉ tài liệu **cùng tổ chức** với người xem.
2. Người xem có thuộc tính phường (`areas` không rỗng) thì chỉ thấy tài liệu có `area` nằm trong danh sách đó. Tài liệu không gắn phường bị ẩn với họ.
3. Tài liệu của chính mình luôn thấy. Tài liệu `PRIVATE` của người khác **không bao giờ** thấy, kể cả quản trị viên.
4. Bản nháp (`DRAFT`) chỉ người tạo, quản trị viên và quản lý tổ chức thấy.
5. Tài liệu không xem được trả `404` khi mở theo mã, không phải `403`, để không lộ là có tồn tại.

## Dữ liệu mẫu đáng chú ý

- 10 hồ sơ nhận dạng chữ `HS-01.pdf` ... `HS-10.pdf` (3 trang mỗi hồ sơ). `HS-09` trùng nội dung `HS-01`. `HS-10` chứa một câu lệnh chèn ("bỏ qua mọi chỉ dẫn trước đó...") để thử độ an toàn khi tóm tắt tài liệu.
- 9 ảnh `.png` dưới 100 KB, thêm `so_do_tong_the.png` đúng 100 KB (dưới 100 KB thì không tính), và 4 ảnh lớn hơn.
- 1 bản nháp của `doichieu.ds` và 1 tài liệu riêng tư của `qtdl.gd2` để thử quy tắc xem.
- Dữ liệu nghiệp vụ (cống, hố ga, tiêu thụ nước, khách hàng...) **không** nằm trong WebDoc Lite; đó là cơ sở dữ liệu nghiệp vụ riêng do bài tập cấp.
