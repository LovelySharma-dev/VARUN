from typing import Any


def calculate_iou(
    a: Any,
    b: Any,
) -> float:

    ax1 = a.x
    ay1 = a.y
    ax2 = a.x + a.width
    ay2 = a.y + a.height

    bx1 = b.x
    by1 = b.y
    bx2 = b.x + b.width
    by2 = b.y + b.height

    ix1 = max(ax1, bx1)
    iy1 = max(ay1, by1)
    ix2 = min(ax2, bx2)
    iy2 = min(ay2, by2)

    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)

    intersection = iw * ih

    if intersection == 0:
        return 0.0

    area_a = a.width * a.height
    area_b = b.width * b.height

    union = area_a + area_b - intersection

    return intersection / union if union else 0.0


def non_max_suppression(
    detections: list[Any],
    iou_threshold: float = 0.5,
) -> list[Any]:

    ordered = sorted(
        detections,
        key=lambda item: item.score,
        reverse=True,
    )

    selected = []

    while ordered:

        current = ordered.pop(0)
        selected.append(current)

        ordered = [
            item
            for item in ordered
            if calculate_iou(
                current,
                item,
            ) < iou_threshold
        ]

    return selected
