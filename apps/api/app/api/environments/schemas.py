import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EnvironmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    base_url: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        if not value:
            raise ValueError("Environment name cannot be blank.")
        return value

    @field_validator("base_url")
    @classmethod
    def trim_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class EnvironmentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=120)
    base_url: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is not None and not value:
            raise ValueError("Environment name cannot be blank.")
        return value

    @field_validator("base_url")
    @classmethod
    def trim_base_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class EnvironmentVariableWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value: str
    is_secret: bool = False


class EnvironmentVariableRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    value: str | None
    is_secret: bool
    created_at: datetime
    updated_at: datetime


class EnvironmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    name: str
    base_url: str | None
    created_at: datetime
    updated_at: datetime
    variables: list[EnvironmentVariableRead] = Field(default_factory=list)


class EnvironmentListRead(BaseModel):
    items: list[EnvironmentRead]
    total: int
    limit: int
    offset: int


VARIABLE_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
