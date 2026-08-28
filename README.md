# NonnaBot 👵📦

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

## Installazione in locale (il modo più semplice per averlo su Telegram)

Scarica il repository e fai **doppio clic** sullo script della tua piattaforma:

| Sistema | File | Come |
| --- | --- | --- |
| Windows | `avvia.bat` | doppio clic |
| Linux / macOS | `avvia.sh` | `bash avvia.sh` nel terminale |

Lo script crea l'ambiente, installa le dipendenze e prepara il file `.env`.
Al **primo giro** si ferma e ti chiede una cosa sola:

1. apri `.env` col Blocco note (o un editor qualsiasi);
2. incolla il token dopo `TELEGRAM_BOT_TOKEN=` — te lo dà
   [@BotFather](https://t.me/BotFather) con `/newbot`;
3. rilancia lo script.

Da quel momento la finestra resta aperta e **il bot risponde su Telegram**.
Chiudi la finestra (o `Ctrl+C`) e il bot si ferma: quando vuoi usarlo, riaprila.

> Serve Python **3.10 o superiore** ([python.org](https://www.python.org/downloads/);
> su Windows spunta *Add Python to PATH* durante l'installazione).

### A mano, se preferisci

```bash
git clone https://github.com/PiBOH/nonna_ebay_bot.git
cd nonna_ebay_bot
python3 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env          # poi incolla il token dentro .env
python main.py
```

### Configurazione

Tutto si configura con variabili d'ambiente (in locale puoi copiare
`.env.example` in `.env`):

| Variabile | Default | Descrizione |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | — *(obbligatoria)* | Token di @BotFather (accettato anche `BOT_TOKEN`) |
| `DATABASE_PATH` | `nonnabot.db` | Percorso del file SQLite |
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

> **GitHub conserva il codice, non lo esegue.** Il bot deve restare acceso 24/7
> per ricevere i tuoi messaggi, quindi i parametri (token e chiavi) vanno messi
> **dove il bot gira**, mai nei file del repository.
> Guida completa, con pro e contro di ogni opzione: **[DEPLOY.md](DEPLOY.md)**.

| Opzione | Costo | Carta? | Comandi interattivi | Note |
| --- | --- | --- | --- | --- |
| **GitHub Actions** ⭐ | gratis | ❌ | ❌ solo notifiche | la lista si gestisce col pulsante *Run workflow* |
| **Il tuo PC / Raspberry Pi** | gratis | ❌ | ✅ | il bot completo, ma la macchina deve restare accesa |
| **Hugging Face Space** ⭐ | gratis | ❌ | ✅ | sempre acceso, senza tenere il PC acceso: guida in [`deploy/huggingface/`](deploy/huggingface/ISTRUZIONI.md) |
| **Render** Background Worker | 7 $/mese | ✅ | ✅ | i worker **non** hanno piano gratuito |
| **PythonAnywhere** Developer | 10 $/mese | ✅ | ✅ | il piano gratuito non basta (vedi sotto) |

> **Senza soldi e senza carta:** Hugging Face Space per il bot completo sempre
> acceso, il tuo PC se preferisci, GitHub Actions se ti bastano le notifiche.
> Oracle Cloud e Fly.io chiedono la carta anche per i piani gratuiti.

### GitHub (consigliato se parti da zero)

1. `Settings → Secrets and variables → Actions`:
   * **Secrets**: `TELEGRAM_BOT_TOKEN` (facoltativi `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET`)
   * **Variables**: `TELEGRAM_CHAT_ID` (te lo dice [@userinfobot](https://t.me/userinfobot))
2. Copia i workflow da `deploy/github/` in `.github/workflows/`
   (istruzioni in [`deploy/github/README.md`](deploy/github/README.md)).
3. `Actions → Gestisci lista (manuale) → Run workflow → aggiungi → <link eBay>`.

Tre workflow: `tests.yml` (test a ogni push, senza segreti),
`gestisci-lista.yml` (aggiungi/lista/rimuovi a mano), `check-prezzi.yml`
(controllo prezzi ogni ora con `python main.py --check-once`).

### Render

Il repo include [`render.yaml`](render.yaml) (New → **Blueprint**): servizio,
disco e variabili si configurano da soli, e i segreti marcati `sync: false` te
li chiede la dashboard invece di stare nel file. A mano: *New → Background
Worker*, build `pip install -r requirements.txt`, start `python main.py`,
variabile `TELEGRAM_BOT_TOKEN`, **Disk** montato in `/data` con
`DATABASE_PATH=/data/nonnabot.db`.

### PythonAnywhere

Il piano gratuito (Beginner) **non funziona** per questo bot: niente always-on
task e accesso in uscita limitato a una allowlist dove **ebay.it non compare**.
Col piano Developer: crea `~/nonnabot/.env` col token (`chmod 600`), poi
**Tasks → Always-on task** con
`/home/TUOUSER/nonnabot/.venv/bin/python /home/TUOUSER/nonnabot/main.py`.

### VPS con systemd

```bash
sudo cp deploy/nonnabot.env.example /etc/nonnabot.env   # poi compilalo
sudo chmod 600 /etc/nonnabot.env
sudo cp deploy/nonnabot.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now nonnabot
```

> Su tutti i servizi serve **un solo processo**: il controllo prezzi è già
> dentro il bot (job queue), non va avviato a parte.

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
main.py                        tutto il bot (comandi, database, worker, dati eBay)
CHANGELOG.md                   registro delle modifiche (Keep a Changelog)
DEPLOY.md                      dove mettere token e chiavi, piattaforma per piattaforma
requirements.txt               dipendenze
render.yaml                    blueprint Render (worker + disco + variabili)
tests/test_bot.py              test automatici
.env.example                   modello di configurazione per il locale
.github/workflows/             CI dei test + cron di controllo prezzi
deploy/                        unit systemd e modello .env per VPS
```

### Due modalità di esecuzione

```bash
python main.py                 # processo residente: comandi + controllo prezzi
python main.py --check-once    # un solo giro di controllo, poi esce (cron/Actions)
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
