"""SqlConnector — đọc dữ liệu nghiệp vụ (PostgreSQL, MySQL, SQLite) qua SQLAlchemy.

LLM không bao giờ viết SQL: agent chỉ gửi QuerySpec (tập dữ liệu, cột, điều kiện lọc). Connector
  - chỉ nhận tên bảng/cột có trong danh mục cho phép (TableSpec), so khớp chính xác từng chuỗi,
  - dựng SELECT bằng SQLAlchemy Core, mọi giá trị đi qua tham số ràng buộc (bind parameter),
  - luôn LIMIT 5000, quá 5 giây thì huỷ câu lệnh, phiên làm việc chỉ đọc.
Tài khoản CSDL vẫn nên chỉ có quyền SELECT: đó là chốt chặn cuối, các biện pháp ở đây là lớp thêm.
"""
from __future__ import annotations

import operator
import time
from dataclasses import dataclass, field

import pandas as pd
import sqlalchemy as sa

MAX_ROWS = 5000
TIMEOUT_S = 5
MAX_IN_VALUES = 1000
ALLOWED_OPS = {"==", "!=", ">", ">=", "<", "<=", "in", "contains", "between"}
_COMPARE = {"==": operator.eq, "!=": operator.ne, ">": operator.gt, ">=": operator.ge,
            "<": operator.lt, "<=": operator.le}
_SCALAR = (str, int, float, bool)


@dataclass
class QuerySpec:
    dataset: str
    columns: list[str] | None = None
    filters: list[dict] = field(default_factory=list)   # {"col","op","value"}


@dataclass(frozen=True)
class TableSpec:
    name: str
    title: str
    description: str
    columns: dict[str, str]                                   # cột được phép -> mô tả
    column_class: dict[str, str] = field(default_factory=dict)  # cột -> "han_che"
    area_col: str = ""                                        # cột phường (lọc ABAC theo areas)
    status_col: str = ""                                      # cột vòng đời bản ghi
    official_status: str = "Chính thức"
    required_perm: str = ""                                   # quyền cấp bảng, VD gaa.table.khach_hang


class QueryRejected(ValueError):
    """QuerySpec chứa tên bảng/cột/phép so sánh/giá trị ngoài danh sách cho phép."""


class QueryTimeout(RuntimeError):
    pass


class SqlConnector:
    def __init__(self, url: str | sa.Engine, tables: list[TableSpec], org: str,
                 timeout_s: float = TIMEOUT_S, max_rows: int = MAX_ROWS) -> None:
        self.engine = url if isinstance(url, sa.Engine) else sa.create_engine(url)
        self.tables = {t.name: t for t in tables}
        self.org = org                       # tổ chức sở hữu CSDL này
        self.timeout_s, self.max_rows = timeout_s, max_rows
        if self.engine.dialect.name == "sqlite":
            sa.event.listen(self.engine, "connect", lambda dbapi_conn, _: dbapi_conn.execute("PRAGMA query_only = ON"))

    # ---- danh mục ---------------------------------------------------------
    def table(self, name: object) -> TableSpec:
        if not isinstance(name, str) or name not in self.tables:
            raise QueryRejected(f"Tập dữ liệu không nằm trong danh sách cho phép: {name!r}")
        return self.tables[name]

    def list_tables(self) -> list[str]:
        existing = set(sa.inspect(self.engine).get_table_names())
        return sorted(n for n in self.tables if n in existing)

    def describe(self, name: str) -> list[dict]:
        """Cột của bảng theo information_schema, chỉ giữ cột trong danh sách cho phép."""
        t = self.table(name)
        dialect = self.engine.dialect.name
        if dialect in ("postgresql", "mysql"):
            schema = "current_schema()" if dialect == "postgresql" else "DATABASE()"
            sql = sa.text("SELECT column_name, data_type, is_nullable FROM information_schema.columns "
                          f"WHERE table_schema = {schema} AND table_name = :t ORDER BY ordinal_position")
            with self.engine.connect() as conn:
                rows = [(r[0], r[1], r[2] == "YES") for r in conn.execute(sql, {"t": t.name})]
        else:  # SQLite không có information_schema
            rows = [(c["name"], str(c["type"]), c["nullable"]) for c in sa.inspect(self.engine).get_columns(t.name)]
        return [{"column": n, "type": typ, "nullable": nullable, "description": t.columns[n]}
                for n, typ, nullable in rows if n in t.columns]

    # ---- truy vấn ---------------------------------------------------------
    def query(self, spec: QuerySpec, enforced: list[dict] = (), columns: list[str] | None = None) -> pd.DataFrame:
        """`enforced`: điều kiện bắt buộc của Data Gateway, AND với điều kiện của agent."""
        t, tbl = self._sa_table(spec.dataset)
        cols = columns if columns is not None else (spec.columns or list(t.columns))
        stmt = (sa.select(*(self._column(t, tbl, c) for c in cols))
                .where(*self._where(t, tbl, list(spec.filters) + list(enforced)))
                .limit(self.max_rows))
        return pd.DataFrame(self._execute(stmt), columns=cols)

    def count_by(self, spec: QuerySpec, enforced: list[dict], col: str) -> dict:
        t, tbl = self._sa_table(spec.dataset)
        c = self._column(t, tbl, col)
        stmt = (sa.select(c, sa.func.count()).where(*self._where(t, tbl, list(spec.filters) + list(enforced)))
                .group_by(c))
        return {k: int(n) for k, n in self._execute(stmt)}

    def _sa_table(self, name: object) -> tuple[TableSpec, sa.TableClause]:
        t = self.table(name)
        return t, sa.table(t.name, *(sa.column(c) for c in t.columns))

    @staticmethod
    def _column(t: TableSpec, tbl: sa.TableClause, col: object) -> sa.ColumnClause:
        if not isinstance(col, str) or col not in t.columns:
            raise QueryRejected(f"Cột không nằm trong danh sách cho phép của {t.name}: {col!r}")
        return tbl.c[col]

    def _where(self, t: TableSpec, tbl: sa.TableClause, filters: list[dict]) -> list:
        out = []
        for f in filters:
            if not isinstance(f, dict):
                raise QueryRejected(f"Điều kiện lọc phải là {{col, op, value}}: {f!r}")
            c, op, val = self._column(t, tbl, f.get("col")), f.get("op"), f.get("value")
            if op not in ALLOWED_OPS:
                raise QueryRejected(f"Phép so sánh không được phép: {op!r}")
            if op == "in":
                if not isinstance(val, list) or len(val) > MAX_IN_VALUES or not all(isinstance(v, _SCALAR) for v in val):
                    raise QueryRejected(f"'in' cần danh sách tối đa {MAX_IN_VALUES} giá trị đơn")
                out.append(c.in_(val))
            elif op == "between":
                if not isinstance(val, list) or len(val) != 2 or not all(isinstance(v, _SCALAR) for v in val):
                    raise QueryRejected("'between' cần đúng 2 giá trị đơn")
                out.append(c.between(*val))
            elif not isinstance(val, _SCALAR):
                raise QueryRejected(f"Giá trị lọc phải là chuỗi hoặc số: {val!r}")
            elif op == "contains":
                out.append(c.contains(str(val), autoescape=True))
            else:
                out.append(_COMPARE[op](c, val))
        return out

    def _execute(self, stmt) -> list:
        with self.engine.connect() as conn:   # thoát khối là rollback: không gì được ghi
            started = time.monotonic()
            self._guard(conn)
            try:
                return conn.execute(stmt).fetchall()
            except sa.exc.OperationalError as e:
                if time.monotonic() - started >= self.timeout_s:
                    raise QueryTimeout(f"Truy vấn quá {self.timeout_s:g} giây, đã huỷ") from e
                raise
            finally:
                if self.engine.dialect.name == "sqlite":
                    conn.connection.driver_connection.set_progress_handler(None, 0)

    def _guard(self, conn: sa.Connection) -> None:
        """Phiên chỉ đọc + giới hạn thời gian, theo từng hệ quản trị."""
        ms = int(self.timeout_s * 1000)
        dialect = self.engine.dialect
        if dialect.name == "postgresql":
            conn.exec_driver_sql("SET TRANSACTION READ ONLY")
            conn.exec_driver_sql(f"SET LOCAL statement_timeout = {ms}")
        elif dialect.name == "mysql":
            conn.exec_driver_sql("SET SESSION TRANSACTION READ ONLY")
            if getattr(dialect, "is_mariadb", False):
                conn.exec_driver_sql(f"SET SESSION max_statement_time = {self.timeout_s:g}")
            else:
                conn.exec_driver_sql(f"SET SESSION MAX_EXECUTION_TIME = {ms}")
        elif dialect.name == "sqlite":
            deadline = time.monotonic() + self.timeout_s
            conn.connection.driver_connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 10_000)
