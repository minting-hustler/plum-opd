"""Member routes."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query

from models.schemas import MemberCreate, MemberResponse
from services import firebase_service as fb

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/{member_id}", response_model=MemberResponse)
async def get_member(member_id: str):
    member = fb.get_member_by_id(member_id)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    category_used = fb.get_category_used_ytd(member_id)
    return MemberResponse(**member, category_used_ytd=category_used)


@router.get("/by-uid/{firebase_uid}", response_model=MemberResponse)
async def get_member_by_uid(firebase_uid: str):
    member = fb.get_member_by_uid(firebase_uid)
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    category_used = fb.get_category_used_ytd(member["id"])
    return MemberResponse(**member, category_used_ytd=category_used)


@router.post("", response_model=MemberResponse)
async def create_member(body: MemberCreate):
    existing = fb.get_member_by_uid(body.firebase_uid)
    if existing:
        return MemberResponse(**existing, category_used_ytd={})
    member = fb.create_member(body.model_dump(mode="json"))
    return MemberResponse(**member, category_used_ytd={})
