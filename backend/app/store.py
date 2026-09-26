"""数据仓库：进程内读写 + 本地 JSON 落盘。

所有修改在内存字典上原地完成后调用 save() 写入 backend/data/store.json，
刷新页面或重启服务都能读到上一次保存的结果；数据文件不存在时用示例数据起步。
真实项目换成数据库时，只需保持 rows/find/save 这几个方法的口径。
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from app.seed import SEED_ROWS

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_FILE = DATA_DIR / "store.json"


class Store:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._tables: dict[str, list[dict[str, Any]]] = self._load()

    def _load(self) -> dict[str, list[dict[str, Any]]]:
        """优先读落盘文件；文件缺失或损坏时回退到示例数据，保证服务能起。"""
        if DATA_FILE.exists():
            try:
                payload = json.loads(DATA_FILE.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                payload = None
            if isinstance(payload, dict) and isinstance(payload.get("tables"), dict):
                # 以 seed 为底，再用落盘数据整体覆盖，保证后续新增模块也有表
                tables = {name: [dict(row) for row in rows] for name, rows in SEED_ROWS.items()}
                for name, rows in payload["tables"].items():
                    if isinstance(rows, list):
                        tables[name] = [dict(row) for row in rows if isinstance(row, dict)]
                return tables
        return {name: [dict(row) for row in rows] for name, rows in SEED_ROWS.items()}

    def save(self) -> None:
        """把当前全部数据原子写入 JSON 文件，避免写一半被读到。"""
        with self._lock:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            tmp_file = DATA_FILE.with_suffix(".json.tmp")
            tmp_file.write_text(
                json.dumps({"tables": self._tables}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp_file.replace(DATA_FILE)

    def module_names(self) -> list[str]:
        return sorted(self._tables)

    def rows(self, module: str) -> list[dict[str, Any]]:
        return self._tables.setdefault(module, [])

    def find(self, module: str, entry_id: int) -> dict[str, Any] | None:
        for row in self.rows(module):
            if int(row.get("id", 0)) == entry_id:
                return row
        return None

    def overview(self) -> dict[str, object]:
        modules: list[dict[str, object]] = []
        for name in self.module_names():
            rows = self.rows(name)
            modules.append({
                "name": name,
                "created": len(rows),
                "pending": sum(1 for row in rows if row.get("pending")),
                "abnormal": sum(1 for row in rows if row.get("abnormal")),
            })
        cards = [
            {"label": "业务模块", "value": len(modules)},
            {"label": "今日新增", "value": sum(int(item["created"]) for item in modules)},
            {"label": "待处理", "value": sum(int(item["pending"]) for item in modules)},
            {"label": "异常量", "value": sum(int(item["abnormal"]) for item in modules)},
        ]
        return {"cards": cards, "modules": modules}


store = Store()
