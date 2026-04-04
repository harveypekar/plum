@echo off
REM Compile all GLSL compute shaders to SPIR-V
set GLSLC=%VULKAN_SDK%\Bin\glslc.exe

for %%f in (*.comp) do (
    echo Compiling %%f...
    %GLSLC% %%f -o %%~nf.spv
    if errorlevel 1 (
        echo FAILED: %%f
        exit /b 1
    )
)
echo All shaders compiled successfully.
