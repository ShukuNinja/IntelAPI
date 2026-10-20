from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse, JSONResponse

from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import check_database

settings = get_settings()
configure_logging(settings.log_level)
app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Backend API for the API Intelligence Platform.",
    docs_url=None,
    redoc_url="/redoc" if settings.app_env != "production" else None,
)


@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request,
    exc: HTTPException,
) -> JSONResponse:
    del request

    detail = exc.detail
    if isinstance(detail, dict):
        code = detail.get("code", "INTERNAL_ERROR")
        message = detail.get("message", "The request failed.")
        details = detail.get("details")
    else:
        code = {
            400: "BAD_REQUEST",
            401: "UNAUTHENTICATED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            409: "CONFLICT",
            413: "PAYLOAD_TOO_LARGE",
            422: "VALIDATION_ERROR",
            429: "RATE_LIMITED",
        }.get(exc.status_code, "INTERNAL_ERROR")
        message = str(detail)
        details = None

    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = details

    return JSONResponse(
        status_code=exc.status_code,
        content={"error": error},
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    del request

    details = [
        {
            "field": ".".join(str(part) for part in error["loc"]),
            "issue": error["msg"],
        }
        for error in exc.errors()
    ]

    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "The request is invalid.",
                "details": details,
            }
        },
    )


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui() -> HTMLResponse:
    openapi_url = app.openapi_url
    if openapi_url is None:
        raise HTTPException(
            status_code=404,
            detail="OpenAPI schema is disabled",
        )

    swagger_response = get_swagger_ui_html(
        openapi_url=openapi_url,
        title=f"{app.title} - Swagger UI",
        swagger_ui_parameters={
            "withCredentials": True,
            "persistAuthorization": True,
        },
    )

    body = swagger_response.body
    if isinstance(body, memoryview):
        body = body.tobytes()

    html = body.decode("utf-8")

    csrf_script = """
    <script>
    (() => {
      function readCookie(name) {
        const prefix = name + "=";
        const entry = document.cookie
          .split("; ")
          .find((cookie) => cookie.startsWith(prefix));

        return entry
          ? decodeURIComponent(entry.substring(prefix.length))
          : null;
      }

      const originalFetch = window.fetch;

      window.fetch = function(input, init = {}) {
        const url = typeof input === "string" ? input : input.url;
        const method = (
          init.method ||
          (typeof input !== "string" ? input.method : "GET")
        ).toUpperCase();

        const isApiRequest = url.includes("/api/");
        const isSafeMethod = ["GET", "HEAD", "OPTIONS"].includes(method);

        if (isApiRequest && !isSafeMethod) {
          const token = readCookie("csrf_token");

          if (token) {
            const headers = new Headers(
              init.headers ||
              (typeof input !== "string" ? input.headers : undefined)
            );

            headers.set("X-CSRF-Token", token);

            init = {
              ...init,
              headers,
              credentials: "include",
            };
          }
        }

        return originalFetch.call(this, input, init);
      };
    })();
    </script>
    """

    html = html.replace("</body>", csrf_script + "</body>")

    return HTMLResponse(
        content=html,
        status_code=swagger_response.status_code,
        media_type="text/html",
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-CSRF-Token"],
)
app.include_router(api_router, prefix=settings.api_v1_prefix)


@app.get("/health/live", tags=["health"], include_in_schema=False)
def liveness() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready", tags=["health"], include_in_schema=False)
def readiness() -> dict[str, str]:
    check_database()
    return {"status": "ready"}
