from fastapi import APIRouter

router = APIRouter()

@router.get("/meta")
def get_metadata() -> dict[str, str]:
    return {"name": "API Intelligence Platform", "version": "0.1.0", "status": "scaffold"}
