from fastapi import APIRouter

from app.integrations.llm import get_llm_provider_options

router = APIRouter()


@router.get("/meta")
def get_metadata() -> dict[str, str]:
    return {"name": "API Intelligence Platform", "version": "0.1.0", "status": "scaffold"}


@router.get("/meta/llm-providers")
def get_llm_providers() -> dict[str, object]:
    """List supported providers and key availability without exposing credentials."""
    return get_llm_provider_options()
