@echo off
echo Building PrintFlow Bridge DLL...
"C:\Users\12104\Desktop\tcc\tcc\tcc.exe" "%~dp0printflow-bridge.c" -shared -o "%~dp0printflow-bridge.dll" -luser32 -lkernel32
if %ERRORLEVEL% EQU 0 (
    echo SUCCESS: printflow-bridge.dll built
) else (
    echo FAILED: compilation error
)
pause
