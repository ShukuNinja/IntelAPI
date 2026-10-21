"""Health-check API contracts."""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

AssertionType = Literal[
    "status_code",
    "latency_threshold",
    "json_path_equals",
    "header_equals",
    "response_schema",
    "response_time_lte",
]

JSON_TYPES = {"object", "array", "string", "boolean", "integer", "number", "null"}
SCHEMA_KEYWORDS = {
    "$schema",
    "$id",
    "title",
    "description",
    "default",
    "example",
    "examples",
    "type",
    "properties",
    "required",
    "items",
    "enum",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "multipleOf",
    "minLength",
    "maxLength",
    "minItems",
    "maxItems",
    "uniqueItems",
    "minProperties",
    "maxProperties",
    "additionalProperties",
    "allOf",
    "anyOf",
    "oneOf",
    "not",
}


def _validate_schema_document(schema: dict[str, Any], depth: int = 0) -> None:
    if depth > 12:
        raise ValueError("Response schema nesting cannot exceed 12 levels.")
    schema_type = schema.get("type")
    if schema_type is not None and not isinstance(schema_type, (str, list)):
        raise ValueError("Response schema type must be a string or array of strings.")
    if isinstance(schema_type, str) and schema_type not in JSON_TYPES:
        raise ValueError(f"Unsupported response schema type: {schema_type}.")
    if isinstance(schema_type, list) and (
        not schema_type
        or any(not isinstance(item, str) or item not in JSON_TYPES for item in schema_type)
    ):
        raise ValueError("Response schema type lists must contain supported JSON types.")
    if "$ref" in schema:
        raise ValueError("Response schema references are not supported in health assertions.")
    unsupported = set(schema) - SCHEMA_KEYWORDS
    if unsupported:
        raise ValueError("Unsupported response schema keywords: " + ", ".join(sorted(unsupported)))
    required = schema.get("required", [])
    if not isinstance(required, list) or any(not isinstance(item, str) for item in required):
        raise ValueError("Response schema required must be an array of property names.")
    properties = schema.get("properties", {})
    if not isinstance(properties, dict) or any(
        not isinstance(key, str) or not isinstance(value, dict) for key, value in properties.items()
    ):
        raise ValueError("Response schema properties must map names to schema objects.")
    for child in properties.values():
        _validate_schema_document(child, depth + 1)
    items = schema.get("items")
    if items is not None:
        if not isinstance(items, dict):
            raise ValueError("Response schema items must be a schema object.")
        _validate_schema_document(items, depth + 1)
    additional = schema.get("additionalProperties", True)
    if not isinstance(additional, (bool, dict)):
        raise ValueError("additionalProperties must be a boolean or schema object.")
    if isinstance(additional, dict):
        _validate_schema_document(additional, depth + 1)
    for keyword in ("allOf", "anyOf", "oneOf"):
        branches = schema.get(keyword)
        if branches is not None:
            if (
                not isinstance(branches, list)
                or not branches
                or any(not isinstance(branch, dict) for branch in branches)
            ):
                raise ValueError(f"{keyword} must be a non-empty array of schema objects.")
            for branch in branches:
                _validate_schema_document(branch, depth + 1)
    negated = schema.get("not")
    if negated is not None:
        if not isinstance(negated, dict):
            raise ValueError("not must be a schema object.")
        _validate_schema_document(negated, depth + 1)
    enum = schema.get("enum")
    if enum is not None and (not isinstance(enum, list) or len(enum) > 1000):
        raise ValueError("Response schema enum must be an array of at most 1000 values.")
    for keyword in ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf"):
        value = schema.get(keyword)
        if value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool)):
            raise ValueError(f"{keyword} must be a number.")
    if "multipleOf" in schema and schema["multipleOf"] <= 0:
        raise ValueError("multipleOf must be greater than zero.")
    for keyword in (
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
        "minProperties",
        "maxProperties",
    ):
        value = schema.get(keyword)
        if value is not None and (
            not isinstance(value, int) or isinstance(value, bool) or value < 0
        ):
            raise ValueError(f"{keyword} must be a non-negative integer.")
    if "uniqueItems" in schema and not isinstance(schema["uniqueItems"], bool):
        raise ValueError("uniqueItems must be a boolean.")


class ORMRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AssertionDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: AssertionType
    expected: Any
    target: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def validate_definition(self) -> "AssertionDefinition":
        if self.type in {"json_path_equals", "header_equals"} and not self.target:
            raise ValueError(f"target is required for {self.type} assertions.")
        if self.type == "status_code" and (
            not isinstance(self.expected, int)
            or isinstance(self.expected, bool)
            or not 100 <= self.expected <= 599
        ):
            raise ValueError("status_code expected value must be an integer from 100 to 599.")
        if self.type in {"response_time_lte", "latency_threshold"} and (
            not isinstance(self.expected, (int, float))
            or isinstance(self.expected, bool)
            or self.expected < 0
        ):
            raise ValueError("response_time_lte expected value must be a non-negative number.")
        if self.type == "response_schema" and not isinstance(self.expected, dict):
            raise ValueError("response_schema expected value must be a JSON Schema object.")
        if self.type == "response_schema":
            _validate_schema_document(self.expected)
        return self


class HealthCheckCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=160)
    saved_request_id: UUID
    assertions: list[AssertionDefinition] = Field(min_length=1, max_length=20)
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def non_blank_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Name cannot be blank.")
        return value.strip()


class HealthCheckUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str | None = Field(default=None, min_length=1, max_length=160)
    assertions: list[AssertionDefinition] | None = Field(default=None, min_length=1, max_length=20)
    enabled: bool | None = None

    @field_validator("name")
    @classmethod
    def non_blank_name(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("Name cannot be blank.")
        return value.strip() if value is not None else None


class HealthCheckRead(ORMRead):
    id: UUID
    project_id: UUID
    saved_request_id: UUID | None
    name: str
    definition: dict[str, Any]
    enabled: bool
    created_at: datetime
    updated_at: datetime


class AssertionResultRead(ORMRead):
    id: UUID
    execution_id: UUID
    health_check_id: UUID | None
    assertion_type: str
    passed: bool
    expected: Any | None
    actual: Any | None
    message: str
    execution_status: Literal["completed", "failed"] | None = None
    created_at: datetime


class HealthCheckListRead(BaseModel):
    items: list[HealthCheckRead]
    total: int
    limit: int
    offset: int


class HealthCheckRunRead(BaseModel):
    health_check: HealthCheckRead
    execution_id: UUID
    status: Literal["healthy", "degraded", "unavailable"]
    assertions: list[AssertionResultRead]
