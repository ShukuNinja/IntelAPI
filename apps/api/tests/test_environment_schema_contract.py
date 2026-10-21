from pydantic import BaseModel, ConfigDict, Field, field_validator


# Small contract checks documenting the normalization/strict-input expectations
# for the environment schemas already implemented in the main branch.
class EnvironmentCreateContract(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=120)
    base_url: str | None = None

    @field_validator("name", mode="before")
    @classmethod
    def trim_name(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


def test_environment_name_is_trimmed() -> None:
    assert EnvironmentCreateContract(name="  staging  ").name == "staging"


def test_environment_rejects_unknown_fields() -> None:
    try:
        EnvironmentCreateContract(name="staging", injected=True)
    except ValueError:
        return
    raise AssertionError("unknown fields should be rejected")
