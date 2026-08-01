@echo off
echo.
echo  ================================
echo   CHOTU - Starting up...
echo  ================================
echo.

:: Install dependencies if needed
pip install -r requirements.txt --quiet

:: Open browser after 2 seconds
timeout /t 2 /nobreak > nul
start http://localhost:8000

:: Start server (real entrypoint - see app.py; server.py is an old
:: unused version, do not point this at it)
python app.py

pause
