#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MiaNonnaBot — bot Telegram per il monitoraggio dei prezzi su eBay.

L'utente incolla il link di un'inserzione eBay: il bot ne estrae titolo e prezzo,
lo mette sotto controllo e avvisa in chat ogni volta che il prezzo cambia
(in ribasso 📉 o in aumento 📈).

Caratteristiche principali
--------------------------
* Tutti i comandi funzionano sia con lo ``/`` sia come testo semplice, e sono
  completamente insensibili alle maiuscole/minuscole (``lista``, ``LISTA``,
  ``/Lista`` sono equivalenti).
* Database SQLite locale (zero configurazione) con indice progressivo *per chat*.
* Worker in background (job queue di ``python-telegram-bot``) che ricontrolla i
  prezzi a intervalli regolari.
* Estrazione dati eBay a più livelli di fallback (JSON-LD → microdata → CSS →
  regex) così il bot continua a funzionare anche se eBay cambia il markup.
* Supporto opzionale alle API ufficiali *eBay Browse* (basta impostare
  ``EBAY_CLIENT_ID`` e ``EBAY_CLIENT_SECRET``): più stabili dello scraping.

Configurazione (variabili d'ambiente)
-------------------------------------
Obbligatoria:
    TELEGRAM_BOT_TOKEN      Token fornito da @BotFather (accettato anche BOT_TOKEN).

Opzionali:
    DATABASE_PATH           Percorso del file SQLite (default: ``mianonnabot.db``).
    CHECK_INTERVAL_MINUTES  Ogni quanti minuti ricontrollare i prezzi (default: 60).
    EBAY_SITE               Sito eBay usato per i link (default: ``www.ebay.it``).
    EBAY_CLIENT_ID          Client ID app eBay (abilita le API Browse ufficiali).
    EBAY_CLIENT_SECRET      Client Secret app eBay.
    EBAY_MARKETPLACE_ID     Marketplace per le API (default: ``EBAY_IT``).
    EBAY_LANG               Lingua richiesta alle API (default: ``it-IT``).
    EPN_CAMPAIGN_ID         ID campagna eBay Partner Network (link affiliati).
    EPN_TOOL_ID             Tool ID ePN (default: 10001).
    MAX_TRACKED_PER_CHAT    Limite oggetti per chat (default: 50).
    HTTP_TIMEOUT            Timeout delle richieste HTTP in secondi (default: 25).
    REQUEST_DELAY_SECONDS   Pausa fra due richieste eBay nel worker (default: 4).
    LOG_LEVEL               Livello di logging (default: INFO).

Avvio
-----
    python main.py                 # processo residente: comandi + controllo prezzi
    python main.py --check-once    # un solo giro di controllo, poi esce (cron / Actions)
    python main.py --version       # stampa la versione

Copyright (C) 2026 — rilasciato con licenza GNU AGPL v3 (vedi LICENSE).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import random
import re
import sqlite3
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from types import SimpleNamespace
from typing import Any, Iterable, Optional, Sequence

import requests
from bs4 import BeautifulSoup

from telegram import Update
from telegram.constants import ChatAction
from telegram.error import Forbidden, InvalidToken, NetworkError, RetryAfter, TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
)

# python-dotenv è utile in sviluppo locale (file .env); su Render/PythonAnywhere
# le variabili si impostano dal pannello, quindi l'import è opzionale.
try:  # pragma: no cover - dipende dall'ambiente
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass


# ---------------------------------------------------------------------------
# Versione e metadati
# ---------------------------------------------------------------------------

#: Versione del bot, secondo lo standard Semantic Versioning (https://semver.org).
__version__ = "0.0.1"

BOT_NAME = "MiaNonnaBot"
BOT_USERNAME = os.environ.get("BOT_USERNAME", "nonna_ebay_bot")

#: Nome del file di changelog distribuito insieme al bot.
CHANGELOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "CHANGELOG.md")


# ---------------------------------------------------------------------------
# Configurazione
# ---------------------------------------------------------------------------

def _env_int(name: str, default: int) -> int:
    """Legge una variabile d'ambiente intera, tornando al default se non valida."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logging.warning("Variabile %s=%r non è un intero: uso il default %d", name, raw, default)
        return default


def _env_float(name: str, default: float) -> float:
    """Legge una variabile d'ambiente decimale, tornando al default se non valida."""
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw.replace(",", "."))
    except ValueError:
        logging.warning("Variabile %s=%r non è un numero: uso il default %s", name, raw, default)
        return default


TELEGRAM_BOT_TOKEN: str = (
    os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("BOT_TOKEN") or ""
).strip()

DATABASE_PATH: str = os.environ.get("DATABASE_PATH", "mianonnabot.db").strip() or "mianonnabot.db"
CHECK_INTERVAL_MINUTES: int = max(5, _env_int("CHECK_INTERVAL_MINUTES", 60))
EBAY_SITE: str = os.environ.get("EBAY_SITE", "www.ebay.it").strip() or "www.ebay.it"
EBAY_CLIENT_ID: str = os.environ.get("EBAY_CLIENT_ID", "").strip()
EBAY_CLIENT_SECRET: str = os.environ.get("EBAY_CLIENT_SECRET", "").strip()
EBAY_MARKETPLACE_ID: str = os.environ.get("EBAY_MARKETPLACE_ID", "EBAY_IT").strip() or "EBAY_IT"
EBAY_LANG: str = os.environ.get("EBAY_LANG", "it-IT").strip() or "it-IT"
EPN_CAMPAIGN_ID: str = os.environ.get("EPN_CAMPAIGN_ID", "").strip()
EPN_TOOL_ID: str = os.environ.get("EPN_TOOL_ID", "10001").strip() or "10001"
MAX_TRACKED_PER_CHAT: int = max(1, _env_int("MAX_TRACKED_PER_CHAT", 50))
HTTP_TIMEOUT: float = _env_float("HTTP_TIMEOUT", 25.0)
REQUEST_DELAY_SECONDS: float = _env_float("REQUEST_DELAY_SECONDS", 4.0)
MAX_MESSAGE_LENGTH: int = 3900  # Telegram accetta 4096 caratteri: ci teniamo un margine.

# Le API ufficiali sono usate solo se sono presenti entrambe le credenziali.
USE_BROWSE_API: bool = bool(EBAY_CLIENT_ID and EBAY_CLIENT_SECRET)

LOG_LEVEL: str = os.environ.get("LOG_LEVEL", "INFO").strip().upper() or "INFO"
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=getattr(logging, LOG_LEVEL, logging.INFO),
)
logger = logging.getLogger("mianonnabot")

# User-Agent realistico: riduce (non elimina) la probabilità di essere bloccati.
HTTP_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,*/*;q=0.8",
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.7,en;q=0.6",
    "Cache-Control": "no-cache",
}


# ---------------------------------------------------------------------------
# Testi fissi mostrati all'utente
# ---------------------------------------------------------------------------

def build_help() -> str:
    """Costruisce il messaggio di benvenuto/aiuto.

    Il testo viene inviato *senza* parse mode: contiene asterischi e cuori che in
    Markdown sarebbero interpretati come formattazione e romperebbero l'output.
    """
    return (
        f"{BOT_NAME}:\n"
        f"Versione: {__version__}\n"
        "\n"
        "👋 Comandi utilizzabili\n"
        "\n"
        "* aiuto,help,h : questo messaggio\n"
        "* lista,list,l : elenco prodotti sotto controllo\n"
        "* cancella num : elimina prodotto da osservare\n"
        "* azzera : elimina tutti i prodotti sottoscritti\n"
        "* numero : richiama link prodotto n "
        '(es. inviando solo il numero "1" o "/1" o "numero 1")\n'
        "* changelog : mostra il registro delle modifiche\n"
        "\n"
        "Incolla un link eBay, per tener sotto controllo il prezzo\n"
        "\n"
        "❤️ Il bot si può aggiungere a gruppi e canali ❤️\n"
        "\n"
        "Il Bot è ancora in fase di sviluppo e può funzionare non correttamente."
    )


UNKNOWN_TEXT = (
    "Non ho capito 🤔\n"
    "Incolla un link eBay per mettere l'oggetto sotto controllo, "
    'oppure scrivi "aiuto" per vedere i comandi.'
)

DELETE_USAGE = 'Uso: cancella <numero>\nEsempio: "cancella 3" (oppure "/cancella 3").'
LINK_USAGE = 'Uso: numero <numero>\nEsempio: "numero 3", oppure invia solo "3" o "/3".'


# ---------------------------------------------------------------------------
# Piccoli helper di formattazione
# ---------------------------------------------------------------------------

def format_price(value: Optional[float], currency: str = "EUR") -> str:
    """Formatta un prezzo in stile italiano: ``1234.5`` → ``€1.234,50``."""
    if value is None:
        return "n/d"
    text = f"{value:,.2f}"                       # 1234.5 -> "1,234.50"
    text = text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    symbol = {"EUR": "€", "GBP": "£", "USD": "$", "CHF": "CHF "}.get(currency, f"{currency} ")
    if symbol.endswith(" "):
        return f"{text} {symbol.strip()}"
    return f"{symbol}{text}"


def shorten(text: str, limit: int = 90) -> str:
    """Tronca un titolo troppo lungo aggiungendo i puntini di sospensione."""
    text = " ".join((text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


# ---------------------------------------------------------------------------
# Parsing dei prezzi (i formati eBay variano: "EUR 1.234,56", "500.0", "$1,234.56")
# ---------------------------------------------------------------------------

_PRICE_NOISE_RE = re.compile(
    r"[^0-9.,]",
)


def parse_price(raw: Any) -> Optional[float]:
    """Converte una stringa di prezzo in ``float``.

    Regole:
      * se sono presenti sia ``.`` sia ``,`` il più a destra è il separatore decimale;
      * se c'è solo ``,`` è decimale (formato italiano: ``1.234,56``);
      * se c'è solo ``.`` è decimale, *tranne* quando la parte decimale ha
        esattamente 3 cifre, che in italiano indica le migliaia (``1.234``).

    Ritorna ``None`` se non riesce a ricavare un numero positivo.
    """
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw) if raw > 0 else None

    text = str(raw).replace("\xa0", " ").replace(" ", " ").strip()
    text = _PRICE_NOISE_RE.sub("", text).strip(".,")
    if not text or not any(ch.isdigit() for ch in text):
        return None

    has_dot, has_comma = "." in text, "," in text
    if has_dot and has_comma:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif has_comma:
        text = text.replace(".", "").replace(",", ".")
    elif has_dot:
        integer_part, _, decimals = text.rpartition(".")
        if len(decimals) == 3 and integer_part:
            text = text.replace(".", "")  # 1.234 -> 1234 (migliaia in italiano)

    try:
        value = float(text)
    except ValueError:
        return None
    return value if value > 0 else None


# ---------------------------------------------------------------------------
# Estrazione dell'ID oggetto eBay dal testo inviato dall'utente
# ---------------------------------------------------------------------------

#: URL generico all'interno di un messaggio Telegram.
_URL_RE = re.compile(r"https?://[^\s<>\"')]+", re.IGNORECASE)
#: Percorso canonico: https://www.ebay.it/itm/405399021732 (anche con slug testuale).
_ITM_RE = re.compile(r"/itm/(?:[^/?#]*?[-/])?(\d{10,13})", re.IGNORECASE)
#: Vecchie URL di tipo ...ViewItem&item=405399021732 oppure ?item=...
_ITEM_PARAM_RE = re.compile(r"[?&]item=(\d{10,13})", re.IGNORECASE)
#: Ultimo blocco di 10-13 cifre di una URL eBay (fallback).
_DIGITS_RE = re.compile(r"(\d{10,13})")
#: ID oggetto scritto da solo nel messaggio.
_BARE_ID_RE = re.compile(r"^\d{10,13}$")


def extract_item_id(text: str) -> Optional[str]:
    """Estrae l'ID numerico di un'inserzione eBay da un messaggio di testo.

    Supporta ``https://www.ebay.it/itm/405399021732?hash=...``, i link con slug
    testuale, le vecchie URL ``ViewItem&item=``, i domini locali eBay e l'ID
    nudo e crudo. Ritorna ``None`` se non trova nulla.
    """
    if not text:
        return None

    # 1) Cerchiamo prima dentro le URL complete (il caso più frequente).
    for url in _URL_RE.findall(text):
        host = url.split("/")[2].lower() if url.count("/") >= 2 else ""
        if "ebay" not in host and "itm" not in host:
            continue
        for pattern in (_ITM_RE, _ITEM_PARAM_RE, _DIGITS_RE):
            match = pattern.search(url)
            if match:
                return match.group(1)

    # 2) Nessuna URL riconoscibile: proviamo con un ID inviato da solo.
    candidate = text.strip()
    if _BARE_ID_RE.match(candidate):
        return candidate

    # 3) Ultimo tentativo: frammenti tipo "itm 405399021732" senza protocollo.
    match = _ITM_RE.search(text) or _ITEM_PARAM_RE.search(text)
    return match.group(1) if match else None


def build_item_url(item_id: str) -> str:
    """Costruisce la URL canonica dell'oggetto, eventualmente in affiliazione ePN."""
    url = f"https://{EBAY_SITE}/itm/{item_id}"
    if EPN_CAMPAIGN_ID:
        url += f"?campid={EPN_CAMPAIGN_ID}&toolid={EPN_TOOL_ID}&mkevt=1"
    return url


# ---------------------------------------------------------------------------
# Parsing della pagina eBay
# ---------------------------------------------------------------------------

#: Indicatori di inserzione conclusa (varie lingue).
_ENDED_MARKERS = (
    "l'inserzione è terminata",
    "l'inserzione e' terminata",
    "l'oggetto non è più disponibile",
    "la vendita è terminata",
    "questo oggetto non è più disponibile",
    "this listing has ended",
    "this item is no longer available",
    "the listing has ended",
)


@dataclass(frozen=True)
class EbayInfo:
    """Dati essenziali di un'inserzione eBay."""

    item_id: str
    title: str
    price: Optional[float]
    currency: str
    url: str
    ended: bool = False
    source: str = ""


def _first(node: Any, selectors: Sequence[str]) -> Optional[str]:
    """Restituisce il testo del primo selettore CSS che produce un risultato."""
    for selector in selectors:
        try:
            found = node.select_one(selector)
        except Exception:  # selettori non supportati da Soup in versioni molto vecchie
            continue
        if found and found.get_text(strip=True):
            return found.get_text(strip=True)
    return None


def _from_json_ld(soup: BeautifulSoup) -> tuple[Optional[str], Optional[float], str]:
    """Legge titolo, prezzo e valuta dai blocchi ``application/ld+json`` (schema.org)."""
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        payload = script.string or script.get_text() or ""
        if not payload.strip():
            continue
        try:
            data = json.loads(payload)
        except (ValueError, TypeError):
            continue

        candidates: list[dict[str, Any]] = []
        stack: list[Any] = [data]
        while stack:  # visita ricorsiva senza ricorsione Python
            current = stack.pop()
            if isinstance(current, dict):
                candidates.append(current)
                stack.extend(current.values())
            elif isinstance(current, list):
                stack.extend(current)

        for node in candidates:
            node_type = node.get("@type")
            types = {node_type} if isinstance(node_type, str) else set(node_type or [])
            offers = node.get("offers")
            if "Product" not in types and not offers:
                continue

            title = node.get("name") if isinstance(node.get("name"), str) else None
            price, currency = None, ""
            offer_list = offers if isinstance(offers, list) else [offers] if offers else []
            for offer in offer_list:
                if not isinstance(offer, dict):
                    continue
                price = parse_price(offer.get("price") or offer.get("lowPrice"))
                currency = str(offer.get("priceCurrency") or "").upper()
                if price:
                    break
            if title or price:
                return title, price, currency
    return None, None, ""


def _from_microdata(soup: BeautifulSoup) -> tuple[Optional[str], Optional[float], str]:
    """Fallback su microdata ``itemprop`` (presente su alcune varianti di pagina)."""
    title = _first(soup, ['[itemprop="name"]'])
    price_node = soup.select_one('[itemprop="price"]')
    price = None
    currency = ""
    if price_node is not None:
        price = parse_price(price_node.get("content") or price_node.get_text())
        currency = str(price_node.get("content_currency") or "").upper()
    if not currency:
        currency_node = soup.select_one('[itemprop="priceCurrency"]')
        if currency_node is not None:
            currency = str(
                currency_node.get("content") or currency_node.get_text() or ""
            ).upper()
    return title, price, currency


_TITLE_SELECTORS = (
    "h1.x-item-title__mainTitle",
    "div.x-item-title__mainTitle span",
    "h1.x-item-title__mainTitle span",
    "#itemTitle",
    "h1.it-ttl",
    "h1",
)

_PRICE_SELECTORS = (
    "div.x-price-primary span.ux-labels-values__values",
    "div.x-price-primary span",
    'div[data-testid="x-price-primary"]',
    "div.x-price-primary",
    "div.x-price__main span",
    "div.x-price__main",
    "#prcIsum",
    "#mm-saleDscPrc",
    "span.notranslate",
)

#: Ultimo disperato fallback: cerca il prezzo nel JSON embedded della pagina.
_RAW_PRICE_PATTERNS = (
    re.compile(r'"displayPrice"\s*:\s*"([^"]{1,40})"'),
    re.compile(r'"price"\s*:\s*"([\d][\d.,]{1,15})"\s*,\s*"priceCurrency"\s*:\s*"([A-Z]{3})"'),
    re.compile(r'"priceCurrency"\s*:\s*"([A-Z]{3})"\s*,\s*"price"\s*:\s*"([\d][\d.,]{1,15})"'),
    re.compile(r'EUR\s*([0-9][0-9.\u00a0 ]{1,10},\d{2})'),
)


def parse_ebay_page(page_html: str, item_id: str, url: str = "") -> EbayInfo:
    """Estrae titolo, prezzo e valuta dall'HTML di una pagina oggetto eBay.

    La funzione procede per tentativi successivi (JSON-LD → microdata → selettori
    CSS → regex sul grezzo) perché il markup eBay cambia spesso e differisce fra
    A/B test. Alza ``ValueError`` se non riesce a ricavare nemmeno il prezzo.
    """
    soup = BeautifulSoup(page_html or "", "html.parser")
    lowered = (page_html or "").lower()
    ended = any(marker in lowered for marker in _ENDED_MARKERS)

    title: Optional[str] = None
    price: Optional[float] = None
    currency = ""
    source = ""

    # 1) JSON-LD: fonte più stabile e completa.
    ld_title, ld_price, ld_currency = _from_json_ld(soup)
    if ld_price:
        price, source = ld_price, "json-ld"
    title = ld_title
    if ld_currency:
        currency = ld_currency

    # 2) Microdata.
    if price is None or not title:
        md_title, md_price, md_currency = _from_microdata(soup)
        if price is None and md_price:
            price, source = md_price, "microdata"
        title = title or md_title
        currency = currency or md_currency

    # 3) Selettori CSS (markup "UX" attuale e markup legacy).
    if not title:
        title = _first(soup, _TITLE_SELECTORS)
    if price is None:
        css_price = _first(soup, _PRICE_SELECTORS)
        parsed = parse_price(css_price)
        if parsed:
            price, source = parsed, "css"
            if not currency and css_price:
                head = css_price.strip().split()[0].upper()
                currency = head if head in {"EUR", "GBP", "USD", "CHF"} else "EUR"

    # 4) Regex sul testo grezzo.
    if price is None:
        for pattern in _RAW_PRICE_PATTERNS:
            match = pattern.search(page_html or "")
            if not match:
                continue
            groups = match.groups()
            candidate = parse_price(groups[0])
            if candidate:
                price, source = candidate, "regex"
                if len(groups) > 1:
                    currency = (groups[1] or "").upper()
                break

    title = " ".join((title or "").split()) or f"Oggetto eBay {item_id}"
    currency = currency or "EUR"
    if price is None:
        raise ValueError(f"Prezzo non trovato nella pagina dell'oggetto {item_id}")

    return EbayInfo(
        item_id=item_id,
        title=title,
        price=price,
        currency=currency,
        url=url or build_item_url(item_id),
        ended=ended,
        source=source,
    )


# ---------------------------------------------------------------------------
# Accesso a eBay: API Browse ufficiali (opzionali) oppure scraping
# ---------------------------------------------------------------------------

_TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
_BROWSE_ITEM_URL = "https://api.ebay.com/buy/browse/v1/item/{item_id}"

_token_cache: dict[str, Any] = {"token": None, "expires_at": 0.0}


def _browse_token() -> Optional[str]:
    """Ottiene (e tiene in cache) il token OAuth2 client-credentials per le API eBay."""
    now = time.time()
    if _token_cache["token"] and _token_cache["expires_at"] > now + 60:
        return _token_cache["token"]
    try:
        response = requests.post(
            _TOKEN_URL,
            data={"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"},
            auth=(EBAY_CLIENT_ID, EBAY_CLIENT_SECRET),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=HTTP_TIMEOUT,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:  # noqa: BLE001 - vogliamo solo un log e il fallback
        logger.warning("OAuth eBay fallito (%s): uso lo scraping", exc)
        return None

    token = payload.get("access_token")
    if not token:
        return None
    _token_cache["token"] = token
    _token_cache["expires_at"] = now + int(payload.get("expires_in", 7200))
    return token


def _info_from_browse_api(item_id: str) -> Optional[EbayInfo]:
    """Recupera titolo e prezzo via API ufficiale eBay Browse (se configurata)."""
    token = _browse_token()
    if not token:
        return None
    try:
        response = requests.get(
            _BROWSE_ITEM_URL.format(item_id=item_id),
            params={"fieldgroups": "COMPACT"},
            headers={
                "Authorization": f"Bearer {token}",
                "X-EBAY-C-MARKETPLACE-ID": EBAY_MARKETPLACE_ID,
                "Content-Language": EBAY_LANG,
            },
            timeout=HTTP_TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.warning("API Browse non raggiungibile per %s: %s", item_id, exc)
        return None

    if response.status_code == 404:
        return None
    if response.status_code != 200:
        logger.warning("API Browse ha risposto %s per %s", response.status_code, item_id)
        return None

    try:
        data = response.json()
    except ValueError:
        return None

    price_block = data.get("price") or {}
    price = parse_price(price_block.get("value"))
    if not price:
        return None
    return EbayInfo(
        item_id=item_id,
        title=" ".join(str(data.get("title") or f"Oggetto eBay {item_id}").split()),
        price=price,
        currency=str(price_block.get("currency") or "EUR").upper(),
        url=build_item_url(item_id),
        ended=False,
        source="browse-api",
    )


def _http_get(url: str, attempts: int = 2) -> Optional[str]:
    """GET con retry semplice; ritorna l'HTML o ``None``."""
    for attempt in range(1, attempts + 1):
        try:
            response = requests.get(url, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT)
            if response.status_code == 200:
                return response.text
            logger.info("GET %s -> HTTP %s (tentativo %d)", url, response.status_code, attempt)
            if response.status_code in (404, 410):
                return None
        except requests.RequestException as exc:
            logger.info("GET %s fallita (%s) - tentativo %d", url, exc, attempt)
        if attempt < attempts:
            time.sleep(1.5 * attempt + random.uniform(0, 1.0))
    return None


def get_ebay_info(item_id: str) -> Optional[EbayInfo]:
    """Recupera titolo e prezzo corrente di un oggetto eBay.

    Ordine di tentativo: API Browse (se configurata) → scraping della pagina.
    Ritorna ``None`` se l'oggetto non esiste o se eBay non è raggiungibile.
    """
    item_id = str(item_id).strip()
    if not re.fullmatch(r"\d{10,13}", item_id):
        logger.warning("ID oggetto non valido: %r", item_id)
        return None

    if USE_BROWSE_API:
        info = _info_from_browse_api(item_id)
        if info:
            return info

    url = f"https://{EBAY_SITE}/itm/{item_id}"
    page_html = _http_get(url)
    if page_html is None:
        # Ultimo tentativo sul sito globale, utile per gli oggetti non localizzati.
        fallback_site = "www.ebay.com" if EBAY_SITE != "www.ebay.com" else "www.ebay.it"
        url = f"https://{fallback_site}/itm/{item_id}"
        page_html = _http_get(url)
    if page_html is None:
        logger.warning("Pagina eBay non raggiungibile per %s", item_id)
        return None

    try:
        return parse_ebay_page(page_html, item_id, url)
    except ValueError as exc:
        logger.warning("Parsing fallito per %s: %s", item_id, exc)
        return None


# ---------------------------------------------------------------------------
# Database SQLite
# ---------------------------------------------------------------------------

#: Le colonne richieste dallo schema del progetto più alcune utili al worker.
_SCHEMA = """
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
"""


@dataclass
class TrackedItem:
    """Un oggetto sotto controllo, con il proprio indice progressivo nella chat."""

    row_id: int
    index: int
    chat_id: int
    item_id: str
    last_price: Optional[float]
    title: str
    url: str
    currency: str = "EUR"
    ended: bool = False
    last_checked: Optional[str] = None


def connect_db() -> sqlite3.Connection:
    """Apre una connessione SQLite con impostazioni adatte a un bot concorrente."""
    conn = sqlite3.connect(DATABASE_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 15000")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


def init_db() -> None:
    """Crea lo schema se non esiste."""
    with connect_db() as conn:
        conn.executescript(_SCHEMA)
    logger.info("Database pronto: %s", DATABASE_PATH)


def _row_to_item(row: sqlite3.Row, index: int) -> TrackedItem:
    return TrackedItem(
        row_id=row["id"],
        index=index,
        chat_id=row["chat_id"],
        item_id=row["item_id_ebay"],
        last_price=row["last_price"],
        title=row["title"] or f"Oggetto eBay {row['item_id_ebay']}",
        url=row["url"],
        currency=row["currency"] or "EUR",
        ended=bool(row["ended"]),
        last_checked=row["last_checked"],
    )


def list_items(chat_id: int) -> list[TrackedItem]:
    """Elenca gli oggetti di una chat, numerati progressivamente da 1.

    L'indice è ricalcolato a ogni lettura: dopo una cancellazione i numeri
    restano compatti (1, 2, 3...) come si aspetta l'utente.
    """
    with connect_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tracciamenti WHERE chat_id = ? ORDER BY id ASC", (chat_id,)
        ).fetchall()
    return [_row_to_item(row, position) for position, row in enumerate(rows, start=1)]


def find_by_index(chat_id: int, index: int) -> Optional[TrackedItem]:
    """Ritorna l'oggetto con quel numero progressivo nella chat, se esiste."""
    if index <= 0:
        return None
    for item in list_items(chat_id):
        if item.index == index:
            return item
    return None


def find_by_item_id(chat_id: int, item_id: str) -> Optional[TrackedItem]:
    """Verifica se l'oggetto è già tracciato da questa chat (evita duplicati)."""
    for item in list_items(chat_id):
        if item.item_id == str(item_id):
            return item
    return None


def count_items(chat_id: int) -> int:
    """Numero di oggetti tracciati nella chat."""
    with connect_db() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS totale FROM tracciamenti WHERE chat_id = ?", (chat_id,)
        ).fetchone()
    return int(row["totale"]) if row else 0


def add_item(
    chat_id: int,
    item_id: str,
    price: Optional[float],
    title: str,
    url: str,
    currency: str = "EUR",
) -> int:
    """Inserisce un oggetto da monitorare e ne ritorna il ``rowid``."""
    with connect_db() as conn:
        cursor = conn.execute(
            """
            INSERT INTO tracciamenti
                (chat_id, item_id_ebay, last_price, title, url, currency, created_at, last_checked)
            VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            (chat_id, str(item_id), price, title, url, currency),
        )
        return int(cursor.lastrowid)


def delete_item(chat_id: int, index: int) -> Optional[TrackedItem]:
    """Elimina l'oggetto con quel numero progressivo; ritorna l'oggetto rimosso."""
    item = find_by_index(chat_id, index)
    if item is None:
        return None
    with connect_db() as conn:
        conn.execute("DELETE FROM tracciamenti WHERE id = ?", (item.row_id,))
    return item


def clear_items(chat_id: int) -> int:
    """Elimina tutti gli oggetti della chat; ritorna quanti ne ha tolti."""
    with connect_db() as conn:
        cursor = conn.execute("DELETE FROM tracciamenti WHERE chat_id = ?", (chat_id,))
        return int(cursor.rowcount)


def all_tracked_items() -> list[TrackedItem]:
    """Tutti gli oggetti tracciati da tutte le chat (per il worker)."""
    with connect_db() as conn:
        rows = conn.execute(
            "SELECT * FROM tracciamenti WHERE ended = 0 ORDER BY chat_id, id"
        ).fetchall()
    # L'indice viene ricalcolato per chat per coerenza con /lista.
    counters: dict[int, int] = {}
    items: list[TrackedItem] = []
    for row in rows:
        chat_id = int(row["chat_id"])
        counters[chat_id] = counters.get(chat_id, 0) + 1
        items.append(_row_to_item(row, counters[chat_id]))
    return items


def update_price(row_id: int, price: float, checked: bool = True) -> None:
    """Aggiorna il prezzo noto e l'orario dell'ultimo controllo."""
    with connect_db() as conn:
        conn.execute(
            """
            UPDATE tracciamenti
               SET last_price = ?,
                   last_checked = CASE WHEN ? THEN datetime('now') ELSE last_checked END
             WHERE id = ?
            """,
            (price, int(checked), row_id),
        )


def update_title(row_id: int, title: str) -> None:
    """Allinea il titolo salvato a quello attuale (i venditori lo modificano)."""
    with connect_db() as conn:
        conn.execute("UPDATE tracciamenti SET title = ? WHERE id = ?", (title, row_id))


def touch_checked(row_id: int) -> None:
    """Segna l'orario dell'ultimo tentativo di controllo (anche senza variazioni)."""
    with connect_db() as conn:
        conn.execute(
            "UPDATE tracciamenti SET last_checked = datetime('now') WHERE id = ?", (row_id,)
        )


def mark_ended(row_id: int) -> None:
    """Marca un'inserzione come conclusa: il worker non la ricontrollerà più."""
    with connect_db() as conn:
        conn.execute(
            "UPDATE tracciamenti SET ended = 1, last_checked = datetime('now') WHERE id = ?",
            (row_id,),
        )


# ---------------------------------------------------------------------------
# Logica dei comandi: parsing del messaggio
# ---------------------------------------------------------------------------

class Action(str, Enum):
    """Azioni in cui può essere tradotto un messaggio dell'utente."""

    IGNORE = "ignore"
    HELP = "help"
    LIST = "list"
    CLEAR = "clear"
    CHANGELOG = "changelog"
    DELETE = "delete"
    DELETE_USAGE = "delete_usage"
    LINK = "link"
    LINK_USAGE = "link_usage"
    ADD = "add"
    UNKNOWN = "unknown"


#: Sinonimi accettati per ciascun comando (tutti in minuscolo).
HELP_WORDS = {"start", "aiuto", "help", "h", "comandi", "menu", "info", "?"}
LIST_WORDS = {"lista", "list", "l", "elenco", "prodotti", "oggetti"}
CLEAR_WORDS = {"azzera", "azzerratutto", "reset", "svuota", "eliminatutto", "cancellatutto"}
CHANGELOG_WORDS = {"changelog", "novita", "novità", "versione", "changelogs"}
DELETE_WORDS = {"cancella", "elimina", "rimuovi", "remove", "delete", "del", "x", "d"}
NUMBER_WORDS = {"numero", "num", "n", "link"}


@dataclass
class Parsed:
    """Risultato dell'analisi di un messaggio."""

    action: Action
    value: Any = None


def parse_message(text: str) -> Parsed:
    """Traduce un messaggio (con o senza ``/``, in qualsiasi case) in un'azione.

    È la funzione "cervello" del bot: è pura, quindi è testabile senza Telegram.
    """
    if not text or not text.strip():
        return Parsed(Action.IGNORE)

    raw = text.strip()

    # Un link eBay vince sempre su tutto il resto.
    item_id = extract_item_id(raw)
    if item_id and not raw.startswith("/"):
        return Parsed(Action.ADD, item_id)

    body = raw[1:].strip() if raw.startswith("/") else raw

    # Rimuove l'eventuale menzione al bot: /lista@MiaNonnaBot -> "lista".
    first, _, rest = body.partition(" ")
    if "@" in first:
        first = first.split("@", 1)[0]
    rest = rest.strip()

    # "/405399021732": ID lungo → nuovo tracciamento; numero corto → indice.
    if first.isdigit() and not rest:
        if len(first) >= 10:
            return Parsed(Action.ADD, first)
        return Parsed(Action.LINK, int(first))

    token = first.lower()

    if token in HELP_WORDS:
        return Parsed(Action.HELP)
    if token in CHANGELOG_WORDS:
        return Parsed(Action.CHANGELOG, int(rest) if rest.isdigit() else None)
    if token in LIST_WORDS:
        return Parsed(Action.LIST)
    if token in CLEAR_WORDS:
        return Parsed(Action.CLEAR)
    if token in DELETE_WORDS:
        if rest.isdigit():
            return Parsed(Action.DELETE, int(rest))
        if not rest:
            return Parsed(Action.DELETE_USAGE)
        # "cancella 3 oggetti": prendiamo comunque il primo numero trovato.
        number = re.search(r"\d+", rest)
        return Parsed(Action.DELETE, int(number.group())) if number else Parsed(Action.DELETE_USAGE)
    if token in NUMBER_WORDS:
        if rest.isdigit():
            return Parsed(Action.LINK, int(rest))
        return Parsed(Action.LINK_USAGE)

    # Testo composto non riconosciuto, ma contiene comunque un link eBay.
    if item_id:
        return Parsed(Action.ADD, item_id)

    return Parsed(Action.UNKNOWN)


# ---------------------------------------------------------------------------
# Formattazione delle risposte
# ---------------------------------------------------------------------------

def format_list(items: Sequence[TrackedItem]) -> str:
    """Costruisce l'elenco numerato degli oggetti sotto controllo."""
    if not items:
        return (
            "Nessun oggetto sotto controllo 👵\n"
            "Incolla un link eBay e inizierò a tenerlo d'occhio per te."
        )
    lines = [f"👀 {len(items)} oggetti sotto controllo:", ""]
    for item in items:
        flag = " ⛔ conclusa" if item.ended else ""
        lines.append(f"{item.index}. {shorten(item.title, 60)} - {format_price(item.last_price, item.currency)}{flag}")
    lines.append("")
    lines.append('Invia "cancella <numero>" per togliere un oggetto.')
    return "\n".join(lines)


def describe_price_change(
    old_price: Optional[float], new_price: Optional[float], item: TrackedItem
) -> Optional[str]:
    """Costruisce il testo di notifica per una variazione di prezzo.

    Ritorna ``None`` quando il prezzo non è cambiato (o non è confrontabile),
    così il worker resta in silenzio.
    """
    if new_price is None or old_price is None:
        return None
    delta = new_price - old_price
    if abs(delta) < 0.005:
        return None

    currency = item.currency or "EUR"
    if delta < 0:
        head = f"📉 Prezzo sceso da {format_price(old_price, currency)} a {format_price(new_price, currency)}!"
    else:
        head = f"📈 Prezzo aumentato da {format_price(old_price, currency)} a {format_price(new_price, currency)}!"
    return f"{head}\n\n{shorten(item.title, 80)}\n{item.url}"


def format_changelog(markdown_text: str, max_versions: int = 3) -> str:
    """Estrae dal CHANGELOG.md le ultime N versioni, pronte per Telegram."""
    if not markdown_text.strip():
        return "Changelog non disponibile."

    blocks: list[list[str]] = []
    current: Optional[list[str]] = None
    for line in markdown_text.splitlines():
        if line.startswith("## "):
            current = [line.lstrip("#").strip()]
            blocks.append(current)
        elif current is not None:
            if line.strip() or current[-1].strip():
                current.append(line.rstrip())

    selected = blocks[:max_versions] if max_versions > 0 else blocks
    if not selected:
        return "Changelog non disponibile."

    header = f"📒 Changelog {BOT_NAME} (ultime {len(selected)} versioni)\n"
    body = "\n\n".join("\n".join(block).strip() for block in selected)
    return header + "\n\n" + body


def split_message(text: str, limit: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """Spezza un testo lungo in blocchi inviabili, senza tagliare le righe."""
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current = ""
    for line in text.splitlines(keepends=True):
        if len(current) + len(line) > limit:
            if current:
                chunks.append(current.rstrip("\n"))
                current = ""
            if len(line) > limit:  # riga singola enorme: taglio brutale
                for start in range(0, len(line), limit):
                    chunks.append(line[start : start + limit])
                continue
        current += line
    if current.strip():
        chunks.append(current.rstrip("\n"))
    return chunks or [text[:limit]]


def read_changelog() -> str:
    """Legge il file CHANGELOG.md distribuito col bot."""
    try:
        with open(CHANGELOG_FILE, "r", encoding="utf-8") as handle:
            return handle.read()
    except OSError as exc:
        logger.warning("Impossibile leggere %s: %s", CHANGELOG_FILE, exc)
        return ""


# ---------------------------------------------------------------------------
# Invio messaggi (con gestione del flood control di Telegram)
# ---------------------------------------------------------------------------

async def send_text(context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str) -> None:
    """Invia un testo, spezzandolo se troppo lungo e rispettando i limiti di Telegram."""
    for chunk in split_message(text):
        try:
            await context.bot.send_message(chat_id=chat_id, text=chunk)
        except RetryAfter as exc:
            wait = int(exc.retry_after) + 1
            logger.warning("Flood control: attendo %ss", wait)
            await asyncio.sleep(wait)
            try:
                await context.bot.send_message(chat_id=chat_id, text=chunk)
            except TelegramError as inner:
                logger.error("Invio fallito a %s anche dopo l'attesa: %s", chat_id, inner)
        except Forbidden as exc:
            logger.info("Non posso scrivere nella chat %s: %s", chat_id, exc)
            return
        except (NetworkError, TelegramError) as exc:
            logger.error("Errore Telegram verso %s: %s", chat_id, exc)


# ---------------------------------------------------------------------------
# Gestione delle azioni
# ---------------------------------------------------------------------------

async def action_help(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    """Mostra il messaggio di benvenuto/aiuto."""
    await send_text(context, chat_id, build_help())


async def action_list(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    """Elenca gli oggetti sotto controllo della chat."""
    items = await asyncio.to_thread(list_items, chat_id)
    await send_text(context, chat_id, format_list(items))


async def action_clear(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    """Rimuove tutti gli oggetti della chat."""
    removed = await asyncio.to_thread(clear_items, chat_id)
    if removed:
        await send_text(context, chat_id, f"🧹 Fatto! Ho tolto {removed} oggetti dal controllo.")
    else:
        await send_text(context, chat_id, "Non c'era nessun oggetto sotto controllo da eliminare.")


async def action_changelog(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, how_many: Optional[int] = None
) -> None:
    """Mostra la cronologia delle modifiche."""
    markdown = await asyncio.to_thread(read_changelog)
    await send_text(context, chat_id, format_changelog(markdown, how_many or 3))


async def action_delete(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, index: int
) -> None:
    """Elimina l'oggetto con quel numero progressivo."""
    removed = await asyncio.to_thread(delete_item, chat_id, index)
    if removed is None:
        total = await asyncio.to_thread(count_items, chat_id)
        if total == 0:
            await send_text(context, chat_id, "Non hai oggetti sotto controllo da eliminare.")
        else:
            await send_text(
                context,
                chat_id,
                f"Il numero {index} non esiste. Hai {total} oggetti: usa \"lista\" per vederli.",
            )
        return
    await send_text(
        context,
        chat_id,
        f"🗑️ Ho smesso di controllare:\n{shorten(removed.title, 80)}",
    )


async def action_link(context: ContextTypes.DEFAULT_TYPE, chat_id: int, index: int) -> None:
    """Invia il link eBay dell'oggetto con quel numero progressivo."""
    item = await asyncio.to_thread(find_by_index, chat_id, index)
    if item is None:
        total = await asyncio.to_thread(count_items, chat_id)
        if total == 0:
            await send_text(
                context,
                chat_id,
                "Non hai ancora oggetti sotto controllo: incolla un link eBay per iniziare 😉",
            )
        else:
            await send_text(
                context,
                chat_id,
                f"Il numero {index} non esiste. Hai {total} oggetti: usa \"lista\" per vederli.",
            )
        return
    await send_text(
        context,
        chat_id,
        f"{item.index}. {shorten(item.title, 80)}\n"
        f"Ultimo prezzo: {format_price(item.last_price, item.currency)}\n"
        f"{item.url}",
    )


async def action_add(context: ContextTypes.DEFAULT_TYPE, chat_id: int, item_id: str) -> None:
    """Aggiunge un oggetto al monitoraggio: recupera prezzo e titolo da eBay."""
    existing = await asyncio.to_thread(find_by_item_id, chat_id, item_id)
    if existing is not None:
        await send_text(
            context,
            chat_id,
            f"⚠️ Questo oggetto è già sotto controllo al numero {existing.index}.\n{existing.url}",
        )
        return

    total = await asyncio.to_thread(count_items, chat_id)
    if total >= MAX_TRACKED_PER_CHAT:
        await send_text(
            context,
            chat_id,
            f"Hai raggiunto il limite di {MAX_TRACKED_PER_CHAT} oggetti per chat. "
            'Usa "azzera" o "cancella <numero>" per fare spazio.',
        )
        return

    try:
        await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
    except TelegramError:
        pass

    # La richiesta HTTP è bloccante: la eseguiamo in un thread per non congelare il bot.
    info = await asyncio.to_thread(get_ebay_info, item_id)
    if info is None or info.price is None:
        await send_text(
            context,
            chat_id,
            f"😕 Non riesco a leggere il prezzo dell'oggetto {item_id}.\n"
            "Controlla che il link sia corretto e che l'inserzione sia ancora attiva.",
        )
        return

    url = info.url or build_item_url(item_id)
    await asyncio.to_thread(
        add_item, chat_id, info.item_id, info.price, info.title, url, info.currency
    )
    index = await asyncio.to_thread(count_items, chat_id)

    note = "\n⚠️ L'inserzione risulta conclusa: il prezzo non cambierà più." if info.ended else ""
    await send_text(
        context,
        chat_id,
        f"✅ Aggiunto al tracciamento come numero {index}:\n"
        f"{shorten(info.title, 80)}\n"
        f"Prezzo attuale: {format_price(info.price, info.currency)}\n"
        f"{url}{note}",
    )


async def action_unknown(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> None:
    """Risposta di cortesia ai messaggi non riconosciuti."""
    await send_text(context, chat_id, UNKNOWN_TEXT)


async def route_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Punto d'ingresso unico: smista ogni messaggio testuale all'azione corretta."""
    message = update.effective_message
    chat = update.effective_chat
    if message is None or chat is None:
        return

    text = message.text or message.caption or ""
    parsed = parse_message(text)
    chat_id = chat.id

    logger.info("Chat %s -> %s %r", chat_id, parsed.action.value, parsed.value)

    try:
        if parsed.action is Action.IGNORE:
            return
        if parsed.action is Action.HELP:
            await action_help(context, chat_id)
        elif parsed.action is Action.LIST:
            await action_list(context, chat_id)
        elif parsed.action is Action.CLEAR:
            await action_clear(context, chat_id)
        elif parsed.action is Action.CHANGELOG:
            await action_changelog(context, chat_id, parsed.value)
        elif parsed.action is Action.DELETE:
            await action_delete(context, chat_id, parsed.value)
        elif parsed.action is Action.DELETE_USAGE:
            await send_text(context, chat_id, DELETE_USAGE)
        elif parsed.action is Action.LINK:
            await action_link(context, chat_id, parsed.value)
        elif parsed.action is Action.LINK_USAGE:
            await send_text(context, chat_id, LINK_USAGE)
        elif parsed.action is Action.ADD:
            await action_add(context, chat_id, parsed.value)
        else:
            await action_unknown(context, chat_id)
    except Exception:  # noqa: BLE001 - un errore non deve mai far cadere il polling
        logger.exception("Errore gestendo il messaggio %r nella chat %s", text, chat_id)
        try:
            await send_text(
                context,
                chat_id,
                "Ops, qualcosa è andato storto 😅 Riprova fra poco o scrivi \"aiuto\".",
            )
        except Exception:  # noqa: BLE001
            logger.exception("Impossibile inviare il messaggio di errore alla chat %s", chat_id)


# ---------------------------------------------------------------------------
# Worker in background: ricontrollo periodico dei prezzi
# ---------------------------------------------------------------------------

async def check_prices_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Job pianificato: aggiorna i prezzi e notifica le variazioni.

    Ogni oggetto viene ricontrollato con una piccola pausa fra una richiesta e
    l'altra per non stressare eBay. Gli errori su un singolo oggetto non
    interrompono il giro.
    """
    items = await asyncio.to_thread(all_tracked_items)
    if not items:
        logger.debug("Nessun oggetto da controllare")
        return

    logger.info("Controllo prezzi: %d oggetti in %d chat", len(items), len({i.chat_id for i in items}))

    changes = 0
    failures = 0
    for position, item in enumerate(items):
        if position:
            await asyncio.sleep(REQUEST_DELAY_SECONDS + random.uniform(0, 1.5))

        info = await asyncio.to_thread(get_ebay_info, item.item_id)
        if info is None:
            failures += 1
            logger.info("Nessun dato per l'oggetto %s (chat %s)", item.item_id, item.chat_id)
            continue

        if info.ended:
            await asyncio.to_thread(mark_ended, item.row_id)
            await send_text(
                context,
                item.chat_id,
                f"⛔ L'inserzione è terminata, smetto di controllarla:\n"
                f"{shorten(item.title, 80)}\n{item.url}",
            )
            continue

        if info.title and info.title != item.title:
            # I venditori modificano i titoli: teniamo aggiornato anche il database.
            await asyncio.to_thread(update_title, item.row_id, info.title)
            item.title = info.title

        notification = describe_price_change(item.last_price, info.price, item)
        if info.price is not None and info.price != item.last_price:
            await asyncio.to_thread(update_price, item.row_id, info.price)
        else:
            await asyncio.to_thread(touch_checked, item.row_id)

        if notification:
            changes += 1
            await send_text(context, item.chat_id, notification)

    logger.info(
        "Controllo prezzi completato: %d variazioni, %d oggetti non raggiungibili",
        changes,
        failures,
    )


# ---------------------------------------------------------------------------
# Avvio
# ---------------------------------------------------------------------------

def _schedule_jobs(application: Application) -> None:
    """Registra il worker periodico se la job queue è disponibile."""
    if application.job_queue is None:
        logger.warning(
            "Job queue non disponibile: installa python-telegram-bot[job-queue]. "
            "Il controllo automatico dei prezzi resterà disattivato."
        )
        return

    interval = CHECK_INTERVAL_MINUTES * 60
    application.job_queue.run_repeating(
        check_prices_job,
        interval=interval,
        first=60,  # primo giro dopo un minuto, per partire subito
        name="check_prices",
    )
    logger.info("Worker pianificato ogni %d minuti", CHECK_INTERVAL_MINUTES)


def build_application(token: str) -> Application:
    """Costruisce l'Application con handler e job queue già configurati."""
    application = (
        ApplicationBuilder()
        .token(token)
        .concurrent_updates(True)   # più chat servite in parallelo
        .build()
    )

    # Un solo handler per tutto il testo: comandi con "/", testo semplice e post
    # dei canali finiscono nello stesso smistatore (case-insensitive di fabbrica).
    # block=False: ogni messaggio viene servito in un task proprio, così il
    # download di una pagina eBay (che può richiedere secondi) non mette in coda
    # gli altri utenti.
    application.add_handler(
        MessageHandler(
            filters.TEXT | filters.COMMAND | filters.UpdateType.CHANNEL_POST,
            route_message,
            block=False,
        )
    )

    _schedule_jobs(application)
    return application


async def run_check_once() -> int:
    """Esegue un solo giro di controllo prezzi e termina.

    Serve per gli ambienti che non ospitano un processo residente: cron di GitHub
    Actions, scheduled task di PythonAnywhere, crontab su VPS. In questa modalità
    il bot *invia* le notifiche di variazione ma non risponde ai comandi.
    """
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    inizializzata = False
    try:
        # initialize() chiama get_me(): se il token è sbagliato si ferma subito
        # con un errore chiaro invece di girare a vuoto.
        await application.initialize()
        inizializzata = True
        await check_prices_job(SimpleNamespace(bot=application.bot))
    finally:
        if inizializzata:  # chiudiamo il client HTTP solo se è stato aperto
            await application.shutdown()
    return 0


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Legge la riga di comando."""
    parser = argparse.ArgumentParser(
        prog="mianonnabot",
        description="Bot Telegram che tiene d'occhio i prezzi su eBay.",
    )
    parser.add_argument(
        "--check-once",
        action="store_true",
        help="esegue un solo controllo prezzi e termina (per cron/Actions/scheduled task)",
    )
    parser.add_argument(
        "--version", action="version", version=f"{BOT_NAME} {__version__}"
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point del bot."""
    args = parse_args(argv)

    if not TELEGRAM_BOT_TOKEN:
        logger.error(
            "Manca TELEGRAM_BOT_TOKEN: imposta la variabile d'ambiente col token di @BotFather."
        )
        return 1

    init_db()
    logger.info(
        "%s v%s avviato — sito %s, API Browse %s, intervallo %d min",
        BOT_NAME,
        __version__,
        EBAY_SITE,
        "attive" if USE_BROWSE_API else "non configurate (scraping)",
        CHECK_INTERVAL_MINUTES,
    )

    if args.check_once:
        logger.info("Modalità --check-once: un solo giro di controllo e poi esco")
        try:
            return asyncio.run(run_check_once())
        except InvalidToken:
            logger.error("Token Telegram rifiutato dal server: controlla TELEGRAM_BOT_TOKEN.")
            return 1
        except TelegramError as exc:
            logger.error("Impossibile contattare Telegram: %s", exc)
            return 1

    application = build_application(TELEGRAM_BOT_TOKEN)
    # ALL_TYPES è necessario per ricevere anche i post dei canali.
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
