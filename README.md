# MiaNonnaBot 👵📦

Bot Telegram che tiene d'occhio i prezzi su **eBay** per te: incolli il link di
un'inserzione e il bot ti avvisa ogni volta che il prezzo cambia, in ribasso 📉
o in aumento 📈.

Bot pubblico: **[@nonna_ebay_bot](https://t.me/nonna_ebay_bot)**

---

## Comandi

Tutti i comandi funzionano **con o senza la barra** e sono **insensibili alle
maiuscole** (`lista`, `LISTA`, `/Lista`, `/l` fanno la stessa cosa).

| Comando | Alias | Cosa fa |
| --- | --- | --- |
| `aiuto` | `help`, `h`, `/start`, `/aiuto` | Mostra l'aiuto e la versione |
| `lista` | `list`, `l` | Elenco numerato degli oggetti sotto controllo |
| `cancella <num>` | `elimina`, `rimuovi` | Toglie l'oggetto con quel numero |
| `azzera` | `reset` | Toglie tutti gli oggetti della chat |
| `numero <n>` | il numero da solo (`1`, `/1`) | Rinvia il link dell'oggetto n |
| `changelog` | `novita` | Registro delle modifiche |
| *(link eBay)* | — | Mette l'oggetto sotto controllo |

Esempio di conversazione:

```
tu  → https://www.ebay.it/itm/405399021732
bot → ✅ Aggiunto al tracciamento come numero 1:
      Apple iPhone 13 - 128GB - Bianco
      Prezzo attuale: €500,00
      https://www.ebay.it/itm/405399021732

tu  → lista
bot → 👀 1 oggetti sotto controllo:
      1. Apple iPhone 13 - 128GB - Bianco - €500,00

     (un'ora dopo, in automatico)
bot → 📉 Prezzo sceso da €500,00 a €479,00!
      Apple iPhone 13 - 128GB - Bianco
      https://www.ebay.it/itm/405399021732
```

Il bot si può aggiungere a **gruppi e canali**: in quel caso la lista degli
oggetti è condivisa dalla chat. Nei gruppi con *privacy mode* attivo il bot vede
solo i comandi e i messaggi che lo menzionano (impostazione di @BotFather).

---

## Installazione in locale

```bash
git clone https://github.com/PiBOH/nonna_ebay_bot.git
cd nonna_ebay_bot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

export TELEGRAM_BOT_TOKEN="123456789:IL-TUO-TOKEN"
python main.py
```

Python **3.10 o superiore**. Il token si ottiene da [@BotFather](https://t.me/BotFather)
con `/newbot`.

### Configurazione

Tutto si configura con variabili d'ambiente (in locale puoi copiare
`.env.example` in `.env`):

| Variabile | Default | Descrizione |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | — *(obbligatoria)* | Token di @BotFather (accettato anche `BOT_TOKEN`) |
| `DATABASE_PATH` | `mianonnabot.db` | Percorso del file SQLite |
| `CHECK_INTERVAL_MINUTES` | `60` | Ogni quanti minuti ricontrollare i prezzi (minimo 5) |
| `EBAY_SITE` | `www.ebay.it` | Sito usato per i link |
| `EBAY_CLIENT_ID` | — | Client ID app eBay: se presente si usano le API ufficiali |
| `EBAY_CLIENT_SECRET` | — | Client Secret app eBay |
| `EBAY_MARKETPLACE_ID` | `EBAY_IT` | Marketplace per le API (`EBAY_IT`, `EBAY_DE`, …) |
| `EPN_CAMPAIGN_ID` | — | Campagna eBay Partner Network per i link affiliati |
| `MAX_TRACKED_PER_CHAT` | `50` | Limite di oggetti per chat |
| `REQUEST_DELAY_SECONDS` | `4` | Pausa fra due richieste eBay nel worker |
| `HTTP_TIMEOUT` | `25` | Timeout HTTP in secondi |
| `LOG_LEVEL` | `INFO` | Livello di logging |

---

## Come recupera i prezzi

1. **API ufficiali eBay Browse** — usate automaticamente se imposti
   `EBAY_CLIENT_ID` e `EBAY_CLIENT_SECRET` (app creata su
   [developer.ebay.com](https://developer.ebay.com)). È la via più stabile:
   niente blocchi IP, dati strutturati.
2. **Scraping della pagina oggetto** — se le API non sono configurate, il bot
   scarica `https://www.ebay.it/itm/<id>` e cerca i dati in cascata:
   JSON-LD (schema.org) → microdata `itemprop` → selettori CSS → regex sul
   grezzo. Se un livello cambia, il successivo tiene in piedi il bot.

Le inserzioni concluse vengono riconosciute, notificate una sola volta ed
escluse dai controlli successivi.

---

## Messa online

### Render (consigliato, gratis)

1. Nuovo **Background Worker** collegato al repository.
2. Runtime *Python 3*, build `pip install -r requirements.txt`, start `python main.py`.
3. Variabile d'ambiente `TELEGRAM_BOT_TOKEN`.
4. **Importante**: il disco dei piani gratuiti è effimero. Per non perdere i
   tracciamenti a ogni deploy monta un *Disk* (es. `/data`) e imposta
   `DATABASE_PATH=/data/mianonnabot.db`.

### PythonAnywhere

1. Carica i file, apri una console Bash e installa: `pip install -r requirements.txt --user`.
2. Esporta il token: `export TELEGRAM_BOT_TOKEN=...`
3. Avvia da una **Always-on task** (non da una console temporanea):
   `python /home/TUOUSER/nonna_ebay_bot/main.py`.
4. Su PythonAnywhere il disco è persistente, quindi il default `mianonnabot.db`
   va bene; mettilo comunque in una cartella che non sia `/tmp`.

> Su entrambi i servizi serve **un solo processo**: il worker di controllo
> prezzi è già dentro il bot (job queue), non va avviato a parte.

---

## Test

```bash
pip install pytest
python -m pytest tests/ -q
```

I test coprono parsing dei comandi, parsing dei prezzi, estrazione dalla pagina
eBay (con HTML di esempio per ogni livello di fallback), database, notifiche del
worker e l'handler Telegram con `Update` reali. Non servono rete né token.

---

## Struttura

```
main.py            tutto il bot (comandi, database, worker, estrazione dati)
CHANGELOG.md       registro delle modifiche (formato Keep a Changelog)
requirements.txt   dipendenze
tests/test_bot.py  test automatici
.env.example       modello di configurazione
```

### Database

Tabella `tracciamenti`: `id`, `chat_id`, `item_id_ebay`, `last_price`, `title`,
`url` più alcune colonne di servizio (`currency`, `created_at`, `last_checked`,
`ended`). Il numero mostrato da `lista` è la **posizione** dell'oggetto nella
chat, ricalcolata a ogni lettura: cancellando il 2, il 3 diventa il nuovo 2.

---

## Avvertenze

* Lo scraping viola potenzialmente i termini d'uso di eBay e può rompersi senza
  preavviso: per un uso continuativo imposta le credenziali API.
* Il bot è in fase di sviluppo (`0.x.y`) e può funzionare non correttamente.

## Licenza

GNU AGPL v3 — vedi [LICENSE](LICENSE).
