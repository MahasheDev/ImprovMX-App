@echo off
set nameapp=ImprovMX-App
set projectdirectory=%~dp0
set projectassets=%projectdirectory%Assets
set projectfavicon=%projectassets%\img\favicon.ico
set mainprojectfile=%projectdirectory%ImprovMX.py
del /f /q "%~dp0%nameapp%.exe"
pyinstaller --noconfirm --onefile --windowed --icon "%projectfavicon%" --name "%nameapp%" --uac-admin --uac-uiaccess --add-data "%projectdirectory%\ui_themes.py;." --add-data "%projectdirectory%\ui_i18n.py;." --add-data "%projectdirectory%\improvmx_api.py;." --add-data "%projectassets%\.env;." --hidden-import "os" --hidden-import "requests" --hidden-import "json" --hidden-import "base64" --hidden-import "typing" --hidden-import "Dict" --hidden-import "dataclass" --hidden-import "sys" --hidden-import "csv" --hidden-import "subprocess" --hidden-import "PySide6"  "%mainprojectfile%"
rd /s /q "%~dp0Project-Build"
timeout /t 4 >nul
del /f /q "%nameapp%.spec"
rd /s /q "build"
mkdir "%~dp0Project-Build"
copy /y "%~dp0dist\%nameapp%.exe" "%~dp0Project-Build"
timeout /t 2 >nul
rd /s /q "dist"
