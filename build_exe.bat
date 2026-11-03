@echo off
chcp 65001 >nul
echo ========================================
echo   JMComic 下载器 - 打包成 exe
echo ========================================
echo.

echo [1/3] 安装打包工具...
py -m pip install pyinstaller -q

echo [2/3] 开始打包（可能需要几分钟）...
py -m PyInstaller --noconfirm --onefile --windowed ^
  --name "JMComic下载器" ^
  --add-data "assets;assets" ^
  --hidden-import=gradio ^
  --hidden-import=jmcomic ^
  --hidden-import=zhconv ^
  app.py

echo.
echo [3/3] 完成！
echo exe 文件在： dist\JMComic下载器.exe
echo.
echo 双击它就能运行，可以直接分享给别人。
pause
