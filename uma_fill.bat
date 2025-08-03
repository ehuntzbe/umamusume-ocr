@echo off
setlocal

:: Change to script directory
cd /d "C:\Users\skyfj\Documents\My Games\Umamusume\simulator inputs"

:: Run Python OCR script
echo Running OCR on screenshots...
python uma_ocr_to_csv.py 1.JPG 2.JPG uma_data.csv

:: Trigger UI.Vision macro (change folder path as needed)
echo Launching UI.Vision macro...
"C:\Program Files\Mozilla Firefox\firefox.exe" "file:///C:/Users/skyfj/AppData/Roaming/UI.Vision/ui.vision.html?macro=uma_fill_macro&storage=browser"

echo Done.
pause
