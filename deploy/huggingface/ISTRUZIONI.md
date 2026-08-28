# NonnaBot su Hugging Face Spaces — guida passo passo

⏱️ Tempo stimato: **15 minuti**, tutto dal browser. Niente carta di credito,
niente software da installare.

Cosa stai facendo: il bot (che finora girava sul tuo PC, o da nessuna parte)
prende casa in un container **sempre acceso** su Hugging Face. Il bot resta
lo stesso: [@nonna_ebay_bot](https://t.me/nonna_ebay_bot).

## Perché Hugging Face

* Lo Space (piano gratuito `cpu-basic`) tiene acceso un container Docker.
* Non serve carta di credito.
* Limite da gestire: **si addormenta dopo 48 h senza visite** → il workflow
  `keep-alive.yml` (punto 7) lo sveglia ogni 6 ore.
* Il disco è **effimero**: *"The data written on disk is lost whenever your
  Docker Space restarts"*. Per questo il database viene salvato su un
  *dataset* dello stesso account (punto 2) e ripristinato a ogni avvio.

## 1. Prerequisiti

1. Un account Hugging Face, gratis: <https://huggingface.co>.
2. Il token di Telegram, da @BotFather → `/token`. **Non condividerlo mai.**

## 2. Crea il dataset per il backup (2 minuti)

1. In alto a destra → **New dataset** (oppure <https://huggingface.co/new/dataset>).
2. Nome: ad esempio `nonnabot` → l'indirizzo finale sarà `tuonome/nonnabot`.
3. Lascialo **vuoto**: non devi caricare niente, i file li metterà il bot.
4. Annota l'indirizzo completo: sarà il valore di `HF_BACKUP_REPO`.

## 3. Crea lo Space (2 minuti)

1. **New Space** (<https://huggingface.co/spaces/new>).
2. Nome: ad esempio `nonnabot`.
3. SDK: **Docker** (obbligatorio, è questo che usa il nostro `Dockerfile`).
4. Hardware: `cpu-basic` (gratis).
5. **Create**.

## 4. Carica i 4 file nello Space (3 minuti)

Nella pagina dello Space, crea questi file (pennino *Edit* → nuovo file):

| File da questo repository | Nome nello Space |
| --- | --- |
| `main.py` | `main.py` |
| `requirements.txt` | `requirements.txt` |
| `Dockerfile` | `Dockerfile` |
| `deploy/huggingface/space-README.md` | **`README.md`** |

⚠️ Nel Space il file di configurazione **deve** chiamarsi `README.md` (contiene
`sdk: docker` e `app_port: 7860`).

Ogni modifica a un file fa ripartire lo Space: fai tutti e quattro prima di
continuare, così il build gira una volta sola.

## 5. Variabili e segreti (2 minuti)

Nello Space: **Settings → Variables and secrets** → *New variable/secret*:

| Nome | Tipo | Valore |
| --- | --- | --- |
| `TELEGRAM_BOT_TOKEN` | **Secret** | il token di @BotFather |
| `HF_TOKEN` | **Secret** | token Hugging Face con permesso *Write* (Settings → Access tokens → New token → scope **Write**) |
| `HF_BACKUP_REPO` | Variable | `tuonome/nonnabot` (il dataset del punto 2) |
| `EBAY_CLIENT_ID` | Secret | facoltativo: API ufficiali eBay |
| `EBAY_CLIENT_SECRET` | Secret | facoltativo: API ufficiali eBay |

Senza `HF_TOKEN` e `HF_BACKUP_REPO` il bot funziona lo stesso, ma la lista
dei prodotti **si azzera a ogni riavvio** del container.

## 6. Aspetta il build e prova (5 minuti)

1. Lo Space parte: la prima volta il build *Building* dura 2-5 minuti.
2. Quando lo stato diventa **Running**, su Telegram scrivi `aiuto` a
   @nonna_ebay_bot.
3. Incolla un link eBay: deve arrivare la conferma `✅ Aggiunto...`.
4. La pagina web dello Space non mostra nulla: è normale, esiste solo per la
   porta di salute (7860) che la piattaforma usa per capire che è vivo.

## 7. Tienilo sveglio, una tantum (3 minuti)

1. In **questo** repository copia il workflow:
   `cp deploy/github/keep-alive.yml .github/workflows/keep-alive.yml`
   (e poi commit + push).
2. GitHub → **Settings → Secrets and variables → Actions → Variables** →
   `SPACE_URL` = `https://TUO-SPAZIO.huggingface.co`.
3. Da allora ogni 6 ore il workflow fa una GET alla porta di salute e lo
   Space non si addormenta mai.

## Se qualcosa non funziona

* **"Building" resta rosso** → apri *Logs*: di solito è un file mancante
  (i quattro del punto 4) o un nome sbagliato.
* **Il bot non risponde** → ricontrolla `TELEGRAM_BOT_TOKEN` in
  *Variables and secrets*: deve essere un **Secret**, senza spazi in più.
* **La lista svanisce a ogni riavvio** → manca `HF_BACKUP_REPO`, oppure
  `HF_TOKEN` non ha lo scope *Write* sul dataset.
* **Lo Space si spegne dopo qualche giorno** → manca il keep-alive (punto 7).
* **Voglio smettere** → nel menu a freccia dello Space: *Delete Space*. Il
  dataset col backup resta finché lo elimini tu.
