# app/schemas/favorite.py
from pydantic import BaseModel

class FavoriteCourseOut(BaseModel):
   
    course_id: str          # 科目代號(編號)
    semester: str | None    # 學期
    department_id: str | None  # 系所(代碼)
    department_name: str | None # 系所(名稱) - 沒有就會是 None/空
    grade: int | None       # 年級
    class_group: str | None # 班組
    name_zh: str            # 課程名稱
    teacher_name: str | None # 教師姓名
    limit_max: int | None   # 上課人數
    credit: int             # 學分數
    required_type: str | None # 課別
    time_text: str | None   # 節次(格式化後)

    # 收藏欄位
    is_favorite: bool = True
