from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, field_validator

import distributor_client
from auth_routes import get_current_user

router = APIRouter(tags=["bom"])


class BomItem(BaseModel):
    part_number: str = Field(min_length=1, max_length=150)
    quantity: int = Field(default=1, ge=1, le=1_000_000)
    reference: str = Field(default="", max_length=500)
    description: str = Field(default="", max_length=500)

    @field_validator("part_number")
    @classmethod
    def clean_part_number(cls, value: str) -> str:
        return value.strip()


class BomSearchRequest(BaseModel):
    items: list[BomItem] = Field(min_length=1, max_length=50)
    providers: list[Literal["mouser", "digikey"]] = Field(default=["mouser", "digikey"], min_length=1)


@router.post("/bom/search")
def search_bom(body: BomSearchRequest, current_user: dict = Depends(get_current_user)):
    items = [item.model_dump() for item in body.items]
    results, provider_errors = distributor_client.search_bom(items, list(dict.fromkeys(body.providers)))
    return {"items": results, "provider_errors": provider_errors}
