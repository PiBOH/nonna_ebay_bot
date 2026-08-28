**A cosa serve questo file.** È la memoria del progetto. Se apri una nuova chat
> e dai a un agente *solo* questo file, deve poter ricostruire NonnaBot da zero.
>
> **Cosa garantisce davvero, senza illusioni.**
> * I file riprodotti **per intero** nel §5 sono byte-per-byte identici.
> * `main.py` e `tests/test_bot.py` sono descritti come **blueprint + contratti**
>   (§3, §4, §6): un agente che li segue ottiene un comportamento **equivalente e
>   verificabile**, non gli stessi byte. Per l'identico byte-per-byte di quei due
>   file serve il file stesso (o il commit Git indicato in §8).
> * Ogni file ha lo **sha256** (§2): dopo la ricostruzione, `sha256sum` dice subito
>   cosa coincide e cosa no.
>
> Lingua del progetto: **italiano** (commenti, messaggi all'utente, documentazione).
> Licenza: **GNU AGPL v3** (file `LICENSE` già presente nel repository).

---

## 1. Contesto e decisioni già prese

Bot Telegram **NonnaBot** (`@nonna_ebay_bot`): l'utente incolla il link di
un'inserzione eBay e riceve una notifica ogni volta che il prezzo cambia
(📉 ribasso / 📈 rincaro).

| Decisione | Scelta | Perché |
| --- | --- | --- |
| Nome | **NonnaBot** (prima era `MiaNonnaBot`) | richiesta esplicita dell'utente |
| Versione | `0.0.1`, SemVer + Keep a Changelog | richiesta iniziale |
| Stack | Python 3.10+, `python-telegram-bot` v20+ asincrono, `requests`, `BeautifulSoup4`, `sqlite3` | richiesta iniziale |
| Un solo file per il bot | `main.py` | richiesta iniziale |
| Estrazione dati | API Browse opzionali → JSON-LD → microdata → CSS → regex | il markup eBay cambia; la cascata evita rotture |
| Indice degli oggetti | posizione nella chat, ricalcolata a ogni lettura | cancellando il 2, il 3 diventa 2 |
| Hosting scelto dall'utente | **Hugging Face Space** (gratis, senza carta) | l'utente non ha soldi né carta e vuole usare il bot solo in chat |

**Fatti verificati sulle pagine ufficiali** (non fidarsi di altre fonti):

* [render.com/docs/free](https://render.com/docs/free): solo Web Service, Postgres
  e Key Value hanno istanze gratuite — *"Other service types don't support Free
  instances"*. I **Background Worker sono a pagamento** (da 7 $/mese). I web
  service free si spengono dopo 15 minuti senza traffico in entrata → inutili per
  un bot in polling.
* [pythonanywhere.com/pricing](https://www.pythonanywhere.com/pricing/): il piano
  gratuito *Beginner* non ha **always-on task** né **scheduled task**.
* [allowlist PythonAnywhere](https://www.pythonanywhere.com/whitelist/): **ebay.it
  non compare** → dal piano gratuito il bot non leggerebbe i prezzi.
* [HF Spaces](https://huggingface.co/docs/huggingface_hub/en/guides/manage-spaces):
  `cpu-basic` si addormenta dopo **48 h** di inattività.
* [HF Docker Spaces](https://huggingface.co/docs/hub/spaces-sdks-docker):
  *"The data written on disk is lost whenever your Docker Space restarts"*;
  SDK `docker`, `app_port: 7860`, UID 1000, segreti a runtime come env var.
* Fly.io non ha più free tier; Oracle Cloud Always Free chiede la carta.

---

## 2. Inventario file (righe / byte / sha256 primi 16 caratteri)

```
main.py                             1786   66456   0e589e5bcb59f6e9
tests/test_bot.py                   1175   44253   75fd4b6b1acb3451
CHANGELOG.md                         103    6070   b231ee6e250fb551
requirements.txt                      21     719   4176ee2b7a4fd9bc   (§5.1)
README.md                            238    9615   bf858901416cf77c
DEPLOY.md                            261   11177   d9aad16df773e4dc
Dockerfile                            39    1275   7ed26df4b66a5ac1   (§5.2)
.env.example                          43    1439   96a453a0ca8d6bdd   (§5.3)
.gitignore                            34     352   9396b1ccacd5ac73
render.yaml                           54    1702   9b9abc9ec328a0f4
avvia.sh                              56    1913   e964b4970a200850
avvia.bat                             58    1886   258897d5ccb04209
deploy/nonnabot.service               34     866   2142bd1f380ee106
deploy/nonnabot.env.example           23     763   c031c2e2c61d7ddf   (§5.4)
deploy/github/README.md               26    1040   63879738c9e4331a   (§5.5)
deploy/github/tests.yml               39     950   69361870613d367a
deploy/github/check-prezzi.yml        76    2727   c28aa89a71416942
deploy/github/gestisci-lista.yml      85    2834   48f41f03953f9d10
deploy/github/keep-alive.yml          42    1356   5d7b54925ccd97ef
deploy/huggingface/space-README.md    33    1057   309b8cc16e5f42e9   (§5.6)
deploy/huggingface/ISTRUZIONI.md     116    4324   78661c5bc71ab78e
LICENSE                                   34523   (AGPL v3, già nel repo)
```

`.github/workflows/{tests,check-prezzi,gestisci-lista}.yml` sono **copie identiche**
(stesso sha256) dei file in `deploy/github/`.

---

## 3. Contratti fissi — da rispettare alla lettera

### 3.1 Nome e versione

```python
__version__ = "0.0.1"
BOT_NAME = "NonnaBot"
BOT_USERNAME = os.environ.get("BOT_USERNAME", "nonna_ebay_bot")
```

### 3.2 Messaggio di aiuto (esatto, carattere per carattere)

Inviato **senza parse mode** (gli asterischi devono restare letterali).
La riga della versione è generata da `__version__`.

```
NonnaBot:
Versione: 0.0.1

👋 Comandi utilizzabili

* aiuto,help,h : questo messaggio
* lista,list,l : elenco prodotti sotto controllo
* cancella num : elimina prodotto da osservare
* azzera : elimina tutti i prodotti sottoscritti
* numero : richiama link prodotto n (es. inviando solo il numero "1" o "/1" o "numero 1")
* changelog : mostra il registro delle modifiche

Incolla un link eBay, per tener sotto controllo il prezzo

❤️ Il bot si può aggiungere a gruppi e canali ❤️

Il Bot è ancora in fase di sviluppo e può funzionare non correttamente.
```

### 3.3 Comandi e alias (tutti case-insensitive, con o senza `/`)

```python
HELP_WORDS      = {"start","aiuto","help","h","comandi","menu","info","?"}
LIST_WORDS      = {"lista","list","l","elenco","prodotti","oggetti"}
CLEAR_WORDS     = {"azzera","azzerratutto","reset","svuota","eliminatutto","cancellatutto"}
CHANGELOG_WORDS = {"changelog","novita","novità","versione","changelogs"}
DELETE_WORDS    = {"cancella","elimina","rimuovi","remove","delete","del","x","d"}
NUMBER_WORDS    = {"numero","num","n","link"}
```

Regole di `parse_message(text)`:

1. testo vuoto → `IGNORE`;
2. contiene un link eBay e **non** inizia con `/` → `ADD`;
3. si toglie il `/` iniziale e l'eventuale `@nomebot` dal primo token;
4. primo token tutto cifre: ≥10 cifre → `ADD` (ID oggetto), altrimenti → `LINK(n)`;
5. si confronta il token minuscolo con gli insiemi di cui sopra;
6. `cancella`/`numero` senza numero → rispettivamente `DELETE_USAGE` / `LINK_USAGE`;
7. resto: se c'è comunque un ID eBay → `ADD`, altrimenti `UNKNOWN`.

Testi di errore fissi:

```
DELETE_USAGE = 'Uso: cancella <numero>\nEsempio: "cancella 3" (oppure "/cancella 3").'
LINK_USAGE   = 'Uso: numero <numero>\nEsempio: "numero 3", oppure invia solo "3" o "/3".'
UNKNOWN_TEXT = ("Non ho capito 🤔\n"
                "Incolla un link eBay per mettere l'oggetto sotto controllo, "
                'oppure scrivi "aiuto" per vedere i comandi.')
```

### 3.4 Schema SQLite

```sql
CREATE TABLE IF NOT EXISTS tracciamenti (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id       INTEGER NOT NULL,
    item_id_ebay  TEXT    NOT NULL,
    last_price    REAL,
    title         TEXT,
    url           TEXT    NOT NULL,
    currency      TEXT    NOT NULL DEFAULT 'EUR',
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    last_checked  TEXT,
    ended         INTEGER NOT NULL DEFAULT 0,
    UNIQUE (chat_id, item_id_ebay)
);
CREATE INDEX IF NOT EXISTS idx_tracciamenti_chat ON tracciamenti (chat_id, id);
```

Le prime sei colonne sono quelle richieste dalla specifica originale; le altre
quattro sono di servizio. Connessione: `PRAGMA busy_timeout=15000`,
`journal_mode=WAL`, `synchronous=NORMAL`, `row_factory=sqlite3.Row`, timeout 15 s.

### 3.5 Variabili d'ambiente

| Variabile | Default | Note |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | — (anche `BOT_TOKEN`) | obbligatoria per il bot in ascolto |
| `TELEGRAM_CHAT_ID` | `0` | chat per gli oggetti aggiunti da CLI |
| `DATABASE_PATH` | `nonnabot.db` | |
| `CHECK_INTERVAL_MINUTES` | `60` | minimo 5 |
| `EBAY_SITE` | `www.ebay.it` | |
| `EBAY_CLIENT_ID` / `EBAY_CLIENT_SECRET` | — | se entrambe presenti → API Browse |
| `EBAY_MARKETPLACE_ID` | `EBAY_IT` | |
| `EBAY_LANG` | `it-IT` | |
| `EPN_CAMPAIGN_ID` / `EPN_TOOL_ID` | — / `10001` | link affiliati |
| `MAX_TRACKED_PER_CHAT` | `50` | minimo 1 |
| `HTTP_TIMEOUT` | `25.0` | |
| `REQUEST_DELAY_SECONDS` | `4.0` | pausa fra richieste eBay nel worker |
| `DROP_PENDING_UPDATES` | `0` | **default 0**: recupera i messaggi arrivati a bot spento |
| `PORT` | `7860` | porta endpoint di salute |
| `HF_BACKUP_REPO` / `HF_TOKEN` / `HF_BACKUP_FILENAME` | — / — / `nonnabot.db` | backup su dataset HF |
| `BACKUP_INTERVAL_SECONDS` | `300` | minimo 30, anti-rimbalzo |
| `LOG_LEVEL` | `INFO` | |
| `MAX_MESSAGE_LENGTH` (costante) | `3900` | Telegram ammette 4096 |

Helper di lettura: `_env_int`, `_env_float` (accetta la virgola), `_env_bool`
(vero: `1,true,vero,si,sì,yes,on` — falso: `0,false,falso,no,off` — vuoto o
incomprensibile → default).

### 3.6 Stringhe visibili all'utente (principali)

```
✅ Aggiunto al tracciamento come numero {n}:\n{titolo}\nPrezzo attuale: {prezzo}\n{url}
📉 Prezzo sceso da {vecchio} a {nuovo}!
📈 Prezzo aumentato da {vecchio} a {nuovo}!
⛔ L'inserzione è terminata, smetto di controllarla:
🗑️ Ho smesso di controllare:\n{titolo}
🧹 Fatto! Ho tolto {n} oggetti dal controllo.
👀 {n} oggetti sotto controllo:
Nessun oggetto sotto controllo 👵
Il numero {n} non esiste. Hai {tot} oggetti: usa "lista" per vederli.
📒 Changelog NonnaBot (ultime {n} versioni)
```

Prezzi formattati in stile italiano: `format_price(1234.5)` → `€1.234,50`;
`format_price(None)` → `n/d`. Simboli: `€ £ $`, `CHF` con lo spazio.

### 3.7 Log attesi all'avvio (in questo ordine)

```
Database pronto: {DATABASE_PATH}
NonnaBot v0.0.1 avviato — sito www.ebay.it, API Browse non configurate (scraping), intervallo 60 min
Endpoint di salute in ascolto su 0.0.0.0:7860        (solo con --with-health-endpoint)
Worker pianificato ogni 60 minuti
```

Logger: `logging.getLogger("nonnabot")`, formato
`%(asctime)s - %(name)s - %(levelname)s - %(message)s`.

### 3.8 Riga di comando

```
python main.py                     # in ascolto: comandi + controllo prezzi
python main.py --check-once        # un solo giro di controllo, poi esce (cron)
python main.py --add <link|ID>     # aggiunge (serve --chat-id o TELEGRAM_CHAT_ID)
python main.py --list [--chat-id N]
python main.py --remove <N>
python main.py --with-health-endpoint   # apre anche la porta HTTP di salute
python main.py --version           # "NonnaBot 0.0.1"
```

Codici di uscita: `0` ok · `1` errore di esecuzione/token · `2` errore d'uso
(ID non riconosciuto, chat mancante, limite raggiunto).

---

## 4. Blueprint di `main.py`

Sezioni nell'ordine, con le firme reali (i numeri di riga si riferiscono alla
versione con sha256 `0e589e5bcb59f6e9`).

**Import**: `argparse, asyncio, json, logging, os, random, re, shutil, sqlite3,
sys, threading, time`, `dataclasses`, `enum.Enum`, `types.SimpleNamespace`,
`typing`, `requests`, `bs4.BeautifulSoup`, `telegram.Update`,
`telegram.constants.ChatAction`, `telegram.error.{Forbidden, InvalidToken,
NetworkError, RetryAfter, TelegramError}`, `telegram.ext.{Application,
ApplicationBuilder, ContextTypes, MessageHandler, filters}`; `dotenv.load_dotenv`
in `try/except ImportError`.

1. **Versione e metadati** (riga 108): `__version__`, `BOT_NAME`, `BOT_USERNAME`,
   `CHANGELOG_FILE` (accanto a `main.py`).
2. **Configurazione** (121-196): `_env_int`, `_env_float`, `_env_bool`, poi tutte
   le costanti del §3.5 e `USE_BROWSE_API = bool(CLIENT_ID and CLIENT_SECRET)`.
   `HTTP_HEADERS` con User-Agent Chrome 124 e `Accept-Language: it-IT`.
3. **Testi fissi** (221): `build_help()` — **vedi §3.2, byte per byte**.
4. **Formattazione** (263, 275): `format_price`, `shorten`.
5. **`parse_price(raw)`** (292): accetta `"EUR 1.234,56"`, `"500.0"`, `"1,234.56"`,
   `"€49,99"`, spazi `\xa0`. Regole: se ci sono sia `.` sia `,` vince il più a
   destra; solo `,` → decimale; solo `.` → decimale **tranne** con 3 cifre
   decimali (`1.234` → 1234). Ritorna `None` se ≤ 0 o non numerico.
6. **`extract_item_id(text)`** (349): regex `_URL_RE` (URL http/https),
   `_ITM_RE = /itm/(?:[^/?#]*?[-/])?(\d{10,13})`, `_ITEM_PARAM_RE = [?&]item=(\d{10,13})`,
   `_DIGITS_RE = (\d{10,13})`, `_BARE_ID_RE = ^\d{10,13}$`. Cerca prima dentro le
   URL il cui host contenga `ebay`, poi l'ID nudo, poi i pattern sul testo.
7. **`build_item_url`** (379): `https://{EBAY_SITE}/itm/{id}`, con
   `?campid=&toolid=&mkevt=1` se `EPN_CAMPAIGN_ID` è impostata.
8. **Parsing pagina** (417-601): `_first`, `_from_json_ld` (visita iterativa dei
   blocchi `application/ld+json`, cerca `@type == Product` o `offers`, legge
   `name`/`offers.price`/`lowPrice`/`priceCurrency`), `_from_microdata`
   (`[itemprop=name|price|priceCurrency]`), `parse_ebay_page` con i selettori CSS
   ```
   _TITLE_SELECTORS = ("h1.x-item-title__mainTitle", "div.x-item-title__mainTitle span",
                       "h1.x-item-title__mainTitle span", "#itemTitle", "h1.it-ttl", "h1")
   _PRICE_SELECTORS = ("div.x-price-primary span.ux-labels-values__values",
                       "div.x-price-primary span", 'div[data-testid="x-price-primary"]',
                       "div.x-price-primary", "div.x-price__main span", "div.x-price__main",
                       "#prcIsum", "#mm-saleDscPrc", "span.notranslate")
   ```
   poi 4 regex di riserva (`"displayPrice":"…"`, `"price":"…"…priceCurrency`,
   l'ordine inverso, `EUR …,\d\d`). `EbayInfo.source` vale `json-ld`, `microdata`,
   `css` o `regex`. Inserzione conclusa: `_ENDED_MARKERS` (8 frasi in italiano e
   inglese). Prezzo assente → `raise ValueError`.
9. **Accesso a eBay** (604-764): `_browse_token` (OAuth client_credentials su
   `api.ebay.com/identity/v1/oauth2/token`, cache con scadenza),
   `_info_from_browse_api` (`GET /buy/browse/v1/item/{id}?fieldgroups=COMPACT`,
   header `X-EBAY-C-MARKETPLACE-ID`), `_http_get` (2 tentativi, backoff),
   `get_ebay_info` (valida l'ID con `\d{10,13}`; API → scraping → fallback su
   `www.ebay.com`).
10. **Database** (767-925): le funzioni del §3.4 più `list_items`,
    `find_by_index`, `find_by_item_id`, `count_items`, `add_item`, `delete_item`,
    `clear_items`, `all_tracked_items` (indici ricalcolati per chat),
    `update_price`, `update_title`, `touch_checked`, `mark_ended`.
    `@dataclass TrackedItem(row_id, index, chat_id, item_id, last_price, title,
    url, currency, ended, last_checked)`.
11. **Parsing comandi** (930-1027): `enum Action` con `IGNORE, HELP, LIST, CLEAR,
    CHANGELOG, DELETE, DELETE_USAGE, LINK, LINK_USAGE, ADD, UNKNOWN`,
    `@dataclass Parsed(action, value)`, `parse_message` come in §3.3.
12. **Risposte** (1030-1125): `format_list`, `describe_price_change` (soglia
    `abs(delta) < 0.005` → nessuna notifica), `format_changelog(md, max_versions=3)`
    (estrai i blocchi che iniziano con `## `), `split_message` (mai oltre
    `MAX_MESSAGE_LENGTH`), `read_changelog`.
13. **`send_text`** (1128): spezza, gestisce `RetryAfter` (attesa + retry),
    `Forbidden` (si arrende), `NetworkError`/`TelegramError` (log).
14. **Azioni** (1152-1341): `action_help/list/clear/changelog/delete/link/add/
    unknown`, poi `route_message` che smista; ogni eccezione è catturata,
    loggata con `logger.exception` e risponde con un messaggio di cortesia.
    In `action_add`: duplicato → avviso; limite → rifiuto; `send_chat_action`
    TYPING; `asyncio.to_thread(get_ebay_info, …)`; poi `add_item` e
    `salva_database(True)`.
15. **`check_prices_job`** (1344): per ogni oggetto non concluso: pausa
    `REQUEST_DELAY_SECONDS + random(0,1.5)`, `get_ebay_info`; se `ended` →
    `mark_ended` + notifica; se il titolo è cambiato → `update_title`;
    `describe_price_change` → notifica; `update_price` oppure `touch_checked`;
    alla fine `salva_database(True)` se ci sono state variazioni.
16. **`_schedule_jobs`** (1409) e **`build_application`** (1428): un solo handler
    ```python
    MessageHandler(filters.TEXT | filters.COMMAND | filters.UpdateType.CHANNEL_POST,
                   route_message, block=False)
    ```
    con `ApplicationBuilder().token(…).concurrent_updates(True).build()`; job
    `run_repeating(check_prices_job, interval=CHECK_INTERVAL_MINUTES*60, first=60,
    name="check_prices")`.
17. **`avvia_health_server(port)`** (1454): `ThreadingHTTPServer` su `0.0.0.0`,
    `do_GET` risponde `200` con
    `{"stato":"ok","bot":"NonnaBot","versione":"0.0.1"}`, `log_message` disattivato,
    thread demone, **ritorna il server**.
18. **Backup su Hub** (1484-1550): `_hub_attivo`, `ripristina_database`
    (`hf_hub_download` + `shutil.copyfile`), `salva_database(force)`
    (`HfApi.upload_file(..., repo_type="dataset")`) con anti-rimbalzo su
    `_ultimo_backup`; `huggingface_hub` importato **dentro** le funzioni.
19. **`run_check_once`** (1553): `ApplicationBuilder().token(…).build()`,
    `await initialize()` **dentro** il `try`, flag `inizializzata`,
    `check_prices_job(SimpleNamespace(bot=app.bot))`, `finally: shutdown()` solo
    se inizializzata.
20. **CLI** (1574-1725): `parse_args` (§3.8), `_errore_chat_mancante`,
    `_chat_id_riferimento` (`--chat-id` vince su `TELEGRAM_CHAT_ID`), `cli_add`,
    `cli_remove`, `cli_list`.
21. **`main(argv)`** (1728): `ripristina_database()` → `init_db()` → opzioni CLI
    (senza token) → controllo token → log di avvio → `--check-once` (con
    `InvalidToken`/`TelegramError` tradotti in `exit 1`) → eventuale health
    endpoint → `run_polling(allowed_updates=Update.ALL_TYPES,
    drop_pending_updates=DROP_PENDING_UPDATES)`.

---

## 5. File riprodotti per intero (byte-per-byte)

### 5.1 `requirements.txt`

```
# NonnaBot — dipendenze (Python 3.10+)
# Installazione: pip install -r requirements.txt

# Libreria Telegram asincrona; l'extra [job-queue] serve al controllo prezzi periodico.
python-telegram-bot[job-queue]>=20.8,<23.0

# Chiamate HTTP verso eBay (scraping e API Browse).
requests>=2.31,<3.0

# Parsing dell'HTML della pagina oggetto.
beautifulsoup4>=4.12,<5.0

# Caricamento del file .env in sviluppo locale (opzionale su Render/PythonAnywhere).
python-dotenv>=1.0,<2.0

# Salvataggio del database su un repo dataset di Hugging Face:
# indispensabile su Hugging Face Spaces, dove il disco è effimero.
huggingface_hub>=0.24,<1.0

# --- solo per eseguire i test (non necessarie in produzione) ---
# pytest>=8.0,<9.0
```

### 5.2 `Dockerfile`

```dockerfile
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
```

### 5.3 `.env.example`

```
# Copia questo file in ".env" (git lo ignora) e compila i valori.
# Su Render/PythonAnywhere le stesse variabili si impostano dal pannello.

# --- Obbligatoria -----------------------------------------------------------
# Token fornito da @BotFather (/newbot). NON condividerlo mai.
TELEGRAM_BOT_TOKEN=

# La tua chat Telegram: serve solo se aggiungi oggetti da riga di comando
# (GitHub Actions / cron). Il numero te lo dice @userinfobot su Telegram.
TELEGRAM_CHAT_ID=

# --- Facoltative ------------------------------------------------------------
# Percorso del database SQLite. Su Render punta a un disco montato (es. /data).
DATABASE_PATH=nonnabot.db

# Ogni quanti minuti ricontrollare i prezzi (minimo 5).
CHECK_INTERVAL_MINUTES=60

# Sito eBay usato per i link generati.
EBAY_SITE=www.ebay.it

# API ufficiali eBay Browse (developer.ebay.com). Se presenti, il bot le usa
# al posto dello scraping: più stabili e senza rischio di blocco IP.
EBAY_CLIENT_ID=
EBAY_CLIENT_SECRET=
EBAY_MARKETPLACE_ID=EBAY_IT
EBAY_LANG=it-IT

# eBay Partner Network: se compili la campagna, i link diventano affiliati.
EPN_CAMPAIGN_ID=
EPN_TOOL_ID=10001

# Limiti e tempi.
MAX_TRACKED_PER_CHAT=50

# Se il bot era spento quando gli hai scritto: 0 = recupera quei messaggi
# all'accensione (consigliato), 1 = li butta via.
DROP_PENDING_UPDATES=0
REQUEST_DELAY_SECONDS=4
HTTP_TIMEOUT=25

# Livello di logging: DEBUG, INFO, WARNING, ERROR.
LOG_LEVEL=INFO
```

### 5.4 `deploy/nonnabot.env.example`

```
# /etc/nonnabot.env — letto da systemd con EnvironmentFile=
# Copialo, compilalo e proteggi il file:  chmod 600 /etc/nonnabot.env
#
# Questo file NON va nel repository: contiene i segreti.

# --- Obbligatoria -----------------------------------------------------------
TELEGRAM_BOT_TOKEN=

# --- eBay (opzionali: con queste il bot usa le API ufficiali) ---------------
EBAY_CLIENT_ID=
EBAY_CLIENT_SECRET=
EBAY_MARKETPLACE_ID=EBAY_IT

# --- Affiliazione eBay Partner Network (opzionale) --------------------------
EPN_CAMPAIGN_ID=

# --- Configurazione ---------------------------------------------------------
DATABASE_PATH=/opt/nonnabot/nonnabot.db
CHECK_INTERVAL_MINUTES=60
EBAY_SITE=www.ebay.it
MAX_TRACKED_PER_CHAT=50
REQUEST_DELAY_SECONDS=4
LOG_LEVEL=INFO
```

### 5.5 `deploy/github/README.md`

````
# Workflow GitHub Actions (da copiare in `.github/workflows/`)

Questi due file sono i workflow del progetto. Sono qui **in copia** perché la
connessione GitHub usata in sviluppo non ha il permesso `workflows` e non può
scrivere direttamente dentro `.github/workflows/`.

Per attivarli, dalla radice del repository:

```bash
mkdir -p .github/workflows
cp deploy/github/tests.yml        .github/workflows/tests.yml
cp deploy/github/check-prezzi.yml .github/workflows/check-prezzi.yml
git add .github && git commit -m "ci: attiva i workflow" && git push
```

Poi su GitHub:

1. `Settings → Secrets and variables → Actions → New repository secret`
   aggiungi `TELEGRAM_BOT_TOKEN` (facoltativi: `EBAY_CLIENT_ID`,
   `EBAY_CLIENT_SECRET`).
2. `Actions → Controllo prezzi (cron) → Run workflow` per una prova immediata.

`tests.yml` non richiede nessun segreto: esegue i test a ogni push.
`check-prezzi.yml` gira ogni ora e usa i segreti per mandare le notifiche.

Vedi [DEPLOY.md](../../DEPLOY.md) per i limiti di questa modalità.
````

### 5.6 `deploy/huggingface/space-README.md`

```markdown
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
```

---

## 6. Test: i 65 contratti di `tests/test_bot.py`

120 test (65 funzioni, alcune parametrizzate). Fixture `temp_database`
(autouse): database SQLite temporaneo via `monkeypatch.setattr(main,
"DATABASE_PATH", …)`, `MAX_TRACKED_PER_CHAT=50`, `REQUEST_DELAY_SECONDS=0.0`,
poi `main.init_db()`. `FakeBot` registra i messaggi; gli handler vengono provati
anche con veri `telegram.Update`. **Nessun test tocca la rete.**

```
test_aggiunta_fallita                         test_aggiunta_link_e_duplicato
test_all_tracked_items_indici_per_chat        test_build_application_registra_handler_e_job
test_build_item_url_con_e_senza_affiliazione  test_cancella_e_azzera
test_changelog_assente                        test_changelog_da_telegram
test_changelog_estratto_dal_file_reale        test_chat_diverse_non_si_disturbano
test_chat_id_da_variabile_ambiente            test_check_once_chiude_tutto_anche_se_initialize_fallisce
test_check_once_esegue_il_giro_e_chiude_tutto test_check_once_notifica_le_variazioni
test_cli_add_duplicato_e_limite               test_cli_add_gli_errori
test_cli_add_lista_remove                     test_cli_list_tutte_le_chat
test_cli_remove_inesistente                   test_comando_aiuto
test_comando_lista_vuota_e_piena              test_db_aggiornamento_prezzo_e_stato
test_db_indice_progressivo_e_cancellazione    test_default_non_butta_i_messaggi_in_attesa
test_env_bool                                 test_extract_item_id_varianti
test_flag_health_endpoint_esiste              test_format_list
test_format_list_vuota                        test_format_price_stile_italiano
test_get_ebay_info_api_browse                 test_get_ebay_info_pagina_non_raggiungibile
test_get_ebay_info_rifiuta_id_non_validi      test_get_ebay_info_usa_html_scaricato
test_handler_non_bloccante                    test_handler_reale_con_update_telegram
test_health_endpoint_risponde_veramente       test_hub_disattivato_se_non_configurato
test_main_check_once_passa_dalla_cli          test_main_check_once_traduce_gli_errori_telegram
test_main_gestisce_le_opzioni_cli             test_main_senza_token_esce_con_errore
test_messaggio_di_aiuto_esatto                test_messaggio_sconosciuto
test_notifica_di_variazione_prezzo            test_numero_restituisce_il_link
test_parse_args                               test_parse_message
test_parse_message_ignora_casualita_e_spazi   test_parse_page_css
test_parse_page_inserzione_terminata          test_parse_page_json_ld
test_parse_page_microdata                     test_parse_page_regex_di_riserva
test_parse_page_senza_prezzo_solleva_errore   test_parse_price
test_ripristina_database_copia_il_file        test_ripristina_database_tollera_primo_avvio
test_salva_database_non_esplode_se_hub_fallisce  test_salva_database_su_hub_con_anti_rimbalzo
test_split_message_rispetta_il_limite         test_worker_aggiorna_il_titolo_nel_database
test_worker_gestisce_inserzione_terminata     test_worker_notifica_ribasso_e_rincaro
test_worker_resiste_a_oggetti_non_raggiungibili
```

I fixture HTML dentro il test si chiamano `JSON_LD_PAGE`, `MICRODATA_PAGE`,
`CSS_ONLY_PAGE`, `RAW_JSON_PAGE`, `ENDED_PAGE`, `NO_PRICE_PAGE` e riproducono il
markup reale di ebay.it (l'oggetto di riferimento è `405399021732`,
*"Apple iPhone 13 - 128GB - Bianco"*, JSON-LD `price":"500.0"`,
`priceCurrency":"EUR"`).

---

## 7. Come verificare la ricostruzione

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt pytest
python -m pytest tests/ -q            # atteso: 120 passed
python main.py --version              # atteso: NonnaBot 0.0.1
python main.py --check-once           # senza token: exit 1 con errore chiaro
sha256sum main.py requirements.txt    # confronta con il §2
```

Il messaggio di aiuto va confrontato **byte per byte** con il §3.2.
L'endpoint di salute si prova così (HTTP reale, nessuna rete esterna):

```python
import main; s = main.avvia_health_server(0); print(s.server_address[1])
# poi: curl http://127.0.0.1:<porta>/  → 200 {"stato":"ok","bot":"NonnaBot","versione":"0.0.1"}
```

---

## 8. Stato alla fine della sessione (2026-08-28)

* Repository: `PiBOH/nonna_ebay_bot`, branch **`arena/01a0485f-nonna-ebay-bot`**,
  pull request **#1** (`base main`) → <https://github.com/PiBOH/nonna_ebay_bot/pull/1>.
* **Su GitHub** ci sono i commit fino a `574e5e0` (15 file).
* **Solo in locale** (push bloccato da un guasto TLS della sandbox verso
  `github.com` e `api.github.com`): `a547277` (script di avvio),
  `9c8b5c9` (fix `drop_pending_updates`), `511319a` (Hugging Face Spaces).
  Un push li aggancia automaticamente alla PR #1.
* `.github/workflows/*.yml` **non sono pushabili** da questa sandbox: il token
  GitHub App non ha il permesso `workflows`. Per questo esistono le copie in
  `deploy/github/`.
* L'utente ha creato: un token Hugging Face (nome `nonnabot`) e uno Space vuoto.
  Mancano: il token di Telegram (`/token` a @BotFather), i 4 file nello Space
  (`main.py`, `requirements.txt`, `Dockerfile`, `README.md` ← da
  `deploy/huggingface/space-README.md`) e i secret nello Space.

### Cose in sospeso (roadmap)

- [ ] Notifiche opzionali solo al ribasso (impostazione per chat)
- [ ] Più siti eBay nello stesso comando (`ebay.de`, `ebay.com`)
- [ ] Prezzo obiettivo con avviso dedicato
- [ ] `docker build` mai eseguito (nessun Docker in sandbox)
- [ ] Test su Python 3.10 e 3.12 (in sandbox c'era solo 3.11.2)
- [ ] Chiamate reali a eBay/Telegram/HF mai collaudate (sandbox senza rete)

## 9. Regole per chi continua

1. Non rinominare di nuovo il bot: è **NonnaBot**, non MiaNonnaBot.
2. Il messaggio di aiuto (§3.2) è un contratto: non "migliorarlo".
3. Ogni modifica a `main.py` deve lasciare verdi i 120 test; se cambi un
   comportamento, aggiorna il test **e** il `CHANGELOG.md` (Keep a Changelog).
4. I segreti non vanno mai committati: `.gitignore` esclude `.env`, `*.db`,
   `__pycache__`, `.venv`, cache di test e linting.
5. Prima di dichiarare una cosa "fatta": esegui il comando e riporta l'output.
   Ciò che non si può verificare va detto esplicitamente.