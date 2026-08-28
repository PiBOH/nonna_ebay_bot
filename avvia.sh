#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Avvia NonnaBot sul tuo computer (Linux/macOS).
# Uso:  bash avvia.sh
#
# Al primo giro crea l'ambiente e il file .env: incolla li il token di
# @BotFather e rilancia. Da li in poi il bot resta in ascolto finche questa
# finestra e aperta.
# ---------------------------------------------------------------------------
set -e
cd "$(dirname "$0")"

# 1) Python installato?
if ! command -v python3 >/dev/null 2>&1; then
    echo "[ERRORE] Non trovo Python 3."
    echo "Ubuntu/Debian:  sudo apt install python3 python3-venv"
    echo "Oppure scaricalo da https://www.python.org/downloads/"
    exit 1
fi

# 2) Ambiente virtuale e dipendenze
if [ ! -d ".venv" ]; then
    echo "Creo l'ambiente virtuale (.venv)..."
    python3 -m venv .venv
fi
# shellcheck disable=SC1091
. .venv/bin/activate
echo "Installo/aggiorno le dipendenze..."
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

# 3) File di configurazione col token
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo ""
    echo "Ho creato il file .env"
    echo "Aprilo col tuo editor, incolla il token dopo TELEGRAM_BOT_TOKEN="
    echo "(te lo da @BotFather su Telegram) e poi rilancia questo file."
    exit 0
fi
if ! grep -q "^TELEGRAM_BOT_TOKEN=." .env; then
    echo "[ERRORE] In .env la riga TELEGRAM_BOT_TOKEN= e ancora vuota."
    echo "Incolla il token di @BotFather e rilancia."
    exit 1
fi

# 4) Si parte: finche questa finestra e aperta il bot risponde su Telegram.
echo ""
echo "NonnaBot in ascolto. Premi Ctrl+C per fermarlo."
echo ""
python main.py
