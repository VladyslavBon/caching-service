import uuid

from fastapi import APIRouter, HTTPException, Response, status

from caching_service.api.deps import PayloadServiceDep, SettingsDep
from caching_service.api.schemas import (
    PayloadCreateRequest,
    PayloadCreateResponse,
    PayloadResponse,
)
from caching_service.core.config import Settings

router = APIRouter()


def _ensure_within_limits(body: PayloadCreateRequest, settings: Settings) -> None:
    # Limits are configurable per deployment, so they are checked against the app's
    # settings rather than hard-coded into the schema.
    if len(body.list_1) > settings.max_list_length:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Lists must contain at most {settings.max_list_length} items",
        )
    longest = max(len(value) for value in (*body.list_1, *body.list_2))
    if longest > settings.max_string_length:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"Strings must be at most {settings.max_string_length} characters long",
        )


@router.post(
    "/payload",
    status_code=status.HTTP_201_CREATED,
    response_model=PayloadCreateResponse,
    responses={status.HTTP_200_OK: {"description": "An identical payload already existed"}},
)
async def create_payload(
    body: PayloadCreateRequest,
    response: Response,
    service: PayloadServiceDep,
    settings: SettingsDep,
) -> PayloadCreateResponse:
    _ensure_within_limits(body, settings)
    result = await service.create(body.list_1, body.list_2)
    if not result.created:
        # Idempotent re-submission: nothing was created, so don't claim 201.
        response.status_code = status.HTTP_200_OK
        return PayloadCreateResponse(id=result.id, message="Payload already exists")
    return PayloadCreateResponse(id=result.id, message="Payload created")


@router.get(
    "/payload/{payload_id}",
    response_model=PayloadResponse,
    responses={status.HTTP_404_NOT_FOUND: {"description": "Unknown payload id"}},
)
async def read_payload(payload_id: uuid.UUID, service: PayloadServiceDep) -> PayloadResponse:
    output = await service.get_output(payload_id)
    if output is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payload not found")
    return PayloadResponse(output=output)


@router.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok"}
