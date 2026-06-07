@echo off
REM Bootstrap ComfyUI for still-image generation (SDXL / Flux FP8) on RTX 2080 Ti
cd /d "%~dp0"
set COMFY_DIR=%~dp0comfyui
if exist "%COMFY_DIR%\main.py" (
    echo ComfyUI already cloned at %COMFY_DIR%
    goto models
)
echo Cloning ComfyUI...
git clone https://github.com/comfyanonymous/ComfyUI.git "%COMFY_DIR%"
:models
echo.
echo Next steps (manual, one-time):
echo   1. cd comfyui
echo   2. python -m venv venv
echo   3. venv\Scripts\pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
echo   4. venv\Scripts\pip install -r requirements.txt
echo   5. Download SDXL base to comfyui\models\checkpoints\
echo   6. Use tools\layout_wireframe.png as ControlNet lineart input
echo.
echo Generate wireframe: .venv\Scripts\python tools\generate_layout_wireframe.py
pause
