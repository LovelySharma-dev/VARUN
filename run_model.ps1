param (
    [string]$image = "data/sample_sar_image.tif",
    [string]$output = "output_mask.tif"
)

$model = "models/phase1/unet_oil_spill_v0.1.pth"
$script = "ml/phase1/infer.py"

Write-Host "Running Oil Spill Model Inference..." -ForegroundColor Cyan
Write-Host "Image : $image"
Write-Host "Output: $output"

python $script --image $image --model $model --output $output
