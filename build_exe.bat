@echo off
chcp 65001 >nul
echo ========================================
echo   JMComic 下载器 - 打包成 exe
echo ========================================
echo.

echo [1/3] 安装/更新打包工具...
py -m pip install pyinstaller -q --upgrade

echo [2/3] 开始打包（可能需要几分钟，请耐心等待）...
py -m PyInstaller --noconfirm --onefile --console ^
  --name "JMComic下载器" ^
  --add-data "assets;assets" ^
  --collect-all gradio ^
  --collect-all gradio_client ^
  --collect-all safehttpx ^
  --collect-all groovy ^
  --hidden-import=gradio ^
  --hidden-import=jmcomic ^
  --hidden-import=zhconv ^
  --hidden-import=safehttpx ^
  app.py

echo.
echo [3/3] 完成！
echo exe 文件在： dist\JMComic下载器.exe
echo.
echo 双击它就能运行。
echo 如果还是报错，请把完整报错发给我。
pause
