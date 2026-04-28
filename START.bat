@echo off
title Gas Pinas Inc. - LPG Management System
color 0A

echo.
echo  =====================================================
echo   Gas Pinas Inc. - LPG Distribution Management System
echo  =====================================================
echo.
echo  Starting Flask server...
echo  Open your browser at: http://localhost:5000
echo.
echo  Default login: admin / Admin@1234
echo.

cd /d "%~dp0"
python run.py

pause
