from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


HttpMethod = Literal["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]


class ExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: HttpMethod = "GET"
    url: HttpUrl
    headers: dict[str, str] = Field(default_factory=dict, max_length=50)
    query_params: dict[str, str] = Field(default_factory=dict, max_length=50)
    body: str | None = Field(default=None, max_length=1_000_000)

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


class ExecutionResponse(BaseModel):
    status_code: int
    headers: dict[str, str]
    body: str
    duration_ms: float
    size_bytes: int
    final_url: str