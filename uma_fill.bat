@echo off
setlocal

:: Change to script directory
cd /d "C:\Users\skyfj\Documents\My Games\Umamusume\simulator inputs"

:: Run Python OCR script
echo Running OCR on screenshots...
python uma_ocr_to_csv.py 1.JPG 2.JPG uma_data.csv

:: Generate simulator URL and open local UmaLator UI
echo Creating simulator link...
python uma_csv_to_url.py uma_data.csv

echo Done.
pause
