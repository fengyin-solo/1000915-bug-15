"""中间液配制业务规则：字段编辑、状态流转、领用结论与失效判定都收在这里。

约束：
- 母液编号、目标浓度等字段只挂在各自的配制编号（id）上，编辑只改本条，不碰其它记录；
- 配制/领用结论随动作落库，列表、详情、领用弹窗读到的是同一份数据；
- 失效日期到期后在读取时自动转为「已失效」并落盘；
- 已失效记录只读，历史配制记录不会被新的编辑覆盖。
"""
from __future__ import annotations

from datetime import date
from typing import Any

from app.store import store

MODULE = "intermediate"
# 业务字段：登记时必填
REQUIRED_FIELDS = ["配制编号", "母液编号", "目标浓度"]
# 允许在配制记录上编辑的字段；配制编号是记录身份，不在此列
EDITABLE_FIELDS = ["母液编号", "目标浓度", "配制定容", "配制日期", "失效日期", "配制人员"]
# 配制登记时随结论一起落库的字段
PREPARATION_FIELDS = ["配制定容", "配制日期", "失效日期", "配制人员", "配制结论"]
# 领用登记时随结论一起落库的字段
REQUISITION_FIELDS = ["领用瓶数", "领用人", "领用日期", "领用用途"]

STATUS_PENDING = "待配制"
STATUS_PREPARED = "已配制"
STATUS_RECEIVED = "已领用"
STATUS_EXPIRED = "已失效"
STATUS_ORDER = [STATUS_PENDING, STATUS_PREPARED, STATUS_RECEIVED, STATUS_EXPIRED]

ACTION_RULES = {"登记配制": STATUS_PREPARED, "办理领用": STATUS_RECEIVED, "标记失效": STATUS_EXPIRED}
NEGATIVE_ACTIONS = []


def _today() -> date:
    return date.today()


def _parse_day(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _display_status(entry: dict[str, Any]) -> str:
    """计算一条记录当前应有的状态：已到期的自动失效。"""
    if entry.get("status") != STATUS_EXPIRED:
        expire_day = _parse_day(entry.get("失效日期"))
        if expire_day is not None and expire_day <= _today():
            return STATUS_EXPIRED
    return str(entry.get("status") or STATUS_PENDING)


class IntermediateService:
    def _apply_expiry(self, entry: dict[str, Any]) -> bool:
        """失效日期到期则自动转为已失效；有变更时落库。"""
        current = str(entry.get("status") or "")
        expected = _display_status(entry)
        if current != expected:
            entry["status"] = expected
            entry["pending"] = False
            entry["abnormal"] = False
            return True
        return False

    def _normalize(self, entry: dict[str, Any]) -> dict[str, Any]:
        """对外统一输出：补齐展示字段，状态与列表/详情/弹窗保持同一口径。"""
        self._apply_expiry(entry)
        result = dict(entry)
        result["配制状态"] = result.get("status")
        result["剩余瓶数"] = self._remaining_bottles(entry)
        return result

    @staticmethod
    def _remaining_bottles(entry: dict[str, Any]) -> int | None:
        prepared = entry.get("配制瓶数")
        received = entry.get("累计领用瓶数", 0)
        if prepared in (None, ""):
            return None
        try:
            return max(int(prepared) - int(received or 0), 0)
        except (TypeError, ValueError):
            return None

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        changed = False
        with store._lock:
            rows = store.rows(MODULE)
            for row in rows:
                changed = self._apply_expiry(row) or changed
            if changed:
                store.save()
            filtered = list(rows)
            if keyword:
                filtered = [row for row in filtered if keyword in str(row.get("配制编号", ""))]
            if status:
                filtered = [row for row in filtered if str(row.get("status")) == status]
            total = len(filtered)
            start = max(page - 1, 0) * size
            page_rows = [self._normalize(row) for row in filtered[start:start + size]]
        return page_rows, total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        with store._lock:
            entry = store.find(MODULE, entry_id)
            if entry is None:
                return None
            if self._apply_expiry(entry):
                store.save()
            return self._normalize(entry)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        values = values or {}
        cleaned = {field: str(values.get(field) or "").strip() for field in REQUIRED_FIELDS}
        missing = [field for field, value in cleaned.items() if not value]
        if missing:
            return None, missing
        code = cleaned["配制编号"]
        with store._lock:
            if any(str(row.get("配制编号") or "") == code for row in store.rows(MODULE)):
                return None, [f"配制编号 {code} 已存在"]
            entry: dict[str, Any] = {"id": self._next_id()}
            # 业务字段只属于这条配制编号；登记时可选带配制信息
            for field in REQUIRED_FIELDS:
                entry[field] = cleaned[field]
            for field in EDITABLE_FIELDS:
                if field in REQUIRED_FIELDS:
                    continue
                entry[field] = str(values.get(field) or "").strip()
            entry["配制瓶数"] = self._to_int(values.get("配制瓶数"))
            entry["累计领用瓶数"] = 0
            entry["领用记录"] = []
            entry["配制结论"] = ""
            entry["status"] = STATUS_PENDING
            entry["pending"] = True
            entry["abnormal"] = False
            store.add(MODULE, entry)
            return self._normalize(entry), []

    def update_entry(
        self, entry_id: int, values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        """编辑一条配制记录：只更新本条 id 上允许修改的字段，历史记录互不影响。"""
        values = values or {}
        with store._lock:
            entry = store.find(MODULE, entry_id)
            if entry is None:
                return None, f"中间液 {entry_id} 不存在或已归档"
            self._apply_expiry(entry)
            if entry["status"] == STATUS_EXPIRED:
                return None, "该中间液已失效，历史配制记录不允许再编辑"
            if entry["status"] == STATUS_RECEIVED:
                return None, "该中间液已进入领用环节，配制记录不允许再修改"
            # 母液编号唯一性只与其它配制编号比较，不影响本条
            mother = str(values.get("母液编号") or "").strip()
            if mother:
                for row in store.rows(MODULE):
                    if int(row.get("id", 0)) != entry_id and str(row.get("母液编号") or "") == mother:
                        return None, f"母液编号 {mother} 已挂在其它配制记录上"
            for field in EDITABLE_FIELDS:
                if field in values:
                    entry[field] = str(values.get(field) or "").strip()
            if "配制瓶数" in values:
                bottles = self._to_int(values.get("配制瓶数"))
                if bottles is not None:
                    received = int(entry.get("累计领用瓶数") or 0)
                    if bottles < received:
                        return None, f"配制瓶数不能小于已领用瓶数 {received}"
                    entry["配制瓶数"] = bottles
            store.save()
            return self._normalize(entry), ""

    def run_action(
        self, entry_id: int, action: str, values: dict[str, Any] | None = None
    ) -> tuple[dict[str, Any] | None, str]:
        values = values or {}
        with store._lock:
            entry = store.find(MODULE, entry_id)
            if entry is None:
                return None, f"中间液 {entry_id} 不存在或已归档"
            if action not in ACTION_RULES:
                return None, f"动作「{action}」不属于中间液配制可执行范围"
            self._apply_expiry(entry)
            status = str(entry.get("status") or STATUS_PENDING)
            if status == STATUS_EXPIRED:
                return None, "该中间液已失效，不能再办理配制或领用"

            if action == "登记配制":
                if status != STATUS_PENDING:
                    return None, f"当前状态为「{status}」，不能重复登记配制"
                # 配制结论与定容体积一并落库
                for field in PREPARATION_FIELDS:
                    if field in values:
                        entry[field] = str(values.get(field) or "").strip()
                bottles = self._to_int(values.get("配制瓶数"))
                if bottles is None and entry.get("配制瓶数") in (None, ""):
                    return None, "请填写本次配制瓶数后再登记"
                if bottles is not None:
                    entry["配制瓶数"] = bottles
                entry["status"] = STATUS_PREPARED
                entry["pending"] = True
                entry["abnormal"] = False
                message = "配制结论已保存，中间液状态更新为已配制"

            elif action == "办理领用":
                if status != STATUS_PREPARED:
                    return None, f"当前状态为「{status}」，只有已配制的中间液可以办理领用"
                count = self._to_int(values.get("领用瓶数"))
                if count is None or count <= 0:
                    return None, "请填写正确的领用瓶数"
                remaining = self._remaining_bottles(entry)
                if remaining is not None and count > remaining:
                    return None, f"领用瓶数不能大于剩余瓶数 {remaining}"
                record = {
                    "领用瓶数": count,
                    "领用人": str(values.get("领用人") or "").strip(),
                    "领用日期": str(values.get("领用日期") or "").strip() or _today().isoformat(),
                    "领用用途": str(values.get("领用用途") or "").strip(),
                }
                if not record["领用人"]:
                    return None, "请填写领用人"
                entry.setdefault("领用记录", []).append(record)
                entry["累计领用瓶数"] = int(entry.get("累计领用瓶数") or 0) + count
                # 余量为 0 才进入已领用；还有余量时保持可继续领用
                entry["status"] = (
                    STATUS_RECEIVED if self._remaining_bottles(entry) == 0 else STATUS_PREPARED
                )
                entry["pending"] = entry["status"] != STATUS_RECEIVED
                entry["abnormal"] = False
                message = (
                    "领用登记已完成，瓶数余量为 0，状态更新为已领用"
                    if entry["status"] == STATUS_RECEIVED
                    else f"领用登记已保存，剩余瓶数 {entry['配制瓶数'] - entry['累计领用瓶数']}"
                )

            else:  # 标记失效
                entry["status"] = STATUS_EXPIRED
                entry["pending"] = False
                entry["abnormal"] = False
                message = "中间液已标记失效"

            store.save()
            return self._normalize(entry), message

    def _next_id(self) -> int:
        return max((int(row.get("id", 0)) for row in store.rows(MODULE)), default=0) + 1

    @staticmethod
    def _to_int(value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
