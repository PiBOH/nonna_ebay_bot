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

## Se non vuoi spendere nulla (e non hai carta di credito)

**Risposta breve: Hugging Face Space (Opzione E)** — bot completo, sempre
acceso, senza carta. In alternativa il tuo PC (Opzione D) o, se ti bastano
le notifiche senza chat, GitHub Actions (Opzione A).

Ho verificato lo stato dei piani gratuiti ad agosto 2026:

| Piattaforma | Gratis? | Carta? | Va bene per NonnaBot? |
| --- | --- | --- | --- |
| **GitHub Actions** | ✅ | ❌ non serve | ✅ **sì**, ma solo notifiche + lista manuale |
| **Il tuo PC / Raspberry Pi** | ✅ | ❌ | ✅ sì, bot completo (deve restare acceso) |
| **Hugging Face Spaces** | ✅ | ❌ | ✅ **sì**: già configurato, vedi Opzione E |
| Koyeb | ✅ | ⚠️ "di solito no" | ⚠️ l'istanza free non fa da worker e va a zero senza traffico |
| PythonAnywhere (Beginner) | ✅ | ❌ | ❌ no always-on task e allowlist senza eBay |
| Render | ⚠️ solo web service | ✅ richiesta | ❌ i worker sono a pagamento |
| Fly.io | ❌ solo trial ~2 ore | ✅ richiesta | ❌ |
| Oracle Cloud Always Free | ✅ | ✅ richiesta | ❌ senza carta non ti registri |

Fonti: [Render — piani gratuiti](https://render.com/docs/free) ("Other service
types don't support Free instances"), [PythonAnywhere — piani](https://www.pythonanywhere.com/pricing/)
e [allowlist](https://www.pythonanywhere.com/whitelist/), [Hugging Face —
gestione Spaces](https://huggingface.co/docs/huggingface_hub/en/guides/manage-spaces)
("cpu-basic … automatically be paused after 48h of inactivity").

### Cosa ottieni con GitHub Actions (Opzione A)

* ✅ Ricevi le notifiche 📉/📈 ogni ora.
* ✅ Aggiungi e togli oggetti dal sito di GitHub, col pulsante **Run workflow**.
* ✅ Zero costi, zero carta, zero server da mantenere.
* ❌ Il bot **non risponde** quando gli scrivi su Telegram: per quello serve un
  processo sempre acceso (Opzione D sul tuo PC, o più avanti uno Space).

---

## Opzione A — Solo GitHub (gratis, senza carta)

GitHub non tiene acceso un processo, ma può **svegliarsi a orari fissi** con
GitHub Actions. Sono già pronti tre workflow (in `deploy/github/`, da copiare in
`.github/workflows/` come spiegato in [`deploy/github/README.md`](deploy/github/README.md)):

| Workflow | Cosa fa | Quando parte |
| --- | --- | --- |
| `tests.yml` | esegue i test | a ogni push |
| `gestisci-lista.yml` | aggiunge / elenca / rimuove oggetti | quando premi **Run workflow** |
| `check-prezzi.yml` | controlla i prezzi e notifica | ogni ora |

**Configurazione, una tantum**

1. `Settings → Secrets and variables → Actions → Secrets → New repository secret`
   * Name `TELEGRAM_BOT_TOKEN` — Secret: il token di @BotFather
   * facoltativi: `EBAY_CLIENT_ID`, `EBAY_CLIENT_SECRET`
2. Tab **Variables** → `New repository variable`
   * Name `TELEGRAM_CHAT_ID` — Value: il tuo numero di chat.
     Per scoprirlo scrivi a [@userinfobot](https://t.me/userinfobot) su Telegram.
3. `Actions → Gestisci lista (manuale) → Run workflow →` scegli `aggiungi` e
   incolla il link eBay.

**Uso quotidiano**

* aggiungere: `Run workflow → aggiungi → <link eBay>`
* vedere la lista: `Run workflow → lista` (l'elenco finisce nel log del run)
* togliere: `Run workflow → rimuovi → <numero>`

**Limiti da conoscere**

* Il database vive nella **cache** di Actions, che scade dopo **7 giorni** senza
  accessi: con il cron orario resta viva, ma se disattivi il workflow perdi la lista.
* I cron di GitHub partono spesso con **10-30 minuti di ritardo** e vengono
  **disabilitati dopo 60 giorni** di inattività del repository (basta un commit
  per riattivarli).
* Repo pubblico = minuti illimitati; repo privato = 2.000 minuti/mese.
* L'IP dei runner è condiviso: eBay può rispondere con un blocco. Con le chiavi
  API il problema sparisce.

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
5. **Disk** → mount path `/data`, 1 GB → poi `DATABASE_PATH=/data/nonnabot.db`.

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
nano ~/nonnabot/.env
#    TELEGRAM_BOT_TOKEN=123456789:AAAA...
chmod 600 ~/nonnabot/.env      # leggibile solo da te
```

Poi in **Tasks → Always-on task**:

```
/home/TUOUSER/nonnabot/.venv/bin/python /home/TUOUSER/nonnabot/main.py
```

Il bot carica `.env` da solo (usa `python-dotenv`).

---

## Opzione D — Il tuo PC, un Raspberry Pi o un VPS (gratis, bot completo)

È l'unico modo **a costo zero e senza carta** per avere il bot completo, comandi
compresi: il processo sta acceso su una macchina tua. Un vecchio PC o un
Raspberry Pi vanno benissimo (il bot usa pochi MB di RAM).

### Sul tuo PC (il modo più semplice)

Scarica il repository e fai doppio clic su **`avvia.bat`** (Windows) o esegui
**`bash avvia.sh`** (Linux/macOS). Lo script fa tutto da solo e al primo giro ti
chiede solo di incollare il token dentro `.env`.

Se preferisci a mano:

```bash
git clone https://github.com/PiBOH/nonna_ebay_bot.git
cd nonna_ebay_bot
python3 -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env && nano .env                  # incolla il token
python main.py
```

Finché quella finestra è aperta il bot funziona: risponde ai comandi **e**
controlla i prezzi ogni ora.

### Su un VPS Linux (o un Raspberry Pi sempre acceso)

Qui il bot parte da solo a ogni riavvio grazie a systemd. Nel repo trovi
[`deploy/`](deploy/): copia i due file e sistema i percorsi.

```bash
sudo useradd --system --create-home --home-dir /opt/nonnabot nonnabot
sudo git clone https://github.com/PiBOH/nonna_ebay_bot /opt/nonnabot
cd /opt/nonnabot && sudo -u nonnabot python3 -m venv .venv
sudo -u nonnabot .venv/bin/pip install -r requirements.txt

# i segreti stanno qui, fuori dal repository, permessi 600
sudo cp deploy/nonnabot.env.example /etc/nonnabot.env
sudo nano /etc/nonnabot.env      # incolla il token
sudo chmod 600 /etc/nonnabot.env && sudo chown root:root /etc/nonnabot.env

sudo cp deploy/nonnabot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now nonnabot
journalctl -u nonnabot -f        # guarda i log
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

---

## Opzione E — Hugging Face Space (gratis, senza carta, sempre acceso) ⭐

È l'opzione che dà il **bot completo sempre raggiungibile su Telegram** senza
spendere nulla e senza carta di credito: il container sta acceso in cloud.

**Guida passo passo (15 minuti, tutto dal browser):
[`deploy/huggingface/ISTRUZIONI.md`](huggingface/ISTRUZIONI.md)**

Cosa contiene il repository per questa modalità:

| File | A cosa serve |
| --- | --- |
| `Dockerfile` | immagine dello Space (utente UID 1000, porta 7860) |
| `main.py --with-health-endpoint` | il bot + una porta HTTP di salute per la piattaforma |
| `deploy/huggingface/space-README.md` | il `README.md` dello Space, con `sdk: docker` e `app_port` |
| `deploy/huggingface/ISTRUZIONI.md` | la guida |
| `deploy/github/keep-alive.yml` | lo risveglia ogni 6 ore |

Tre limiti da conoscere, tutti verificati sulla documentazione ufficiale:

* **Il disco è effimero**: *"The data written on disk is lost whenever your
  Docker Space restarts"*. Per questo il database viene salvato su un repo
  *dataset* gratuito (`HF_BACKUP_REPO` + `HF_TOKEN`).
* **Dorme dopo 48 h senza visite** (`cpu-basic`): il workflow `keep-alive.yml`
  lo risveglia ogni 6 ore.
* Il piano gratuito non prevede lo storage persistente `/data`, che è a pagamento.