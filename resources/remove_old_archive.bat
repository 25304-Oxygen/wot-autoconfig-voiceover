@echo off
setlocal enabledelayedexpansion

:: 代码由DeepSeek生成。作用是将归档文件替换掉旧文件
:: 查找以"autoConfigVoiceOver"开头的文件
set "targetfile="
for %%f in ("autoConfigVoiceOver*") do (
    set "targetfile=%%f"
    goto :found
)

:found
if not defined targetfile (
    echo 没有找到以 autoConfigVoiceOver 开头的文件
    pause
    exit /b
)

:: 先检查temp.zip是否存在
if not exist "temp.zip" (
    echo 未找到temp.zip文件，操作中止
    echo 完成更新后会自动移除temp.zip，无需更新时则不会生成temp.zip
    pause
    exit /b 1
)

echo 找到目标文件: %targetfile%
echo 请耐心等待文件更新……

:: 尝试删除文件直到成功
:deleteLoop
del "%targetfile%" >nul 2>&1
if exist "%targetfile%" (
    ping -n 2 127.0.0.1 >nul
    goto :deleteLoop
)

echo 成功删除文件: %targetfile%

:: 重命名temp.zip为被删除的文件名
if exist "temp.zip" (
    ren "temp.zip" "%targetfile%"
    echo 已将temp.zip重命名为: %targetfile%
) else (
    echo 未找到temp.zip文件
    pause
)