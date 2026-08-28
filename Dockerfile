# ---------------------------------------------------------------------------
# Immagine per Hugging Face Spaces (SDK Docker).
# Funziona anche in locale:  docker build -t nonnabot . && docker run --rm \
#   -e TELEGRAM_BOT_TOKEN=... -p 7860:7860 nonnabot
#
# Nota: Hugging Face esegue i container con UID 1000, quindi l'utente va creato
# PRIMA delle COPY e i file vanno copiati con --chown=user.
# ---------------------------------------------------------------------------
FROM python:3.12-slim

RUN useradd -m -u 1000 user
USER user

ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR $HOME/app

# Prima le dipendenze, così la cache del layer sopravvive alle modifiche al codice
COPY --chown=user requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY --chown=user main.py ./

# Cartella per il database (disco effimero: il backup va sul dataset Hub)
RUN mkdir -p $HOME/app/data

ENV DATABASE_PATH=$HOME/app/data/nonnabot.db \
    PORT=7860 \
    CHECK_INTERVAL_MINUTES=60 \
    EBAY_SITE=www.ebay.it \
    LOG_LEVEL=INFO

# Lo Space deve rispondere su questa porta, altrimenti viene considerato morto
EXPOSE 7860

CMD ["python", "main.py", "--with-health-endpoint"]
