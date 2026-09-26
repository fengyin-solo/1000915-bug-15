"""中间液配制业务规则：编辑落库、状态流转、领用扣减、到期失效都收在这里。

数据口径：
- 每条记录以 id + 配制编号 为主键，母液编号、目标浓度等字段只属于这一条配制编号；
- 更新走 update_entry 原地修改并留修订记录，绝不新建/覆盖别的历史记录；
- 登记配制写入配制定容、配制瓶数与配制结论；办理领用按瓶数扣减并追加领用记录；
- 任何读取都会先扫一遍失效日期：失效日期已到且尚未失效的记录自动转为已失效。
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from app.store import store

MODULE = "intermediate"
REQUIRED_FIELDS = ["配制编号", "母液编号", "目标浓度"]
EDITABLE_FIELDS = ["母液编号", "目标浓度", "配制定容", "失效日期", "配制人员"]
STATUS_ORDER = ["待配制", "已配制", "已领用", "已失效"]
ACTION_RULES = {"登记配制": "已配制", "办理领用": "已领用", "标记失效": "已失效"}
NEGATIVE_ACTIONS: list[str] = []
# 已领用、已失效的记录属于历史事实，不允许再改配制内容
LOCKED_STATUSES = ["已领用", "已失效"]

DETAIL_FIELDS = [
    "配制编号", "母液编号", "目标浓度", "配制定容", "配制日期", "失效日期",
    "配制人员", "配制瓶数", "剩余瓶数", "配制结论", "领用记录", "修订记录",
]


def _today() -> date:
    return date.today()


def _parse_day(value: Any) -> date | None:
    """把 YYYY-MM-DD 形式的字段解析成日期；空值或非法值返回 None，不当作已过期。"""
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _to_int(value: Any) -> int | None:
    text = str(value if value is not None else "").strip()
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _sync_display_fields(entry: dict[str, Any]) -> None:
    """让 配制状态 展示字段与内部 status 永远保持同一份口径。"""
    entry["配制状态"] = entry.get("status")
    entry.setdefault("领用记录", [])
    entry.setdefault("修订记录", [])


def _sweep_expired(rows: list[dict[str, Any]]) -> bool:
    """失效日期到了自动转已失效；返回这一轮是否发生过状态变化。"""
    changed = False
    today = _today()
    for entry in rows:
        if entry.get("status") == "已失效":
            continue
        expire_day = _parse_day(entry.get("失效日期"))
        if expire_day is not None and expire_day < today:
            entry["status"] = "已失效"
            entry["pending"] = False
            entry["abnormal"] = False
            entry["配制状态"] = "已失效"
            entry.setdefault("修订记录", []).append(
                {"时间": _now_text(), "动作": "自动失效", "说明": f"失效日期 {expire_day.isoformat()} 已到，系统自动转为已失效"}
            )
            changed = True
    return changed


class IntermediateService:
    def _refresh(self) -> list[dict[str, Any]]:
        rows = store.rows(MODULE)
        if _sweep_expired(rows):
            store.save()
        return rows

    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = self._refresh()
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("配制编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        self._refresh()
        entry = store.find(MODULE, entry_id)
        if entry is not None:
            _sync_display_fields(entry)
        return entry

    def _find_by_code(self, code: str, exclude_id: int | None = None) -> dict[str, Any] | None:
        code = str(code or "").strip()
        for row in store.rows(MODULE):
            if exclude_id is not None and int(row.get("id", 0)) == exclude_id:
                continue
            if str(row.get("配制编号", "")).strip() == code:
                return row
        return None

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        code = str(values["配制编号"]).strip()
        if self._find_by_code(code) is not None:
            return None, [f"配制编号 {code} 已存在，请在原记录上编辑，不能重复登记"]
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry["配制编号"] = code
        for field in DETAIL_FIELDS:
            if field in ("领用记录", "修订记录"):
                entry[field] = []
            elif field in ("配制瓶数", "剩余瓶数"):
                entry[field] = None
            elif field == "配制结论":
                entry[field] = ""
            else:
                entry[field] = str(values.get(field) or "").strip()
        entry["配制日期"] = entry["配制日期"] or _today().isoformat()
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        _sync_display_fields(entry)
        entry["修订记录"].append({"时间": _now_text(), "动作": "登记", "说明": "登记中间液配制申请"})
        rows.append(entry)
        store.save()
        return entry, []

    def update_entry(
        self, entry_id: int, values: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str]:
        """编辑一条配制记录：只改这一条、保留修订痕迹，历史记录不受影响。"""
        self._refresh()
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"中间液 {entry_id} 不存在或已归档"
        if entry.get("status") in LOCKED_STATUSES:
            return None, f"记录已是{entry.get('status')}状态，属于历史事实，配制内容不能再修改"

        changes: list[str] = []
        for field in EDITABLE_FIELDS:
            if field not in values:
                continue
            new_value = str(values.get(field) or "").strip()
            old_value = str(entry.get(field) or "").strip()
            if new_value != old_value:
                changes.append(f"{field}：{old_value or '空'} → {new_value or '空'}")
                entry[field] = new_value

        for field in REQUIRED_FIELDS:
            if not str(entry.get(field) or "").strip():
                return None, f"缺少必填字段：{field}"

        code = str(entry.get("配制编号", "")).strip()
        if self._find_by_code(code, exclude_id=entry_id) is not None:
            return None, f"配制编号 {code} 已被其他记录占用"

        if not changes:
            return entry, "内容没有变化"
        entry.setdefault("修订记录", []).append(
            {"时间": _now_text(), "动作": "编辑", "说明": "；".join(changes)}
        )
        _sync_display_fields(entry)
        store.save()
        return entry, "配制记录修改已保存"

    def run_action(
        self, entry_id: int, action: str, values: dict[str, Any] | None = None
    ) -> tuple[dict[str, Any] | None, str]:
        values = values or {}
        self._refresh()
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"中间液 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于中间液配制可执行范围"

        status = entry.get("status")
        entry.setdefault("领用记录", [])
        entry.setdefault("修订记录", [])

        if action == "登记配制":
            if status != "待配制":
                return None, f"当前为{status}状态，不能重复登记配制"
            volume = str(values.get("配制定容") or "").strip()
            operator = str(values.get("配制人员") or "").strip()
            bottles = _to_int(values.get("配制瓶数"))
            missing = [
                label for label, text in [("配制定容", volume), ("配制人员", operator)] if not text
            ]
            if missing:
                return None, f"请先填写{'、'.join(missing)}再登记配制"
            if bottles is None or bottles <= 0:
                return None, "配制瓶数需为大于 0 的整数"
            entry["配制定容"] = volume
            if operator:
                entry["配制人员"] = operator
            prepare_day = str(values.get("配制日期") or "").strip() or _today().isoformat()
            expire_day = str(values.get("失效日期") or "").strip()
            entry["配制日期"] = prepare_day
            if expire_day:
                entry["失效日期"] = expire_day
                if _parse_day(expire_day) is not None and _parse_day(expire_day) < _today():
                    entry["status"] = "已失效"
                    entry["pending"] = False
                    entry["配制状态"] = "已失效"
                    entry["配制瓶数"] = bottles
                    entry["剩余瓶数"] = bottles
                    entry["配制结论"] = f"配制 {bottles} 瓶，定容 {volume}"
                    entry["修订记录"].append(
                        {"时间": _now_text(), "动作": "登记配制",
                         "说明": f"{operator} 配制 {bottles} 瓶，定容 {volume}；登记时已过失效日期，自动失效"}
                    )
                    store.save()
                    return entry, "配制结论已登记，但失效日期已过，记录自动转为已失效"
            entry["配制瓶数"] = bottles
            entry["剩余瓶数"] = bottles
            entry["配制结论"] = f"配制 {bottles} 瓶，定容 {volume}"
            entry["status"] = "已配制"
            entry["pending"] = True
            entry["abnormal"] = False
            _sync_display_fields(entry)
            entry["修订记录"].append(
                {"时间": _now_text(), "动作": "登记配制",
                 "说明": f"{operator} 配制 {bottles} 瓶，定容 {volume}，配制结论已落库"}
            )
            store.save()
            return entry, "配制结论已登记，状态转为已配制"

        if action == "办理领用":
            if status == "待配制":
                return None, "该中间液尚未登记配制，无瓶可领"
            if status == "已失效":
                return None, "该中间液已失效，不能领用"
            remaining = _to_int(entry.get("剩余瓶数"))
            if remaining is None:
                return None, "配制结论缺失瓶数信息，请先登记配制"
            if remaining <= 0:
                return None, "该中间液已全部领完，不能继续领用"
            bottles = _to_int(values.get("领用瓶数"))
            receiver = str(values.get("领用人员") or "").strip()
            purpose = str(values.get("领用用途") or "").strip()
            if bottles is None or bottles <= 0:
                return None, "领用瓶数需为大于 0 的整数"
            if bottles > remaining:
                return None, f"领用瓶数不能超过剩余瓶数（剩余 {remaining} 瓶）"
            if not receiver:
                return None, "请填写领用人员"
            entry["剩余瓶数"] = remaining - bottles
            entry["领用记录"].append({
                "时间": _now_text(),
                "领用瓶数": bottles,
                "领用人员": receiver,
                "领用用途": purpose,
            })
            entry["status"] = "已领用"
            entry["pending"] = entry["剩余瓶数"] > 0
            entry["abnormal"] = False
            _sync_display_fields(entry)
            left = entry["剩余瓶数"]
            tail = f"，剩余 {left} 瓶" if left > 0 else "，已全部领完"
            entry["修订记录"].append(
                {"时间": _now_text(), "动作": "办理领用",
                 "说明": f"{receiver} 领用 {bottles} 瓶{tail}"}
            )
            store.save()
            return entry, f"领用已登记{tail}"

        # 标记失效
        if status == "已失效":
            return None, "该中间液已是已失效状态"
        entry["status"] = "已失效"
        entry["pending"] = False
        entry["abnormal"] = False
        _sync_display_fields(entry)
        entry["修订记录"].append({"时间": _now_text(), "动作": "标记失效", "说明": "人工标记为已失效"})
        store.save()
        return entry, "中间液已标记失效"
