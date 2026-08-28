# Dove metto i parametri (token, chiavi, configurazione)

## La cosa importante da capire

**GitHub conserva il codice, non lo esegue.** Un bot Telegram deve restare
acceso 24 ore su 24 per ricevere i tuoi messaggi: un repository Git non può
farlo. Quindi i parametri **non vanno mai scritti nei file del repository**
(fincherebbero in chiaro nella storia di Git, per sempre), ma vanno messi
**dove il bot gira**.

```
┌──────────────────┐          ┌───────────────────────────────┐
│      GitHub      │  deploy  │  Un runtime (server)          │
│  solo il codice  │ ───────► │  qui stanno i parametri       │
│  + i SEGRETI     │          │  (variabili d'ambiente)       │
│    (cassaforte)  │          │  python main.py               │
└──────────────────┘          └───────────────────────────────┘
```

GitHub può fare **due** cose utili: tenere il codice, e fare da **cassaforte**
per i segreti (Settings → Secrets). Poi li passa al runtime come variabili
d'ambiente.

## Quale parametro va dove

| Parametro | Tipo | In chiaro? |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | **Segreto** | ❌ mai nel repo |
| `EBAY_CLIENT_ID` | **Segreto** | ❌ mai nel repo |
| `EBAY_CLIENT_SECRET` | **Segreto** | ❌ mai nel repo |
| `EPN_CAMPAIGN_ID` | **Segreto** | ❌ mai nel repo |
| `DATABASE_PATH`, `EBAY_SITE`, `CHECK_INTERVAL_MINUTES`, `LOG_LEVEL`… | Configurazione | ✅ si può committare |

Nel repository c'è solo [`.env.example`](.env.example), che è un **modello
vuoto**: lo copi, lo compili sul server e `.gitignore` lo tiene fuori da Git.

---

## Opzione A — Solo GitHub (gratis, con limiti)

GitHub non tiene acceso un processo, ma può **svegliarsi a orari fissi** con
GitHub Actions. In questa modalità ricevi le **notifiche di variazione prezzo**,
ma il bot **non risponde ai comandi** (`lista`, `cancella`, `azzera`…).

1. **Crea il segreto**
   `GitHub → il tuo repo → Settings → Secrets and variables → Actions →
   New repository secret`
   * Name: `TELEGRAM_BOT_TOKEN` — Secret: *(il token di @BotFather)*
   * Facoltativi, stessi passaggi: `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET`.
2. **Verifica** in `Actions → Controllo prezzi (cron)` che il workflow esista
   (è già nel repo: [`.github/workflows/check-prezzi.yml`](.github/workflows/check-prezzi.yml)).
3. Premi **Run workflow** per provarlo subito.
4. Da lì in poi parte da solo ogni ora (`cron: "17 * * * *"`).

**Limiti da conoscere**

* Niente comandi interattivi: serve un processo residente (opzioni B/C/D).
* Il database vive nella cache di Actions, che scade dopo **7 giorni** senza
  accessi: se succede, la lista dei prodotti riparte da zero.
* I cron di GitHub partono spesso con **10-30 minuti di ritardo** e vengono
  **disabilitati dopo 60 giorni** di inattività del repository.
* Su repo privati hai **2.000 minuti/mese** inclusi (uno pubblico è illimitato).
* L'IP dei runner è condiviso: eBay può rispondere con un blocco. Con le chiavi
  API (`EBAY_CLIENT_ID`/`SECRET`) il problema sparisce.

---

## Opzione B — Render (Background Worker)

⚠️ **I Background Worker su Render non hanno piano gratuito**: la pagina
ufficiale dice che solo Web Service, Postgres e Key Value hanno istanze free.
Il worker parte da **7 $/mese** (+ 0,25 $/GB/mese per il disco persistente, che
ti serve per non perdere il database a ogni deploy). Il Web Service gratuito si
spegne dopo 15 minuti senza traffico in entrata — e un bot in polling non ne fa:
non va bene.

1. Push del codice su GitHub (già fatto).
2. `dashboard.render.com → New → Background Worker →` collega il repo.
3. Build `pip install -r requirements.txt` — Start `python main.py`.
4. **Environment** → aggiungi `TELEGRAM_BOT_TOKEN` (e le eventuali chiavi eBay).
5. **Disk** → mount path `/data`, 1 GB → poi `DATABASE_PATH=/data/mianonnabot.db`.

Il repo contiene [`render.yaml`](render.yaml): su Render puoi usare
**New → Blueprint** e il servizio si configura da solo; i valori marcati
`sync: false` te li chiede la dashboard e non finiscono nel repo.

---

## Opzione C — PythonAnywhere

⚠️ **Il piano gratuito (Beginner) non funziona per questo bot**, per due motivi
verificati sulla pagina ufficiale dei piani:

* niente **always-on task** e niente **scheduled task** (sono funzioni a pagamento);
* l'accesso in uscita è limitato a una **allowlist** di siti, e **ebay.it non
  c'è** → il bot non riuscirebbe a leggere i prezzi.

Serve il piano **Developer a 10 $/mese** (1 always-on task, internet senza
restrizioni). Lì i parametri si mettono così:

```bash
# 1. crea il file dei segreti (NON è nel repository)
nano ~/mianonnabot/.env
#    TELEGRAM_BOT_TOKEN=123456789:AAAA...
chmod 600 ~/mianonnabot/.env      # leggibile solo da te
```

Poi in **Tasks → Always-on task**:

```
/home/TUOUSER/mianonnabot/.venv/bin/python /home/TUOUSER/mianonnabot/main.py
```

Il bot carica `.env` da solo (usa `python-dotenv`).

---

## Opzione D — VPS (anche gratis: Oracle Cloud Always Free)

Un piccolo server Linux tiene acceso il bot senza costi e senza limiti di rete.
Nel repo trovi [`deploy/`](deploy/): copia i due file e sistema i percorsi.

```bash
sudo useradd --system --create-home --home-dir /opt/mianonnabot mianonnabot
sudo git clone https://github.com/PiBOH/nonna_ebay_bot /opt/mianonnabot
cd /opt/mianonnabot && sudo -u mianonnabot python3 -m venv .venv
sudo -u mianonnabot .venv/bin/pip install -r requirements.txt

# i segreti stanno qui, fuori dal repository, permessi 600
sudo cp deploy/mianonnabot.env.example /etc/mianonnabot.env
sudo nano /etc/mianonnabot.env     # incolla il token
sudo chmod 600 /etc/mianonnabot.env && sudo chown root:root /etc/mianonnabot.env

sudo cp deploy/mianonnabot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now mianonnabot
journalctl -u mianonnabot -f       # guarda i log
```

---

## In locale, per provare

```bash
cp .env.example .env      # .gitignore lo esclude da Git
nano .env                 # incolla il token
python main.py
```

---

## Se un segreto finisce per errore su GitHub

1. **Revocalo subito**: @BotFather → `/revoke` (per il token Telegram) oppure
   rigenera le credenziali su developer.ebay.com.
2. Poi rimuovilo dalla storia con `git filter-repo` e forza il push.
3. Ricorda: cancellare il file in un commit successivo **non basta**, il valore
   resta nei commit precedenti.
