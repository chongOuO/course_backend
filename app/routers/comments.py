
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.comment import Comment
from app.models.course import Course
from app.schemas.comment import CommentCreate, CommentOut
from app.utils.auth import get_current_user

from sqlalchemy import func
from app.models.comment_like import CommentLike
from app.models.comment import Comment


from app.models.course import Course
from app.models.course_like import CourseLike

import logging
logger = logging.getLogger("app.admin")


router = APIRouter(prefix="/comments", tags=["Comments"])

@router.post("/{course_id}", response_model=CommentOut)
def add_comment(course_id: str, data: CommentCreate, db: Session = Depends(get_db), user=Depends(get_current_user)):

    course = db.query(Course).filter(Course.id == course_id).first()
    if not course:
        raise HTTPException(404, "Course not found")

    c = Comment(
        user_id=user.id,
        course_id=course_id,
        content=data.content
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


@router.get("/{course_id}/comments")
def list_comments(course_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    #每則留言的按讚數 + 有沒有按過讚
    like_cnt_sq = (
        db.query(CommentLike.comment_id.label("cid"), func.count().label("like_count"))
        .group_by(CommentLike.comment_id)
        .subquery()
    )

    # 按過讚的留言
    liked_sq = (
        db.query(CommentLike.comment_id.label("cid"))
        .filter(CommentLike.user_id == user.id)
        .subquery()
    )

    rows = (
        db.query(
            Comment,
            func.coalesce(like_cnt_sq.c.like_count, 0).label("like_count"),
            (liked_sq.c.cid.isnot(None)).label("liked_by_me"),
        )
        .outerjoin(like_cnt_sq, like_cnt_sq.c.cid == Comment.id)
        .outerjoin(liked_sq, liked_sq.c.cid == Comment.id)
        .filter(Comment.course_id == course_id)
        .order_by(Comment.created_at.desc())
        .all()
    )

    return [
        {
            "id": c.id,
            "course_id": c.course_id,
            "user_id": c.user_id,
            "content": c.content,
            "created_at": c.created_at,
            "like_count": int(like_count),
            "liked_by_me": bool(liked_by_me),
        }
        for c, like_count, liked_by_me in rows
    ]


@router.post("/{course_id}/like")
def toggle_course_like(course_id: str, db: Session = Depends(get_db), user=Depends(get_current_user)):
    # course 存在性
    if not db.query(Course.id).filter(Course.id == course_id).first():
        raise HTTPException(status_code=404, detail="Course not found")

    like = db.query(CourseLike).filter_by(course_id=course_id, user_id=user.id).first()
    if like:
        db.delete(like)
        liked = False
    else:
        db.add(CourseLike(course_id=course_id, user_id=user.id))
        liked = True

    db.commit()

    like_count = db.query(func.count()).select_from(CourseLike).filter(CourseLike.course_id == course_id).scalar()
    return {"liked": liked, "like_count": like_count}  

@router.post("/comments/{comment_id}/like")
def toggle_comment_like(comment_id: int, db: Session = Depends(get_db), user=Depends(get_current_user)):

    if not db.query(Comment.id).filter(Comment.id == comment_id).first():
        confirm = False
        raise HTTPException(status_code=404, detail="Comment not found")

    like = db.query(CommentLike).filter_by(comment_id=comment_id, user_id=user.id).first()
    if like:
        db.delete(like)
        liked = False
    else:
        db.add(CommentLike(comment_id=comment_id, user_id=user.id))
        liked = True

    db.commit()

    like_count = db.query(func.count()).select_from(CommentLike).filter(CommentLike.comment_id == comment_id).scalar()
    return {"liked": liked, "like_count": like_count}

@router.delete("/comments/{comment_id}")
def delete_comment(comment_id: int, db: Session = Depends(get_db), user=Depends (get_current_user)):
    comment = db.query(Comment).filter(Comment.id == comment_id).first()
    if not comment:
        raise HTTPException(status_code=404, detail="Comment not found")

    if comment.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this comment")

    db.delete(comment)
    db.commit()
    return {"detail": "Comment deleted"}