@echo off
chcp 65001 >nul
title JMComic 下载器
cd /d "%~dp0"
echo 正在启动 JMComic 下载器...
echo.
py app.py
pause
