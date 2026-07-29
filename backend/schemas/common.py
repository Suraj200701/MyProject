"""Shared response envelopes used across every router."""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class MessageResponse(BaseModel):
    success: bool = True
    message: str


class DataResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T
