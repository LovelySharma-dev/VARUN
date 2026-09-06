@echo off
REM Command script to run Oil Spill Model Inference

if "%~1"=="" (
    echo ====================================================
    echo Oil Spill U-Net Model Inference Script
    echo ====================================================
    echo Usage:   run_model.bat ^<path_to_sar_image.tif^> [output_mask.tif]
    echo Example: run_model.bat C:\data\sar_sample.tif output_mask.tif
    echo ====================================================
    exit /b 1
)

set IMAGE_PATH=%~1
set OUTPUT_PATH=%~2
if "%OUTPUT_PATH%"=="" set OUTPUT_PATH=output_mask.tif

echo Running Oil Spill Segmentation Model...
echo Input Image : %IMAGE_PATH%
echo Model File  : models/phase1/unet_oil_spill_v0.1.pth
echo Output Mask : %OUTPUT_PATH%
echo ----------------------------------------------------

python ml/phase1/infer.py --image "%IMAGE_PATH%" --model models/phase1/unet_oil_spill_v0.1.pth --output "%OUTPUT_PATH%"

if %ERRORLEVEL% EQU 0 (
    echo ----------------------------------------------------
    echo [SUCCESS] Model inference completed successfully!
) else (
    echo ----------------------------------------------------
    echo [ERROR] Model inference failed with error code %ERRORLEVEL%.
)
