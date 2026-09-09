from typing import Any
import numpy as np
import torch


def preprocess_image(image: Any) -> torch.Tensor:
    if isinstance(image, torch.Tensor):
        tensor = image.float()
    else:
        tensor = torch.as_tensor(
            np.asarray(image),
            dtype=torch.float32,
        )

    if tensor.ndim == 2:
        tensor = tensor.unsqueeze(0).repeat(2, 1, 1)

    elif tensor.ndim == 3:
        if tensor.shape[0] == 2:
            pass
        elif tensor.shape[-1] == 2:
            tensor = tensor.permute(2, 0, 1)
        elif tensor.shape[0] == 1:
            tensor = tensor.repeat(2, 1, 1)
        elif tensor.shape[-1] == 1:
            tensor = tensor.permute(2, 0, 1).repeat(2, 1, 1)
        else:
            tensor = tensor[:2]

    elif tensor.ndim == 4:
        if tensor.shape[1] != 2:
            raise ValueError(
                f"Expected 2 channels, got {tensor.shape[1]}"
            )
        return tensor

    else:
        raise ValueError(
            f"Unsupported image shape: {tuple(tensor.shape)}"
        )

    tensor = torch.nan_to_num(tensor, nan=0.0, posinf=0.0, neginf=0.0)

    minimum = tensor.amin(dim=(-2, -1), keepdim=True)
    maximum = tensor.amax(dim=(-2, -1), keepdim=True)

    tensor = (tensor - minimum) / (maximum - minimum + 1e-8)

    return tensor
