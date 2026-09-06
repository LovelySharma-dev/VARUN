import numpy as np

from varun_phase1_core import Detection


def mask_to_detections(
    mask: np.ndarray,
    probability: np.ndarray | None = None,
    min_area: int = 20,
) -> list[Detection]:
    """
    Convert a binary oil-spill segmentation mask into bounding-box detections.
    """

    mask = np.asarray(mask).astype(bool)

    if mask.ndim != 2:
        raise ValueError(
            f"mask must be 2D, got shape {mask.shape}"
        )

    # Find connected components without requiring OpenCV.
    height, width = mask.shape
    visited = np.zeros_like(mask, dtype=bool)

    detections: list[Detection] = []

    for start_y, start_x in zip(*np.nonzero(mask)):
        if visited[start_y, start_x]:
            continue

        stack = [(int(start_y), int(start_x))]
        visited[start_y, start_x] = True

        min_x = max_x = start_x
        min_y = max_y = start_y
        pixels = 0

        while stack:
            y, x = stack.pop()
            pixels += 1

            min_x = min(min_x, x)
            max_x = max(max_x, x)
            min_y = min(min_y, y)
            max_y = max(max_y, y)

            for ny, nx in (
                (y - 1, x),
                (y + 1, x),
                (y, x - 1),
                (y, x + 1),
            ):
                if (
                    0 <= ny < height
                    and 0 <= nx < width
                    and mask[ny, nx]
                    and not visited[ny, nx]
                ):
                    visited[ny, nx] = True
                    stack.append((ny, nx))

        if pixels < min_area:
            continue

        if probability is not None:
            component = probability[
                min_y:max_y + 1,
                min_x:max_x + 1,
            ]
            score = float(component[mask[
                min_y:max_y + 1,
                min_x:max_x + 1
            ]].mean())
        else:
            score = 1.0

        detections.append(
            Detection(
                x=float(min_x),
                y=float(min_y),
                width=float(max_x - min_x + 1),
                height=float(max_y - min_y + 1),
                score=score,
            )
        )

    return detections
