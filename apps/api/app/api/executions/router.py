from fastapi import APIRouter, HTTPException, status

from app.api.executions.schemas import ExecutionRequest, ExecutionResponse
from app.api.executions.service import ExecutionError, execute_request


router = APIRouter()


@router.post(
    "/",
    response_model=ExecutionResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute an HTTP request",
    description="Execute an outbound HTTP request and return the captured response.",
)
async def run_execution(
    request: ExecutionRequest,
) -> ExecutionResponse:
    try:
        return await execute_request(request)

    except ExecutionError as exc:
        message = str(exc)

        # Unsafe destinations and invalid target URLs are client-side errors.
        if (
            "blocked" in message.lower()
            or "only http" in message.lower()
            or "must contain a hostname" in message.lower()
            or "embedded credentials" in message.lower()
            or "could not be resolved" in message.lower()
            or "failed destination validation" in message.lower()
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message,
            ) from exc

        # The target API failed, timed out, or exceeded the response-size limit.
        if "timed out" in message.lower():
            error_status = status.HTTP_504_GATEWAY_TIMEOUT
        else:
            error_status = status.HTTP_502_BAD_GATEWAY

        raise HTTPException(
            status_code=error_status,
            detail=message,
        ) from exc