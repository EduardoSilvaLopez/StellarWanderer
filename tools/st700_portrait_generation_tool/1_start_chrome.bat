@echo off
rem Starts a special Chrome window that the ST-700 portrait tool can control.
rem It uses its own profile folder, so your normal Chrome is not touched.
echo Starting the Chrome window for the ST-700 portrait tool...
start "" "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --user-data-dir="%USERPROFILE%\chrome-perchance"
echo.
echo A new Chrome window opened. LEAVE IT OPEN while the tool runs.
echo Next step: double-click 2_run_tool.bat
echo.
pause
