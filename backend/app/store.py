"""数据仓库：启动时从本地数据文件载入，写操作后落盘。

示例数据来自 ``app.seed``；首次启动或数据文件不存在时使用示例数据并写一份数据文件，
之后以数据文件为准，保证登记、编辑、状态流转在服务重启（第二天再打开）后仍然保留。
真实项目里这里会换成数据库访问层；当前实现只依赖标准库。
"""
from __future__ import annotations

import json
import os
import threading
from typing import Any

from app.seed import SEED_ROWS

DATA_FILE = os.environ.get(
    "LAB_DATA_FILE",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data.json"),
)


class Store:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._tables = self._load()

    def _load(self) -> dict[str, list[dict[str, Any]]]:
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, encoding="utf-8") as handle:
                    saved = json.load(handle)
                if isinstance(saved, dict):
                    # 数据文件只覆盖它已有的模块，新模块仍用示例数据补齐
                    tables = {name: [dict(row) for row in rows] for name, rows in SEED_ROWS.items()}
                    for name, rows in saved.items():
                        if isinstance(rows, list):
                            tables[name] = [dict(row) for row in rows if isinstance(row, dict)]
                    return tables
            except (OSError, json.JSONDecodeError):
                # 数据文件损坏时回退到示例数据，避免服务起不来
                pass
        return {name: [dict(row) for row in rows] for name, rows in SEED_ROWS.items()}

    def _save(self) -> None:
        """把当前全量数据原子落盘，避免写一半被读成空文件。"""
        temporary = f"{DATA_FILE}.tmp"
        with open(temporary, "w", encoding="utf-8") as handle:
            json.dump(self._tables, handle, ensure_ascii=False, indent=2)
        os.replace(temporary, DATA_FILE)

    def module_names(self) -> list[str]:
        return sorted(self._tables)

    def rows(self, module: str) -> list[dict[str, Any]]:
        return self._tables.setdefault(module, [])

    def find(self, module: str, entry_id: int) -> dict[str, Any] | None:
        for row in self.rows(module):
            if int(row.get("id", 0)) == entry_id:
                return row
        return None

    def add(self, module: str, entry: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self.rows(module).append(entry)
            self._save()
        return entry

    def save(self) -> None:
        """业务层在直接改完行内字段后调用，统一落盘。"""
        with self._lock:
            self._save()

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
