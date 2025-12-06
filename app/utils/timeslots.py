
from typing import List, Tuple

def parse_time_slots(time_slots: List[str] | None) -> List[Tuple[int, int]]:
    """
    ["1-1","1-2","3-5"] -> [(1,1),(1,2),(3,5)]
    """
    if not time_slots:
        return []
    out = []
    for s in time_slots:
        s = (s or "").strip()
        if not s:
            continue
        if "-" not in s:
            continue
        a, b = s.split("-", 1)
        try:
            w = int(a)
            sec = int(b)
        except:
            continue
        if 1 <= w <= 7 and 1 <= sec <= 20:
            out.append((w, sec))
    # 去重
    return sorted(set(out))


def compress_slots_to_ranges(slots: List[Tuple[int, int]]):
    """
    [(1,1),(1,2),(1,4),(3,5)] -> [(1,1,2),(1,4,4),(3,5,5)]
    目的是：把同一天連續節次合併成 CourseTime 的 start/end
    """
    if not slots:
        return []
    slots = sorted(set(slots))
    ranges = []
    cur_w, cur_s = slots[0]
    start = end = cur_s

    for w, s in slots[1:]:
        if w == cur_w and s == end + 1:
            end = s
        else:
            ranges.append((cur_w, start, end))
            cur_w = w
            start = end = s
    ranges.append((cur_w, start, end))
    return ranges
