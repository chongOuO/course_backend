# app/utils/conflict.py
def is_conflict(existing_times, new_times):
    """
    existing_times: List of course_time (already selected)
    new_times: List of course_time (new course)

    判斷是否衝堂：
    1. 星期相同
    2. 節次區間有重疊
    """
    for e in existing_times:
        for n in new_times:
            if e.weekday == n.weekday:
                # start-end 區間重疊（時間衝突）
                if not (e.end_section < n.start_section or n.end_section < e.start_section):
                    return True
    return False
