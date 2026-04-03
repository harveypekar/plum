@echo off
REM Compile all HLSL compute shaders to SPIR-V using DXC
set DXC=%VULKAN_SDK%\Bin\dxc.exe

for %%f in (*.hlsl) do (
    echo Compiling %%f...
    %DXC% -spirv -T cs_6_0 -E main -fspv-target-env=vulkan1.2 %%f -Fo %%~nf.spv
    if errorlevel 1 (
        echo FAILED: %%f
        exit /b 1
    )
)
echo All shaders compiled successfully.
