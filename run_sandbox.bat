@echo off
REM GUI Sandbox launcher & tools.
REM Usage:
REM   run_sandbox.bat                  -- start GUI Sandbox (default)
REM   run_sandbox.bat sandbox          -- start GUI Sandbox
REM   run_sandbox.bat launch           -- start real SAP GUI, wait for login
REM   run_sandbox.bat inspect          -- inspect current screen (tree)
REM   run_sandbox.bat inspect --out screens/main.json
REM   run_sandbox.bat scenarios all    -- run all scenarios, output to screens/
REM   run_sandbox.bat scenarios VA01
REM   run_sandbox.bat scenarios SE16 --table SFLIGHT

set SYSPY=python
set ACTION=%1

if "%ACTION%"=="" goto :sandbox
if "%ACTION%"=="sandbox" goto :sandbox

if "%ACTION%"=="launch" (
    %SYSPY% -m tools.sap_launch %2 %3 %4 %5
) else if "%ACTION%"=="inspect" (
    %SYSPY% -m tools.sap_inspect %2 %3 %4 %5
) else if "%ACTION%"=="scenarios" (
    %SYSPY% -m tools.sap_scenarios --scenario %2 %3 %4 %5 %6
) else if "%ACTION%"=="connect" (
    %SYSPY% -m tools.sap_connect
) else (
    goto :usage
)
goto :end

:sandbox
echo Starting GUI Sandbox...
cd /d "%~dp0"
%SYSPY% main.py
goto :end

:usage
echo Usage: run_sandbox.bat [sandbox^|launch^|inspect^|scenarios^|connect] [options]
echo.
echo   sandbox    Start the GUI Sandbox simulator (default)
echo   launch     Start real SAP GUI, wait for login
echo   inspect    Inspect current screen (tree)
echo   scenarios  Run capture scenarios
echo   connect    Connect to running SAP GUI
echo.
echo Examples:
echo   run_sandbox.bat
echo   run_sandbox.bat sandbox
echo   run_sandbox.bat launch
echo   run_sandbox.bat inspect --tree
echo   run_sandbox.bat scenarios all --out screens/
echo   run_sandbox.bat scenarios SE16 --table SFLIGHT
echo.
pause

:end
