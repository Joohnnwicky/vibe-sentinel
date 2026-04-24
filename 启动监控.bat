@echo off
chcp 65001 >nul
title Vibe Sentinel

echo ========================================
echo Vibe Sentinel - 屏幕活动监控报警器
echo ========================================
echo.

:: 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到Python，请先安装 Python 3.9+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 检查依赖
echo 检查依赖模块...
python -c "import mss, numpy, PIL, tkinter, winsound, playsound" >nul 2>&1
if errorlevel 1 (
    echo [提示] 正在安装依赖...
    pip install mss numpy Pillow playsound==1.2.2
    echo.
)

echo 启动程序...
echo.
python vibe_sentinel_gui.py

if errorlevel 1 (
    echo.
    echo [错误] 程序启动失败
    pause
)
