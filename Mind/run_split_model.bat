@echo off
echo ===================================================
echo      Leo AI Server (Manufacturer: Emenike Chinenye James)
echo ===================================================
echo.
echo This bypasses Ollama validation and runs your OFFICIAL split files directly.
echo using the 'llama-server.exe' you manually downloaded.
echo.

if not exist "%~dp0llama-server.exe" (
    echo [ERROR] llama-server.exe not found!
    echo Please make sure you extracted the ZIP content into this folder.
    pause
    exit /b
)

echo Starting Server...
echo Model: model.gguf
echo Vision: mmproj.gguf
echo URL: http://localhost:8080
echo.

"%~dp0llama-server.exe" -m "%~dp0model.gguf" --mmproj "%~dp0mmproj.gguf" --host 127.0.0.1 --port 8080 -c 32768 --n-gpu-layers 0 --no-warmup

pause
