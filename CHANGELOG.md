# Changelog

Tutte le modifiche rilevanti a **NonnaBot** sono documentate in questo file.

Il formato segue [Keep a Changelog](https://keepachangelog.com/it/1.1.0/)
e il progetto aderisce al [Semantic Versioning](https://semver.org/lang/it/).

Le versioni `0.x.y` sono di sviluppo: l'API e i comandi possono cambiare senza preavviso.

## [Unreleased]

### Aggiunto
- Supporto a **Hugging Face Spaces** (hosting gratuito senza carta di credito):
  `Dockerfile`, flag `--with-health-endpoint` che apre una porta HTTP di salute
  (gli Space Docker devono rispondere su `app_port`, un bot in polling no),
  e `deploy/huggingface/` con il `README.md` dello Space e la guida passo passo.
- Salvataggio del database su un repo *dataset* di Hugging Face
  (`HF_BACKUP_REPO`, `HF_TOKEN`): il ripristino avviene all'avvio e il
  salvataggio dopo ogni modifica e a ogni giro del worker, con anti-rimbalzo.
  Serve perché gli Space Docker perdono il disco a ogni riavvio.
- Workflow `keep-alive.yml`: risveglia lo Space ogni 6 ore (dopo 48 h senza
  visite si addormenta).
- Dipendenza `huggingface_hub` per il backup sull'Hub.
- Script di avvio `avvia.sh` (Linux/macOS) e `avvia.bat` (Windows): creano
  l'ambiente virtuale, installano le dipendenze, generano `.env` e avviano il
  bot. Controllano la versione di Python e che il token sia stato compilato,
  con messaggi in italiano.
- Comandi da riga di comando `--add <link>`, `--list`, `--remove <num>` e
  `--chat-id`: permettono di gestire la lista anche dove non si può tenere un
  processo sempre acceso (GitHub Actions, cron, script).
- Variabile `TELEGRAM_CHAT_ID`: chat di destinazione per gli oggetti aggiunti da
  riga di comando.
- Workflow GitHub Actions `gestisci-lista.yml`: aggiungi/elenco/rimuovi dal sito
  di GitHub con *Run workflow*, senza segreti nello script (i valori viaggiano
  come variabili d'ambiente).
- Modalità `python main.py --check-once`: esegue un solo giro di controllo prezzi
  e termina, per gli ambienti che non ospitano un processo residente
  (cron di GitHub Actions, scheduled task, crontab).
- Argomenti da riga di comando `--check-once`, `--version` e `--help`.
- Gestione pulita degli errori in modalità one-shot: token rifiutato o Telegram
  irraggiungibile producono un messaggio di log e `exit 1` invece di un traceback.
- Workflow GitHub Actions `tests.yml`: esegue i test su Python 3.10/3.11/3.12 a
  ogni push, senza bisogno di segreti.
- Workflow GitHub Actions `check-prezzi.yml`: controllo prezzi orario con i
  segreti letti da GitHub Secrets e database conservato nella cache.
- `render.yaml`: blueprint Render con worker, disco persistente e segreti
  marcati `sync: false` (il valore lo chiede la dashboard, non sta nel repo).
- `deploy/`: unit systemd `nonnabot.service` e modello `/etc/nonnabot.env`
  per l'installazione su VPS, Raspberry Pi o PC.
- `DEPLOY.md`: guida a dove mettere token e chiavi per ogni piattaforma, con una
  tabella delle opzioni gratuite che **non richiedono carta di credito**.

### Corretto
- All'avvio il bot **non butta più via i messaggi arrivati mentre era spento**
  (`drop_pending_updates` era `True`): ora li recupera e li esegue, quindi il
  link incollato a PC spento viene aggiunto all'accensione. Il comportamento
  vecchio resta disponibile con `DROP_PENDING_UPDATES=1`.

### Modificato
- **Il bot si chiama NonnaBot** (prima MiaNonnaBot): aggiornato in codice,
  messaggio di aiuto, documentazione, database di default (`nonnabot.db`),
  logger, unit systemd e blueprint Render.
- Documentazione di installazione corretta: i **Background Worker di Render non
  hanno piano gratuito** e il piano gratuito di **PythonAnywhere** non basta
  (niente always-on task e allowlist in uscita che non comprende eBay).

### Da fare
- [ ] Notifiche opzionali solo al ribasso (impostazione per chat).
- [ ] Supporto a più siti eBay nello stesso comando (es. ebay.de, ebay.com).
- [ ] Comando per impostare un prezzo obiettivo con avviso dedicato.
- [ ] Persistenza del database fuori da SQLite per la modalità GitHub Actions.

## [0.0.1] - 2026-08-28

Prima release pubblica di sviluppo.

### Aggiunto
- Comando di aiuto raggiungibile con `aiuto`, `help`, `h`, `/start`, `/aiuto`, `/help`, `/h`
  (testo e comandi sono tutti insensibili alle maiuscole/minuscole).
- Tracciamento di un oggetto eBay incollando semplicemente il link in chat: il bot
  estrae l'ID con regex, recupera titolo e prezzo e conferma l'indice assegnato.
- Comando `lista` / `list` / `l`: elenco numerato degli oggetti sotto controllo.
- Comando `cancella <numero>`: rimuove il prodotto con quell'indice.
- Comando `azzera`: elimina tutti i prodotti della chat.
- Comando `numero <n>`, il numero inviato da solo (`1`) o `/1`: richiama il link del prodotto n.
- Comando `changelog`: mostra il registro delle modifiche direttamente su Telegram.
- Database SQLite con tabella `tracciamenti`
  (`id`, `chat_id`, `item_id_ebay`, `last_price`, `title`, `url` + colonne di servizio)
  e indice progressivo ricalcolato per chat.
- Worker in background (job queue) che ricontrolla i prezzi ogni 60 minuti e invia
  `📉 Prezzo sceso da €X a €Y!` oppure `📈 Prezzo aumentato da €X a €Y!` con il link.
- Estrazione dati eBay a più livelli di fallback: JSON-LD, microdata, selettori CSS
  e regex sul grezzo; supporto opzionale alle API ufficiali **eBay Browse**
  tramite `EBAY_CLIENT_ID` / `EBAY_CLIENT_SECRET`.
- Rilevamento delle inserzioni concluse: il bot avvisa e smette di controllarle.
- Formattazione prezzi in stile italiano (`€1.234,50`) e messaggi lunghi spezzati
  automaticamente per rispettare il limite di 4096 caratteri di Telegram.
- Rispetto del flood control di Telegram (gestione di `RetryAfter` e `Forbidden`).
- Configurazione completa via variabili d'ambiente, pronta per Render e PythonAnywhere.
- Suite di test automatici (`tests/`) per parsing comandi, prezzi, pagina eBay e database.

[unreleased]: https://github.com/PiBOH/nonna_ebay_bot/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/PiBOH/nonna_ebay_bot/releases/tag/v0.0.1