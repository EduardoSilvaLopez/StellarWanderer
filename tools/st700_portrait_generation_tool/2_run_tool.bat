@echo off
cd /d "%~dp0"
for %%I in ("%~dp0..\..\common\resources\portraits") do set "DEFOUT=%%~fI"
set "TOOL=python st700_portrait_generation_tool.py"

echo ============================================
echo   ST-700 portrait generation tool
echo ============================================
echo.
echo Make sure you already ran 1_start_chrome.bat and left that Chrome open.
echo Tip: for several options separate them with commas, or type All.

:again
echo.
echo ============================================
echo   NEW BATCH
echo ============================================
echo.
echo --- 1. ETHNIC GROUPS ---
%TOOL% --list ethnicities
set "ETH="
set /p ETH=Your choice:
if "%ETH%"=="" (
  echo Nothing chosen. Nothing to do.
  goto ask
)

echo.
echo --- 2. GENDERS ---
%TOOL% --list genders
set "GEN=androgyne"
set /p GEN=Your choice [Enter = androgyne]:

echo.
echo --- 3. CATEGORIES ---
%TOOL% --list categories
set "CAT=All"
set /p CAT=Your choice [Enter = All]:

echo.
echo --- 4. AGES ---
%TOOL% --list ages
set "AGES="
set /p AGES=Your choice [Enter = each category's usual ages]:

echo.
echo --- 5. FOLDER WHERE THE IMAGES ARE SAVED ---
echo   Enter = %DEFOUT%
set "OUT=%DEFOUT%"
set /p OUT=Folder:
if "%OUT:~-1%"=="\" set "OUT=%OUT:~0,-1%"

echo.
set "DRY=n"
set /p DRY=Preview only, without generating anything? [y/N]:
echo.

if /i "%DRY%"=="y" (
  %TOOL% --ethnicity "%ETH%" --genders "%GEN%" --categories "%CAT%" --ages "%AGES%" --out "%OUT%" --dry-run
) else (
  %TOOL% --ethnicity "%ETH%" --genders "%GEN%" --categories "%CAT%" --ages "%AGES%" --out "%OUT%"
)

:ask
echo.
set "MORE=y"
set /p MORE=Generate another batch? [Y/n]:
if /i "%MORE%"=="n" goto done
goto again

:done
echo.
echo Finished. You can close this window and the special Chrome window.
pause
