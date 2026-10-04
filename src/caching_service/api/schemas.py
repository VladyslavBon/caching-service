import uuid
from typing import Self

from pydantic import BaseModel, Field, model_validator


class PayloadCreateRequest(BaseModel):
    list_1: list[str] = Field(min_length=1)
    list_2: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_input(self) -> Self:
        if len(self.list_1) != len(self.list_2):
            raise ValueError("list_1 and list_2 must have the same length")
        # Postgres text columns cannot store NUL; rejecting it here gives a clean 422
        # instead of a database error surfacing as a 500.
        if any("\x00" in value for value in (*self.list_1, *self.list_2)):
            raise ValueError("strings must not contain NUL characters")
        return self


class PayloadCreateResponse(BaseModel):
    id: uuid.UUID
    message: str


class PayloadResponse(BaseModel):
    output: str
