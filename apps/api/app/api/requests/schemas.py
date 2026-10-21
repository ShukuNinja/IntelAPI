from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
BodyType = Literal["none", "json", "text", "form_urlencoded", "multipart"]


class SavedRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=160)
    method: HttpMethod = "GET"
    url_template: str = Field(min_length=1, max_length=4096)
    collection_id: UUID | None = None
    environment_id: UUID | None = None
    headers: dict[str, str] = Field(default_factory=dict, max_length=50)
    query_params: dict[str, str] = Field(default_factory=dict, max_length=50)
    body: Any | None = None
    body_type: BodyType = "none"

    @field_validator("name", "url_template", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("headers")
    @classmethod
    def validate_headers(cls, value: dict[str, str]) -> dict[str, str]:
        forbidden = {
            "host",
            "content-length",
            "connection",
            "transfer-encoding",
            "cookie",
            "proxy-authorization",
        }
        for key in value:
            if key.lower() in forbidden:
                raise ValueError(f"The {key} header cannot be supplied.")
        return value


class SavedRequestUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=160)
    method: HttpMethod | None = None
    url_template: str | None = Field(default=None, min_length=1, max_length=4096)
    collection_id: UUID | None = None
    environment_id: UUID | None = None
    headers: dict[str, str] | None = Field(default=None, max_length=50)
    query_params: dict[str, str] | None = Field(default=None, max_length=50)
    body: Any | None = None
    body_type: BodyType | None = None

    @field_validator("name", "url_template", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip()
        return value

    @field_validator("headers")
    @classmethod
    def validate_headers(
        cls,
        value: dict[str, str] | None,
    ) -> dict[str, str] | None:
        if value is None:
            return value

        forbidden = {
            "host",
            "content-length",
            "connection",
            "transfer-encoding",
            "cookie",
            "proxy-authorization",
        }
        for key in value:
            if key.lower() in forbidden:
                raise ValueError(f"The {key} header cannot be supplied.")
        return value


class SavedRequestRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    collection_id: UUID | None
    environment_id: UUID | None
    name: str
    method: str
    url_template: str
    headers: dict[str, Any]
    query_params: dict[str, Any]
    body: Any | None
    body_type: str
    created_at: datetime
    updated_at: datetime


class PaginationRead(BaseModel):
    limit: int
    offset: int
    total: int


class SavedRequestListRead(BaseModel):
    items: list[SavedRequestRead]
    pagination: PaginationRead
