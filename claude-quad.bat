@echo off
REM Launch Windows Terminal with 4 WSL panes in a 2x2 grid.
REM Positioned to cover the bottom half of the primary screen.

REM Get screen working area: left, midY, width, halfHeight
for /f "tokens=1-4" %%a in ('powershell -NoProfile -Command "Add-Type -AssemblyName System.Windows.Forms; $s = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea; Write-Output ('{0} {1} {2} {3}' -f $s.Left, ($s.Top + [int]($s.Height / 2)), $s.Width, [int]($s.Height / 2))"') do (
    set POS_X=%%a
    set POS_Y=%%b
    set WIN_W=%%c
    set WIN_H=%%d
)

REM Launch Windows Terminal at the bottom-half position
start "" wt -w new --pos %POS_X%,%POS_Y% new-tab wsl.exe --cd /mnt/d/prg/plum -- zsh -ic claude ; split-pane -V wsl.exe --cd /mnt/d/prg/plum -- zsh -ic claude ; split-pane -H wsl.exe --cd /mnt/d/prg/plum ; move-focus left ; split-pane -H wsl.exe --cd /mnt/d/prg/plum -- zsh -ic claude

REM Wait for the window to appear, then resize to fill bottom half exactly
timeout /t 2 /nobreak >nul
powershell -NoProfile -Command "Add-Type -MemberDefinition '[DllImport(\"user32.dll\")] public static extern bool MoveWindow(IntPtr h, int x, int y, int w, int h2, bool r);' -Name W -Namespace W; $p = Get-Process WindowsTerminal ^| Sort-Object StartTime -Descending ^| Select-Object -First 1; if ($p) { [W.W]::MoveWindow($p.MainWindowHandle, %POS_X%, %POS_Y%, %WIN_W%, %WIN_H%, $true) }"
