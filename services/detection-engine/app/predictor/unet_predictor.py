import torch
from typing import Any

from app.predictor.unet import UNet
from app.postprocessing.mask_to_detection import mask_to_detections


class UNetPredictor:
    def __init__(
        self,
        model_path: str,
        threshold: float = 0.5,
        min_area: int = 20,
    ):
        self.device = torch.device(
            "cuda" if torch.cuda.is_available() else "cpu"
        )

        self.model = UNet(
            in_channels=2,
            out_channels=1,
        )

        state = torch.load(
            model_path,
            map_location=self.device,
            weights_only=True,
        )

        self.model.load_state_dict(state, strict=True)
        self.model.to(self.device)
        self.model.eval()

        self.threshold = threshold
        self.min_area = min_area

    @torch.inference_mode()
    def predict(self, image: Any):
        tensor = image

        if not isinstance(tensor, torch.Tensor):
            tensor = torch.as_tensor(
                tensor,
                dtype=torch.float32,
            )

        if tensor.ndim == 3:
            tensor = tensor.unsqueeze(0)

        if tensor.ndim != 4:
            raise ValueError(
                f"Expected image shape (C,H,W) or (B,C,H,W), got {tuple(tensor.shape)}"
            )

        if tensor.shape[1] != 2:
            raise ValueError(
                f"U-Net expects 2 input channels, got {tensor.shape[1]}"
            )

        tensor = tensor.to(
            device=self.device,
            dtype=torch.float32,
        )

        logits = self.model(tensor)
        probabilities = torch.sigmoid(logits)

        probability = probabilities[0, 0].cpu().numpy()

        mask = probability >= self.threshold

        return mask_to_detections(
            mask=mask,
            probability=probability,
            min_area=self.min_area,
        )
