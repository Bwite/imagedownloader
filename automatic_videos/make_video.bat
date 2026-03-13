@echo off
cd /d "%~dp0"
cd ..

echo ============================================================
echo   AUTOMATIC VIDEO GENERATOR
echo ============================================================
echo.
echo Working directory: %CD%
echo.

:: Use venv Python directly
set "PYTHON=%CD%\.venv\Scripts\python.exe"
if not exist "%PYTHON%" (
    echo ERROR: Virtual environment not found at .venv\Scripts\python.exe
    pause
    exit /b 1
)
echo Using Python: %PYTHON%
echo.

:: (Images now stored in timestamped folders per generation, no cleanup needed)

:: Find the audio file in automatic_videos folder
set "AUDIO="
for %%f in ("automatic_videos\*.m4a") do set "AUDIO=%%f"
if "%AUDIO%"=="" for %%f in ("automatic_videos\*.mp3") do set "AUDIO=%%f"
if "%AUDIO%"=="" for %%f in ("automatic_videos\*.wav") do set "AUDIO=%%f"
if "%AUDIO%"=="" for %%f in ("automatic_videos\*.ogg") do set "AUDIO=%%f"
if "%AUDIO%"=="" for %%f in ("automatic_videos\*.flac") do set "AUDIO=%%f"
if "%AUDIO%"=="" for %%f in ("automatic_videos\*.aac") do set "AUDIO=%%f"

if "%AUDIO%"=="" (
    echo ERROR: No audio file found in automatic_videos folder.
    echo Place an audio file in the automatic_videos folder.
    pause
    exit /b 1
)

echo Found audio: %AUDIO%
echo.

:: Step 1 - Transcribe and generate sections
echo [Step 1/3] Transcribing audio and generating sections...
echo ============================================================
"%PYTHON%" automatic_videos\handlescript.py "%AUDIO%"
if errorlevel 1 (
    echo.
    echo ERROR: Step 1 failed.
    pause
    exit /b 1
)
echo.

:: Step 2 - Download images
echo [Step 2/3] Downloading images for each section...
echo ============================================================
"%PYTHON%" automatic_videos\downloader.py automatic_videos\sections.json
if errorlevel 1 (
    echo.
    echo ERROR: Step 2 failed.
    pause
    exit /b 1
)
echo.

:: Step 3 - Build video
echo [Step 3/3] Building video...
echo ============================================================
set "TITLE=output.mp4"
if exist "automatic_videos\video_title.txt" (
    set /p TITLE=<"automatic_videos\video_title.txt"
)
echo Output filename: %TITLE%
"%PYTHON%" automatic_videos\video_builder.py automatic_videos\sections.json automatic_videos\image_folders.json "%AUDIO%" "automatic_videos\%TITLE%"
if errorlevel 1 (
    echo.
    echo ERROR: Step 3 failed.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo   DONE! Video saved to: automatic_videos\%TITLE%
echo ============================================================
echo.
pause
