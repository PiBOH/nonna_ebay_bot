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
