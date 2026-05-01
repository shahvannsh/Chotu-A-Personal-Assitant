@echo off
echo.
echo  ================================
echo   JARVIS - Starting up...
echo  ================================
echo.

:: Install dependencies if needed
pip install -r requirements.txt --quiet

:: Open browser after 2 seconds
timeout /t 2 /nobreak > nul
start http://localhost:8000

:: Start server
python server.py

pause
