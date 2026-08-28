@echo off
REM --------------------------------------------------------------------------
REM Avvia NonnaBot sul tuo computer (Windows).
REM Uso: doppio clic su questo file.
REM
REM Al primo giro crea l'ambiente e il file .env: incolla li il token di
REM @BotFather e rilancia. Da li in poi il bot resta in ascolto finche questa
REM finestra e aperta.
REM --------------------------------------------------------------------------
chcp 65001 >nul
cd /d "%~dp0"

REM 1) Python installato?
where python >nul 2>nul
if errorlevel 1 (
    echo [ERRORE] Non trovo Python 3.
    echo Scaricalo da https://www.python.org/downloads/
    echo Durante l'installazione spunta "Add Python to PATH".
    pause
    exit /b 1
)

REM 2) Ambiente virtuale e dipendenze
if not exist ".venv" (
    echo Creo l'ambiente virtuale (.venv)...
    python -m venv .venv
    if errorlevel 1 ( echo [ERRORE] creazione .venv non riuscita & pause & exit /b 1 )
)
call .venv\Scripts\activate.bat
echo Installo/aggiorno le dipendenze...
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt
if errorlevel 1 ( echo [ERRORE] installazione dipendenze non riuscita & pause & exit /b 1 )

REM 3) File di configurazione col token
if not exist ".env" (
    copy .env.example .env >nul
    echo.
    echo Ho creato il file .env
    echo Aprilo col Blocco note, incolla il token dopo TELEGRAM_BOT_TOKEN=
    echo ^(te lo da @BotFather su Telegram^) e poi rilancia questo file.
    pause
    exit /b 0
)
findstr /r /c:"^TELEGRAM_BOT_TOKEN=." .env >nul
if errorlevel 1 (
    echo [ERRORE] In .env la riga TELEGRAM_BOT_TOKEN= e ancora vuota.
    echo Incolla il token di @BotFather e rilancia.
    pause
    exit /b 1
)

REM 4) Si parte: finche questa finestra e aperta il bot risponde su Telegram.
echo.
echo NonnaBot in ascolto. Chiudi la finestra per fermarlo.
echo.
python main.py
pause