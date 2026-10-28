"""Pydantic 请求模型（响应体由路由层手工构造，便于随前端灵活迭代）。"""
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------- 儿童端：打卡提交 ----------
class SubmitItem(BaseModel):
    task_id: int = Field(..., gt=0, description="家务 ID")
    quantity: int = Field(1, ge=1, le=20, description="打卡次数，默认 1")


class SubmitRequest(BaseModel):
    items: List[SubmitItem] = Field(..., min_length=1, description="至少一项家务")


# ---------- 家长端：PIN ----------
class PinVerify(BaseModel):
    pin: str = Field(..., pattern=r"^\d{4}$", description="4 位数字 PIN")


class PinChange(BaseModel):
    old_pin: str = Field(..., pattern=r"^\d{4}$")
    new_pin: str = Field(..., pattern=r"^\d{4}$")


# ---------- 家长端：任务 ----------
class TaskCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=20)
    pinyin: Optional[str] = Field(None, max_length=100, description="缺省时自动生成带声调拼音")
    icon: str = Field("🧹", max_length=16)
    price: float = Field(..., ge=0.01, le=100, description="单价（元）")
    daily_limit: Optional[int] = Field(None, ge=1, le=20, description="每日上限，空=不限")
    sort_order: Optional[int] = Field(None, ge=0)


class TaskUpdate(BaseModel):
    """局部更新：仅传入的字段会被修改（exclude_unset 语义）。"""
    name: Optional[str] = Field(None, min_length=1, max_length=20)
    pinyin: Optional[str] = Field(None, max_length=100)
    icon: Optional[str] = Field(None, max_length=16)
    price: Optional[float] = Field(None, ge=0.01, le=100)
    daily_limit: Optional[int] = Field(None, ge=1, le=20)
    sort_order: Optional[int] = Field(None, ge=0)
    is_active: Optional[bool] = None


# ---------- 家长端：结算 ----------
class SettlementCreate(BaseModel):
    method: str = Field(..., min_length=1, max_length=20, description="支付宝/微信/现金/玩具兑换…")
    amount: float = Field(..., ge=0.01, le=10000, description="结算金额（元）")
    note: Optional[str] = Field(None, max_length=100, description="备注，如：买了乐高")
