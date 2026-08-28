---
title: NonnaBot
emoji: 👵
colorFrom: red
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
---

# NonnaBot 👵📦

Bot Telegram che tiene d'occhio i prezzi su eBay:
**[@nonna_ebay_bot](https://t.me/nonna_ebay_bot)**

Questo Space non ha un'interfaccia web: il container tiene in ascolto il bot
Telegram (long polling) e risponde sulla porta 7860 solo per il controllo di
salute della piattaforma.

Codice sorgente e istruzioni: <https://github.com/PiBOH/nonna_ebay_bot>

## Variabili e segreti (Settings → Variables and secrets)

| Nome | Tipo | A cosa serve |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | Secret | token di @BotFather |
| `HF_TOKEN` | Secret | token Hugging Face con accesso in scrittura |
| `HF_BACKUP_REPO` | Variable | repo dataset dove salvare il database |
| `EBAY_CLIENT_ID` | Secret | facoltativo: API ufficiali eBay |
| `EBAY_CLIENT_SECRET` | Secret | facoltativo: API ufficiali eBay |

Senza `HF_TOKEN` e `HF_BACKUP_REPO` il bot funziona lo stesso, ma la lista dei
prodotti si azzera a ogni riavvio del container.
