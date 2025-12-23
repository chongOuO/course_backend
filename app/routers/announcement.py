from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
from app.models.announcement import Announcement
from app.schemas.announcement import (
    AnnouncementCreate,
    AnnouncementUpdate,
    AnnouncementSummary,
    AnnouncementDetail,
    AnnouncementListOut,
    AnnouncementCategory,
)

from app.utils.auth import require_admin

import logging
logger = logging.getLogger("app.admin")

router = APIRouter(prefix="/announcements", tags=["Announcements"])





from fastapi import Depends, Query
from sqlalchemy.orm import Session

@router.get("", response_model=AnnouncementListOut)
def list_announcements(
    db: Session = Depends(get_db),
    category: AnnouncementCategory | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    keyword: str | None = Query(None),
    include_inactive: bool = Query(False, description="管理者可看下架公告"),
):
    query = db.query(Announcement)  

    if not include_inactive:
        query = query.filter(Announcement.is_active.is_(True))

    if category:
        query = query.filter(Announcement.category == category)

    if keyword:
        query = query.filter(Announcement.title.ilike(f"%{keyword}%"))

    total = query.count()

    rows = (
        query.order_by(Announcement.is_pinned.desc(), Announcement.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    items = [
        AnnouncementSummary(
            id=r.id,
            title=r.title,
            content=r.content,  
            category=r.category,
            created_at=r.created_at,
            is_pinned=r.is_pinned,
        )
        for r in rows
    ]

    return AnnouncementListOut(items=items, total=total, page=page, page_size=page_size)


@router.get("/{announcement_id}", response_model=AnnouncementDetail)
def get_announcement(announcement_id: int, db: Session = Depends(get_db)):
    ann = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not ann:
        raise HTTPException(status_code=404, detail="Announcement not found")
    return ann


# 只有管理者可以新增
@router.post("", response_model=AnnouncementDetail)
def create_announcement(
    body: AnnouncementCreate,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    ann = Announcement(
        title=body.title,
        content=body.content,
        category=body.category,
        is_pinned=body.is_pinned,
        is_active=body.is_active,
        start_at=body.start_at,
        end_at=body.end_at,
        author_id=getattr(admin, "id", None),
    )
    db.add(ann)
    db.commit()
    db.refresh(ann)
    return ann


#只有管理者可以修改
@router.put("/{announcement_id}", response_model=AnnouncementDetail)
def update_announcement(
    announcement_id: int,
    body: AnnouncementUpdate,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    ann = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not ann:
        raise HTTPException(status_code=404, detail="Announcement not found")

    data = body.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(ann, k, v)

    db.commit()
    db.refresh(ann)
    return ann


# 只有管理者可以刪除
@router.delete("/{announcement_id}")
def delete_announcement(
    announcement_id: int,
    db: Session = Depends(get_db),
    admin=Depends(require_admin),
):
    ann = db.query(Announcement).filter(Announcement.id == announcement_id).first()
    if not ann:
        raise HTTPException(status_code=404, detail="Announcement not found")

    db.delete(ann)
    db.commit()
    return {"detail": "deleted"}
