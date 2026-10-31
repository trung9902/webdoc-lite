# TỔNG HỢP PROMPT KIỂM THỬ TỪ BÀI 1 ĐẾN BÀI 5 (TRÊN 1 TRANG)

---

## 1. PROMPT KỸ THUẬT (CLAUDE OPUS PROMPTS)

* **Bài 1 (Hello Agent)**:
  > *“I have an existing Spring Boot + React application (WebDoc). Add a minimal module: a Spring Boot controller `GET /api/agent/ask?q=...` that forwards the question as JSON to a Python FastAPI service `POST http://localhost:8000/api/v1/ask` (returns `{"answer": "Đã nhận: " + question}`) and returns HTTP 503 with a clear message if the Python service is down; and a React page with an input, a 'Hỏi agent' button, a loading state and an error message. Reuse the existing layout and routing.”*

* **Bài 2 (Sandbox 3 lớp)**:
  > *“Read `gaa/sandbox.py` from the attached project. Explain its three protection layers (AST allow-list, isolated subprocess with rlimits and temp dir, network isolation with unshare -rn). Then expose it as FastAPI `POST /api/sandbox/run {code, data}` with 10 s CPU and 1 GB memory limits, and write unittest cases S1–S7: `sum(range(10)) = 45`; `import os` blocked; `while True` times out; `pd.read_csv` on a URL blocked; `open('/etc/passwd')` blocked; total official sewer length of Đông Sơn = 1204.9 m; a bar chart saved with `save_chart` returns exactly one PNG. Include K6 resource limits test.”*

* **Bài 3 (Data Connector & Gateway)**:
  > *“In the attached GAA project, add a SqlConnector (SQLAlchemy; PostgreSQL, MySQL or SQLite) with list_tables, describe and query(QuerySpec) that builds parameterized read-only SELECT statements with an identifier allow-list, LIMIT 5000 and a 5 s timeout. Change DataGateway so the subject comes from WebDoc JWT claims (sub, org, dept, roles, perms gaa.*, areas, mfa) instead of a fixed role table, add table-level permission `gaa.table.khach_hang`, keep ward and record-status filters and JSON-lines audit. Write tests for: qtdl.gd2 `doan_cong` = 110 rows; capnhat.ht = 16 rows; doichieu.ds = 12 rows; doichieu.ds filtered to Hạc Thành = 0 rows (K10); khaithac.so requesting coordinates = denied (K11); khaithac.so querying `khach_hang` = denied (K5); QuerySpec dataset 'doan_cong; DROP TABLE phuong' = rejected.”*

* **Bài 4 (Multi-Agent Loop & Critic)**:
  > *“In the attached GAA project, extend the orchestrator (graph.py, agents.py, mock_llm.py): add a 'file_search' intent answering metadata questions (format, size, ward, upload date) from the document API; add the business database as a data source; add MockLLM rules for: K1 (Quang Trung completed dossier, HS-01 page 2 cite, HS-09 duplicate); K2 (PNG files under 100 KB = 9 files, 100 KB excluded); K3 (avg monthly water 2025 = 2 087 518.8 m³, peak July); K4 (consumption by ward with 7-bar chart); K7 (deliberately wrong column name on first attempt so Critic returns 'retry', corrected on 2nd attempt); K14 (solve x² - 2y² = 1 with x < 10000 without database access). Keep 3-attempt cap and return trace of steps.”*

* **Bài 5 (Tích hợp WebDoc hoàn chỉnh)**:
  > *“Add a module to the existing WebDoc Spring Boot application. `POST /api/webdoc/ask` reads current user from security context and permission service, signs a 5-minute HS256 JWT (iss=webdoc, aud=gaa, sub, org, dept, roles, perms filtered to gaa.*, areas, mfa) and calls GAA service. `GET /api/v1/gaa/datasets/{dataset}` and `GET /api/v1/gaa/files` verify JWT and reuse existing permission/document services. Add a React page showing answer, planner's query, Vietnamese-formatted table, chart, agent steps trace, and CSV export button (only when gaa.export is granted). Include tests for K8, K9, K12 (revoking gaa.analytics blocks immediately with 403), and K13 (tampered/expired JWT returns 401).”*

---

## 2. BẢNG CÂU HỎI KIỂM THỬ TRÊN GIAO DIỆN (CHO TESTER)

| Bài | Đăng nhập | Câu hỏi nhập vào ô chat | Kết quả cần đạt |
|:---:|:---|:---|:---|
| **B1** | `khaithac.so` | `xin chào` | Trả về: `"Đã nhận: xin chào"` (Tắt Python $\rightarrow$ HTTP 503). |
| **B2** | API sandbox | `RESULT = sum(range(10))` | `result = 45`; chặn `import os`, `open()`; ngắt sau 10s khi `while True`. |
| **B3** | `khaithac.so` | `Liệt kê số điện thoại khách hàng phường Đông Sơn` | **Bị từ chối tại Data Gateway** (thiếu quyền `gaa.table.khach_hang`), có audit. |
| **B3** | `khaithac.so` | `Tọa độ hố ga TN-HG-HT-001 là bao nhiêu?` | **Từ chối**: Cột tọa độ bị che do thiếu `gaa.restricted` + MFA. |
| **B4** | `khaithac.so` | `Tìm hồ sơ hoàn công tuyến cống Quang Trung` | `HS-01` đứng đầu (trang 2); `HS-09` gắn nhãn bản trùng. |
| **B4** | `khaithac.so` | `Tìm các file .png dưới 100 KB` | **9 tệp**; tệp đúng 100 KB (`so_do_tong_the.png`) không được tính. |
| **B4** | `qtdl.gd2` | `Lượng nước tiêu thụ trung bình theo tháng năm 2025` | **2 087 518,8 m³/tháng**; tháng 7 cao nhất: **2 413 061 m³**. |
| **B4** | `qtdl.gd2` | `So sánh sản lượng nước tiêu thụ các phường, vẽ biểu đồ` | Đông Sơn cao nhất **4 911 241 m³**; Quảng Phú thấp nhất **2 504 408 m³**; 7 cột. |
| **B4** | `khaithac.so` | `Giải phương trình x^2 - 2y^2 = 1, tìm các nghiệm nguyên dương với x < 10000` | Ra 5 cặp: `(3,2), (17,12), (99,70), (577,408), (3363,2378)` (Không vào CSDL). |
| **B5** | `qtdl.gd2` | `Tổng chiều dài cống từ D600 trở lên theo phường và vật liệu` | 7 phường: **9 378,5 m** (93 đoạn; Hàm Rồng dài nhất **2 024,1 m**), có biểu đồ, nút CSV. |
| **B5** | `doichieu.ds` | `Tổng chiều dài cống từ D600 trở lên theo phường và vật liệu` | Chỉ thấy Đông Sơn: **1 008,8 m** (10 đoạn). |
| **B5** | `khaithac.so` | *(Quản trị thu hồi quyền `gaa.analytics` trên WebDoc)* hỏi lại câu cống | **Bị từ chối ngay lập tức (HTTP 403)**, không cần sửa GAA hay khởi động lại. |

---

## 3. LỆNH CHẠY TEST TỰ ĐỘNG (TERMINAL)

```powershell
# Bài 2: Test Sandbox 7 ca S1–S7 & Test Defense-in-depth (Fault Injection)
.\.venv\Scripts\python.exe -m unittest tests.test_sandbox tests.test_defense_in_depth tests.test_sandbox_api -v

# Bài 3: Test Data Gateway, RBAC/ABAC & SQL Injection (G1–G7, K5, K10, K11)
.\.venv\Scripts\python.exe -m unittest tests.test_data_gateway -v

# Bài 1 & 5: Test WebDoc Backend Java (Xác thực, phân quyền, tài liệu, JWT)
cd backend; .\gradlew.bat test; cd ..
```
