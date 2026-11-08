@echo off
setlocal DisableDelayedExpansion
"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy RemoteSigned -File "C:\Users\Takashi\OneDrive\Desktop\Lesson_Reservation\operational_launcher\Start-LessonReservation.ps1"
set "launcherExit=%ERRORLEVEL%"
echo.
echo Launcher exit code: %launcherExit%
if not "%launcherExit%"=="0" echo STOP: startup, preflight, or runtime failed. Review the error above. Do not retry an unresolved session.
echo Review the output above before closing this window.
pause
exit /b %launcherExit%
