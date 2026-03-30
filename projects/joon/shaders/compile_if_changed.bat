@echo off
setlocal enabledelayedexpansion
set GLSLC=%VULKAN_SDK%\Bin\glslc.exe
set CHANGED=0

for %%f in (*.comp) do (
    set "COMPILE="
    if not exist "%%~nf.spv" (
        set "COMPILE=1"
    ) else (
        rem dir /od sorts oldest-first; last listed file is newest
        for /f "tokens=*" %%a in ('dir /b /od "%%f" "%%~nf.spv" 2^>nul') do set "NEWEST=%%a"
        if "!NEWEST!"=="%%f" set "COMPILE=1"
    )
    if defined COMPILE (
        echo Compiling %%f...
        "%GLSLC%" %%f -o %%~nf.spv
        if errorlevel 1 (
            echo FAILED: %%f
            exit /b 1
        )
        set /a CHANGED+=1
    )
)

if !CHANGED!==0 (
    echo Shaders up to date.
) else (
    echo Compiled !CHANGED! shader^(s^).
)
