# Changelog

Tutte le modifiche rilevanti a **MiaNonnaBot** sono documentate in questo file.

Il formato segue [Keep a Changelog](https://keepachangelog.com/it/1.1.0/)
e il progetto aderisce al [Semantic Versioning](https://semver.org/lang/it/).

Le versioni `0.x.y` sono di sviluppo: l'API e i comandi possono cambiare senza preavviso.

## [Unreleased]

### Da fare
- [ ] Notifiche opzionali solo al ribasso (impostazione per chat).
- [ ] Supporto a più siti eBay nello stesso comando (es. ebay.de, ebay.com).
- [ ] Comando per impostare un prezzo obiettivo con avviso dedicato.

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
