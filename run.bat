@echo off
chcp 65001 >nul
title 機器人啟動與環境檢查工具

:: ==========================================
:: 設定區（可自行修改）
:: ==========================================
set "PYTHON_VER=3.11.5"
set "PYTHON_URL=https://python.org"
set "INSTALLER=python_installer.exe"
set "VENV_DIR=.venv"

:: ==========================================
:: 1. 檢查 Python 是否已安裝於系統中
:: ==========================================
python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [資訊] 偵測到系統已安裝 Python，跳過安裝步驟。
    goto CHECK_VENV
)

echo [提示] 系統未安裝 Python，即將開始下載並安裝...

:: 檢查暫存安裝檔是否存在，不存在則下載
if not exist "%INSTALLER%" (
    echo [下載] 正在下載 Python %PYTHON_VER%...
    powershell -Command "Invoke-WebRequest -Uri '%PYTHON_URL%' -OutFile '%INSTALLER%'"
    if not exist "%INSTALLER%" (
        echo [錯誤] 下載 Python 失敗，請檢查網路連線！
        pause
        exit /b
    )
)

:: 執行靜默安裝（自動加到環境變數 PATH）
echo [安裝] 正在背景安裝 Python，請稍候...
start /wait "" "%INSTALLER%" /quiet InstallAllUsers=1 PrependPath=1 Include_test=0
del "%INSTALLER%"

:: 重新整理環境變數以套用 python 指令
set "PATH=%PATH%;C:\Program Files\Python311;C:\Program Files\Python311\Scripts"

:: 再次檢查是否安裝成功
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [錯誤] Python 安裝失敗或未成功加入環境變數，請嘗試手動重開此視窗。
    pause
    exit /b
)
echo [成功] Python 安裝完成！

:: ==========================================
:: 2. 檢查與設定虛擬環境（避免干擾系統環境）
:: ==========================================
:CHECK_VENV
if exist "%VENV_DIR%\Scripts\activate.bat" (
    echo [資訊] 偵測到虛擬環境已建立，準備啟動機器人...
    goto RUN_BOT
)

echo [設定] 第一次執行，正在建立虛擬環境...
python -m venv %VENV_DIR%

echo [設定] 正在啟動虛擬環境...
call "%VENV_DIR%\Scripts\activate.bat"

echo [升級] 正在更新 pip...
python -m pip install --upgrade pip

:: ==========================================
:: 3. 安裝 requirements.txt 中的套件
:: ==========================================
if exist "requirements.txt" (
    echo [安裝] 正在安裝 requirements.txt 中的必要套件...
    pip install -r requirements.txt
    echo [成功] 所有套件安裝完畢！
) else (
    echo [警告] 未登錄到 requirements.txt 檔案，將跳過套件安裝。
)

:: ==========================================
:: 4. 啟動機器人 (第二次執行時會直接跳到這裡)
:: ==========================================
:RUN_BOT
echo [啟動] 正在進入虛擬環境並執行 bot.py...
call "%VENV_DIR%\Scripts\activate.bat"
python bot.py

pause
