# Dịch vụ Agent Python + sandbox (cần Linux cho rlimit và unshare -rn).
#
# docker build -t webdoc-agent .
# Kiểm thử:  docker run --rm --security-opt seccomp=unconfined webdoc-agent python -m unittest discover -s tests -v
# Chạy API:  docker run --rm -p 8000:8000 --security-opt seccomp=unconfined webdoc-agent
#
# seccomp=unconfined để `unshare -rn` tạo được user/network namespace bên trong container;
# thiếu cờ này sandbox vẫn chạy nhưng network_isolated = false (chỉ còn lớp AST và rlimit).
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY agent_service.py .
COPY gaa/ gaa/
COPY tests/ tests/
COPY data/ data/

EXPOSE 8000
CMD ["uvicorn", "agent_service:app", "--host", "0.0.0.0", "--port", "8000"]
