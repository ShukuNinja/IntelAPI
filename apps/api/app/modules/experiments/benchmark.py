"""Deterministic localhost-only research fixture with one documented seeded defect."""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/research-benchmark", tags=["research-benchmark"])


@router.get("/widgets/{widget_id}")
def get_widget(widget_id: int) -> dict[str, int | str]:
    if widget_id == 13:
        # Seeded defect B-001: response id violates the documented integer schema.
        return {"id": str(widget_id), "name": "Seeded defect widget"}
    if widget_id < 1 or widget_id > 1000:
        raise HTTPException(status_code=404, detail="Widget not found.")
    return {"id": widget_id, "name": f"Widget {widget_id}"}
