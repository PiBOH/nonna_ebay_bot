# -*- coding: utf-8 -*-
"""
Test automatici di MiaNonnaBot.

Esegui con:  pytest -q
(oppure:     python -m pytest tests/ -q)

I test usano solo codice reale di ``main.py``: il database viene puntato su un
file temporaneo e le chiamate HTTP vengono sostituite da HTML di esempio, quindi
non serve né il token Telegram né la rete.
"""

from __future__ import annotations

import os
import sys
import types
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import main  # noqa: E402  (import dopo il path fix)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def temp_database(tmp_path, monkeypatch):
    """Ogni test usa un database SQLite nuovo e isolato."""
    db_file = tmp_path / "test_bot.db"
    monkeypatch.setattr(main, "DATABASE_PATH", str(db_file))
    monkeypatch.setattr(main, "MAX_TRACKED_PER_CHAT", 50)
    monkeypatch.setattr(main, "REQUEST_DELAY_SECONDS", 0.0)
    main.init_db()
    return db_file


class FakeBot:
    """Sostituto minimo di ``telegram.Bot``: memorizza i messaggi inviati."""

    def __init__(self) -> None:
        self.messages: list[tuple[int, str]] = []
        self.actions: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str, **kwargs) -> object:
        self.messages.append((chat_id, text))
        return SimpleNamespace(message_id=len(self.messages))

    async def send_chat_action(self, chat_id: int, action: str, **kwargs) -> bool:
        self.actions.append((chat_id, action))
        return True

    @property
    def last_text(self) -> str:
        return self.messages[-1][1]

    @property
    def all_text(self) -> str:
        return "\n".join(text for _, text in self.messages)


@pytest.fixture()
def context():
    return SimpleNamespace(bot=FakeBot())


def make_update(text: str, chat_id: int = 42):
    return SimpleNamespace(
        effective_message=SimpleNamespace(text=text, caption=None),
        effective_chat=SimpleNamespace(id=chat_id),
    )


def run(coro):
    """Esegue una coroutine senza bisogno di pytest-asyncio."""
    import asyncio

    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Parsing dei comandi (case-insensitive, con e senza slash, alias)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text, action, value",
    [
        # aiuto
        ("aiuto", main.Action.HELP, None),
        ("AIUTO", main.Action.HELP, None),
        ("Help", main.Action.HELP, None),
        ("/help", main.Action.HELP, None),
        ("/HELP", main.Action.HELP, None),
        ("/h", main.Action.HELP, None),
        ("H", main.Action.HELP, None),
        ("/start", main.Action.HELP, None),
        ("/aiuto@MiaNonnaBot", main.Action.HELP, None),
        # lista
        ("lista", main.Action.LIST, None),
        ("LISTA", main.Action.LIST, None),
        ("/lista", main.Action.LIST, None),
        ("list", main.Action.LIST, None),
        ("/L", main.Action.LIST, None),
        # azzera
        ("azzera", main.Action.CLEAR, None),
        ("AZZERA", main.Action.CLEAR, None),
        ("/azzera", main.Action.CLEAR, None),
        # changelog
        ("changelog", main.Action.CHANGELOG, None),
        ("CHANGELOG", main.Action.CHANGELOG, None),
        ("/changelog", main.Action.CHANGELOG, None),
        ("/changelog 5", main.Action.CHANGELOG, 5),
        # cancella
        ("cancella 3", main.Action.DELETE, 3),
        ("CANCELLA 3", main.Action.DELETE, 3),
        ("/cancella 12", main.Action.DELETE, 12),
        ("elimina 2", main.Action.DELETE, 2),
        ("cancella", main.Action.DELETE_USAGE, None),
        # numero / link
        ("numero 1", main.Action.LINK, 1),
        ("/numero 4", main.Action.LINK, 4),
        ("1", main.Action.LINK, 1),
        ("/1", main.Action.LINK, 1),
        ("7", main.Action.LINK, 7),
        ("link 2", main.Action.LINK, 2),
        ("numero", main.Action.LINK_USAGE, None),
        # inserimento
        ("https://www.ebay.it/itm/405399021732", main.Action.ADD, "405399021732"),
        (
            "https://www.ebay.it/itm/405399021732?hash=item5ec&itmprp=abc",
            main.Action.ADD,
            "405399021732",
        ),
        ("/405399021732", main.Action.ADD, "405399021732"),
        ("405399021732", main.Action.ADD, "405399021732"),
        ("guarda https://www.ebay.it/itm/167017705623?_ul=IT", main.Action.ADD, "167017705623"),
        # non riconosciuto
        ("ciao nonna", main.Action.UNKNOWN, None),
        ("", main.Action.IGNORE, None),
        ("   ", main.Action.IGNORE, None),
    ],
)
def test_parse_message(text, action, value):
    parsed = main.parse_message(text)
    assert parsed.action is action
    assert parsed.value == value


def test_parse_message_ignora_casualita_e_spazi():
    for text in ("  LiStA  ", "\t/Lista\t", "LISTA"):
        assert main.parse_message(text).action is main.Action.LIST


def test_extract_item_id_varianti():
    assert main.extract_item_id("https://www.ebay.it/itm/405399021732") == "405399021732"
    assert (
        main.extract_item_id("https://www.ebay.it/itm/Apple-iPhone-13-128GB/405399021732?x=1")
        == "405399021732"
    )
    assert main.extract_item_id("https://m.ebay.it/itm/167017705623?nordt=true") == "167017705623"
    assert (
        main.extract_item_id("https://www.ebay.it/itm/ViewItem&item=123456789012")
        == "123456789012"
    )
    assert main.extract_item_id("https://www.ebay.com/itm/257594349554") == "257594349554"
    assert main.extract_item_id("405399021732") == "405399021732"
    assert main.extract_item_id("ciao, come va?") is None
    assert main.extract_item_id("1") is None


def test_build_item_url_con_e_senza_affiliazione(monkeypatch):
    monkeypatch.setattr(main, "EPN_CAMPAIGN_ID", "")
    assert main.build_item_url("405399021732") == "https://www.ebay.it/itm/405399021732"
    monkeypatch.setattr(main, "EPN_CAMPAIGN_ID", "5339999999")
    monkeypatch.setattr(main, "EPN_TOOL_ID", "10001")
    url = main.build_item_url("405399021732")
    assert url.startswith("https://www.ebay.it/itm/405399021732?")
    assert "campid=5339999999" in url and "toolid=10001" in url


# ---------------------------------------------------------------------------
# Parsing dei prezzi
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "raw, expected",
    [
        ("EUR 500,00", 500.00),
        ("EUR 1.234,56", 1234.56),
        ("€49,99", 49.99),
        ("500.0", 500.0),          # formato JSON-LD
        ("1234.56", 1234.56),
        ("1.234", 1234.0),          # migliaia in italiano
        ("1,234.56", 1234.56),      # formato anglosassone
        ("EUR 1\u00a0234,50", 1234.50),
        ("EUR 20,24 consegna", 20.24),
        ("500", 500.0),
        (500.0, 500.0),
        (None, None),
        ("", None),
        ("n/d", None),
        ("EUR 0,00", None),
        ("Gratis", None),
    ],
)
def test_parse_price(raw, expected):
    assert main.parse_price(raw) == expected


def test_format_price_stile_italiano():
    assert main.format_price(500.0) == "€500,00"
    assert main.format_price(1234.5) == "€1.234,50"
    assert main.format_price(49.99) == "€49,99"
    assert main.format_price(None) == "n/d"


# ---------------------------------------------------------------------------
# Parsing della pagina eBay (fixture realistiche)
# ---------------------------------------------------------------------------

JSON_LD_PAGE = """
<html><head>
<title>Apple iPhone 13 - 128GB - Bianco | eBay</title>
<script type="application/ld+json">
{"@context":"https://schema.org","@type":"Product","name":"Apple iPhone 13 - 128GB - Bianco",
 "offers":{"@type":"Offer","itemCondition":"https://schema.org/NewCondition",
 "availability":"https://schema.org/InStock","priceCurrency":"EUR","price":"500.0",
 "shippingDetails":[{"shippingRate":{"value":"5.0","currency":"EUR"}}]},
 "aggregateRating":{"ratingValue":"4.75","ratingCount":"4"}}
</script>
</head><body><h1 class="x-item-title__mainTitle"><span>Apple iPhone 13 - 128GB - Bianco</span></h1>
<div class="x-price-primary"><span class="ux-labels-values__values">EUR 500,00</span></div>
</body></html>
"""

MICRODATA_PAGE = """
<html><head><title>Console</title></head><body>
<div itemscope itemtype="https://schema.org/Product">
  <h1 itemprop="name">Sony PlayStation 5 Slim 1TB</h1>
  <div itemprop="offers" itemscope itemtype="https://schema.org/Offer">
    <meta itemprop="priceCurrency" content="EUR" />
    <span itemprop="price" content="429.90">EUR 429,90</span>
  </div>
</div>
</body></html>
"""

CSS_ONLY_PAGE = """
<html><head><title>Oggetto</title></head><body>
<h1 class="x-item-title__mainTitle"><span class="ux-textspans">Lego Technic 42151 Bugatti</span></h1>
<div class="x-price-primary"><span class="ux-labels-values__values">EUR 89,90</span></div>
</body></html>
"""

RAW_JSON_PAGE = """
<html><head><title>Oggetto</title></head><body>
<script>{"components":{"x-price":{"displayPrice":"EUR 19,99"}}}</script>
<div class="something-else">nessun selettore noto</div>
</body></html>
"""

ENDED_PAGE = """
<html><head><title>Oggetto terminato</title></head><body>
<h1 class="x-item-title__mainTitle"><span>Vecchio oggetto</span></h1>
<div class="x-price-primary"><span>EUR 12,00</span></div>
<p>L'inserzione è terminata.</p>
</body></html>
"""

NO_PRICE_PAGE = "<html><body><h1>Pagina di errore</h1><p>Impossibile trovare l'oggetto.</p></body></html>"


def test_parse_page_json_ld():
    info = main.parse_ebay_page(JSON_LD_PAGE, "405399021732")
    assert info.title == "Apple iPhone 13 - 128GB - Bianco"
    assert info.price == 500.0
    assert info.currency == "EUR"
    assert info.source == "json-ld"
    assert info.ended is False
    assert info.url == "https://www.ebay.it/itm/405399021732"


def test_parse_page_microdata():
    info = main.parse_ebay_page(MICRODATA_PAGE, "111111111111")
    assert info.title == "Sony PlayStation 5 Slim 1TB"
    assert info.price == 429.90
    assert info.source == "microdata"


def test_parse_page_css():
    info = main.parse_ebay_page(CSS_ONLY_PAGE, "222222222222")
    assert info.title == "Lego Technic 42151 Bugatti"
    assert info.price == 89.90
    assert info.source == "css"


def test_parse_page_regex_di_riserva():
    info = main.parse_ebay_page(RAW_JSON_PAGE, "333333333333")
    assert info.price == 19.99
    assert info.source == "regex"


def test_parse_page_inserzione_terminata():
    info = main.parse_ebay_page(ENDED_PAGE, "444444444444")
    assert info.ended is True
    assert info.price == 12.0


def test_parse_page_senza_prezzo_solleva_errore():
    with pytest.raises(ValueError):
        main.parse_ebay_page(NO_PRICE_PAGE, "555555555555")


def test_get_ebay_info_usa_html_scaricato(monkeypatch):
    monkeypatch.setattr(main, "USE_BROWSE_API", False)
    monkeypatch.setattr(main, "_http_get", lambda url, attempts=2: JSON_LD_PAGE)
    info = main.get_ebay_info("405399021732")
    assert info is not None
    assert info.price == 500.0
    assert info.title == "Apple iPhone 13 - 128GB - Bianco"


def test_get_ebay_info_rifiuta_id_non_validi(monkeypatch):
    monkeypatch.setattr(main, "_http_get", lambda url, attempts=2: JSON_LD_PAGE)
    assert main.get_ebay_info("123") is None
    assert main.get_ebay_info("abc") is None


def test_get_ebay_info_pagina_non_raggiungibile(monkeypatch):
    monkeypatch.setattr(main, "USE_BROWSE_API", False)
    monkeypatch.setattr(main, "_http_get", lambda url, attempts=2: None)
    assert main.get_ebay_info("405399021732") is None


def test_get_ebay_info_api_browse(monkeypatch):
    """Con le credenziali impostate il bot preferisce l'API ufficiale."""
    monkeypatch.setattr(main, "USE_BROWSE_API", True)
    monkeypatch.setattr(main, "_browse_token", lambda: "token-di-prova")

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json():
            return {
                "title": "Apple iPhone 13 - 128GB - Blu (Sbloccato)",
                "price": {"value": "529.68", "currency": "EUR"},
            }

    monkeypatch.setattr(main.requests, "get", lambda *args, **kwargs: FakeResponse())
    info = main.get_ebay_info("167017705623")
    assert info is not None
    assert info.source == "browse-api"
    assert info.price == 529.68
    assert info.currency == "EUR"


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def test_db_indice_progressivo_e_cancellazione():
    main.add_item(7, "111111111111", 10.0, "Primo oggetto", "https://www.ebay.it/itm/111111111111")
    main.add_item(7, "222222222222", 20.0, "Secondo oggetto", "https://www.ebay.it/itm/222222222222")
    main.add_item(7, "333333333333", 30.0, "Terzo oggetto", "https://www.ebay.it/itm/333333333333")
    main.add_item(8, "444444444444", 40.0, "Altra chat", "https://www.ebay.it/itm/444444444444")

    items = main.list_items(7)
    assert [item.index for item in items] == [1, 2, 3]
    assert [item.title for item in items] == ["Primo oggetto", "Secondo oggetto", "Terzo oggetto"]

    # Gli indici sono indipendenti per ogni chat.
    assert [item.index for item in main.list_items(8)] == [1]

    removed = main.delete_item(7, 2)
    assert removed is not None and removed.item_id == "222222222222"

    after = main.list_items(7)
    assert [item.index for item in after] == [1, 2]  # i numeri restano compatti
    assert [item.item_id for item in after] == ["111111111111", "333333333333"]

    assert main.delete_item(7, 99) is None
    assert main.find_by_index(7, 2).item_id == "333333333333"
    assert main.find_by_item_id(7, "111111111111").index == 1
    assert main.count_items(7) == 2

    assert main.clear_items(7) == 2
    assert main.list_items(7) == []
    assert main.count_items(8) == 1  # le altre chat non vengono toccate


def test_db_aggiornamento_prezzo_e_stato():
    main.add_item(7, "111111111111", 100.0, "Oggetto", "https://www.ebay.it/itm/111111111111")
    row = main.list_items(7)[0]

    main.update_price(row.row_id, 80.0)
    assert main.list_items(7)[0].last_price == 80.0
    assert main.list_items(7)[0].last_checked is not None

    main.mark_ended(row.row_id)
    assert main.list_items(7)[0].ended is True
    assert main.all_tracked_items() == []  # le concluse escono dal worker


def test_all_tracked_items_indici_per_chat():
    for chat in (1, 1, 2, 2, 2):
        main.add_item(chat, f"{chat}0000000{len(main.all_tracked_items())}1", 1.0, "T", "u")
    items = main.all_tracked_items()
    assert sorted(item.index for item in items if item.chat_id == 1) == [1, 2]
    assert sorted(item.index for item in items if item.chat_id == 2) == [1, 2, 3]


# ---------------------------------------------------------------------------
# Testi e formattazione
# ---------------------------------------------------------------------------

def test_messaggio_di_aiuto_esatto():
    text = main.build_help()
    assert text.startswith(f"{main.BOT_NAME}:\nVersione: {main.__version__}")
    assert "Versione: 0.0.1" in text
    for expected in (
        "👋 Comandi utilizzabili",
        "* aiuto,help,h : questo messaggio",
        "* lista,list,l : elenco prodotti sotto controllo",
        "* cancella num : elimina prodotto da osservare",
        "* azzera : elimina tutti i prodotti sottoscritti",
        '* numero : richiama link prodotto n (es. inviando solo il numero "1" o "/1" o "numero 1")',
        "* changelog : mostra il registro delle modifiche",
        "Incolla un link eBay, per tener sotto controllo il prezzo",
        "❤️ Il bot si può aggiungere a gruppi e canali ❤️",
        "Il Bot è ancora in fase di sviluppo e può funzionare non correttamente.",
    ):
        assert expected in text


def test_format_list():
    main.add_item(7, "111111111111", 49.99, "Apple iPhone 13 - 128GB - Bianco", "u")
    main.add_item(7, "222222222222", 89.9, "Lego Technic 42151 Bugatti", "u")
    text = main.format_list(main.list_items(7))
    assert "1. Apple iPhone 13 - 128GB - Bianco - €49,99" in text
    assert "2. Lego Technic 42151 Bugatti - €89,90" in text
    assert "2 oggetti sotto controllo" in text


def test_format_list_vuota():
    assert "Nessun oggetto sotto controllo" in main.format_list([])


def test_split_message_rispetta_il_limite():
    righe = [f"riga numero {i}" for i in range(600)]
    text = "\n".join(righe)
    chunks = main.split_message(text, limit=200)
    assert len(chunks) > 1
    assert all(len(chunk) <= 200 for chunk in chunks)
    # Nessuna riga deve andare persa nel frazionamento.
    assert "\n".join(chunks).split("\n") == righe
    # Una riga singola più lunga del limite viene comunque spezzata.
    lunga = "x" * 500
    assert [len(c) for c in main.split_message(lunga, limit=200)] == [200, 200, 100]
    assert main.split_message("corto") == ["corto"]


def test_changelog_estratto_dal_file_reale():
    markdown = main.read_changelog()
    assert "[0.0.1]" in markdown
    text = main.format_changelog(markdown, 2)
    assert "📒 Changelog" in text
    assert "[Unreleased]" in text
    assert "[0.0.1] - 2026-08-28" in text
    assert len(text) <= main.MAX_MESSAGE_LENGTH


def test_changelog_assente():
    assert main.format_changelog("", 3) == "Changelog non disponibile."


def test_notifica_di_variazione_prezzo():
    item = main.TrackedItem(
        row_id=1, index=1, chat_id=7, item_id="111111111111",
        last_price=100.0, title="Apple iPhone 13", url="https://www.ebay.it/itm/111111111111",
    )
    down = main.describe_price_change(100.0, 89.9, item)
    assert down.startswith("📉 Prezzo sceso da €100,00 a €89,90!")
    assert item.url in down

    up = main.describe_price_change(100.0, 120.0, item)
    assert up.startswith("📈 Prezzo aumentato da €100,00 a €120,00!")

    assert main.describe_price_change(100.0, 100.0, item) is None
    assert main.describe_price_change(100.0, 100.004, item) is None
    assert main.describe_price_change(None, 100.0, item) is None


# ---------------------------------------------------------------------------
# Comandi end-to-end (handler reali, bot finto)
# ---------------------------------------------------------------------------

def test_comando_aiuto(context):
    run(main.route_message(make_update("/HELP"), context))
    assert "Versione: 0.0.1" in context.bot.last_text
    assert "* lista,list,l : elenco prodotti sotto controllo" in context.bot.last_text


def test_comando_lista_vuota_e_piena(context):
    run(main.route_message(make_update("lista"), context))
    assert "Nessun oggetto sotto controllo" in context.bot.last_text

    main.add_item(42, "405399021732", 500.0, "Apple iPhone 13 - 128GB - Bianco", "u")
    run(main.route_message(make_update("/LISTA"), context))
    assert "1. Apple iPhone 13 - 128GB - Bianco - €500,00" in context.bot.last_text


def test_aggiunta_link_e_duplicato(context, monkeypatch):
    info = main.EbayInfo(
        item_id="405399021732",
        title="Apple iPhone 13 - 128GB - Bianco",
        price=500.0,
        currency="EUR",
        url="https://www.ebay.it/itm/405399021732",
    )
    monkeypatch.setattr(main, "get_ebay_info", lambda item_id: info)

    run(main.route_message(make_update("https://www.ebay.it/itm/405399021732?hash=x"), context))
    reply = context.bot.last_text
    assert "✅ Aggiunto al tracciamento come numero 1" in reply
    assert "Prezzo attuale: €500,00" in reply
    assert main.count_items(42) == 1
    assert main.list_items(42)[0].title == "Apple iPhone 13 - 128GB - Bianco"

    # Lo stesso link una seconda volta non duplica.
    run(main.route_message(make_update("https://www.ebay.it/itm/405399021732"), context))
    assert "già sotto controllo" in context.bot.last_text
    assert main.count_items(42) == 1


def test_aggiunta_fallita(context, monkeypatch):
    monkeypatch.setattr(main, "get_ebay_info", lambda item_id: None)
    run(main.route_message(make_update("https://www.ebay.it/itm/999999999999"), context))
    assert "Non riesco a leggere il prezzo" in context.bot.last_text
    assert main.count_items(42) == 0


def test_numero_restituisce_il_link(context):
    main.add_item(42, "111111111111", 12.5, "Primo", "https://www.ebay.it/itm/111111111111")
    main.add_item(42, "222222222222", 30.0, "Secondo", "https://www.ebay.it/itm/222222222222")

    run(main.route_message(make_update("2"), context))
    assert "https://www.ebay.it/itm/222222222222" in context.bot.last_text
    assert "Secondo" in context.bot.last_text

    run(main.route_message(make_update("/numero 1"), context))
    assert "https://www.ebay.it/itm/111111111111" in context.bot.last_text

    run(main.route_message(make_update("9"), context))
    assert "Il numero 9 non esiste" in context.bot.last_text


def test_cancella_e_azzera(context):
    main.add_item(42, "111111111111", 12.5, "Primo", "u1")
    main.add_item(42, "222222222222", 30.0, "Secondo", "u2")

    run(main.route_message(make_update("cancella 1"), context))
    assert "Ho smesso di controllare" in context.bot.last_text
    assert main.count_items(42) == 1
    assert main.list_items(42)[0].item_id == "222222222222"

    run(main.route_message(make_update("cancella"), context))
    assert context.bot.last_text == main.DELETE_USAGE

    run(main.route_message(make_update("/azzera"), context))
    assert "Ho tolto 1 oggetti" in context.bot.last_text
    assert main.count_items(42) == 0

    run(main.route_message(make_update("azzera"), context))
    assert "nessun oggetto sotto controllo" in context.bot.last_text


def test_changelog_da_telegram(context):
    run(main.route_message(make_update("/changelog"), context))
    assert "📒 Changelog MiaNonnaBot" in context.bot.last_text
    assert "0.0.1" in context.bot.last_text


def test_messaggio_sconosciuto(context):
    run(main.route_message(make_update("buongiorno!"), context))
    assert context.bot.last_text == main.UNKNOWN_TEXT


def test_chat_diverse_non_si_disturbano(context):
    main.add_item(42, "111111111111", 12.5, "Oggetto di 42", "u1")
    run(main.route_message(make_update("lista", chat_id=99), context))
    assert "Nessun oggetto sotto controllo" in context.bot.last_text


def test_worker_notifica_ribasso_e_rincaro(context, monkeypatch):
    main.add_item(42, "111111111111", 100.0, "Oggetto che scende", "https://www.ebay.it/itm/111111111111")
    main.add_item(42, "222222222222", 50.0, "Oggetto che sale", "https://www.ebay.it/itm/222222222222")
    main.add_item(42, "333333333333", 70.0, "Oggetto fermo", "https://www.ebay.it/itm/333333333333")

    prezzi = {"111111111111": 89.90, "222222222222": 55.00, "333333333333": 70.0}

    def fake_get(item_id):
        return main.EbayInfo(
            item_id=item_id,
            title=f"Titolo {item_id}",
            price=prezzi[item_id],
            currency="EUR",
            url=f"https://www.ebay.it/itm/{item_id}",
        )

    monkeypatch.setattr(main, "get_ebay_info", fake_get)
    run(main.check_prices_job(context))

    inviati = context.bot.all_text
    assert "📉 Prezzo sceso da €100,00 a €89,90!" in inviati
    assert "📈 Prezzo aumentato da €50,00 a €55,00!" in inviati
    assert "Titolo 333333333333" not in inviati  # nessuna variazione, nessun messaggio

    assert main.find_by_index(42, 1).last_price == 89.90
    assert main.find_by_index(42, 2).last_price == 55.00

    # Secondo giro: prezzi invariati, nessuna nuova notifica.
    context.bot.messages.clear()
    run(main.check_prices_job(context))
    assert context.bot.messages == []


def test_worker_gestisce_inserzione_terminata(context, monkeypatch):
    main.add_item(42, "111111111111", 100.0, "Oggetto terminato", "https://www.ebay.it/itm/111111111111")

    def fake_get(item_id):
        return main.EbayInfo(
            item_id=item_id, title="Oggetto terminato", price=100.0,
            currency="EUR", url=f"https://www.ebay.it/itm/{item_id}", ended=True,
        )

    monkeypatch.setattr(main, "get_ebay_info", fake_get)
    run(main.check_prices_job(context))
    assert "L'inserzione è terminata" in context.bot.all_text
    assert main.list_items(42)[0].ended is True

    context.bot.messages.clear()
    run(main.check_prices_job(context))  # non viene più controllata
    assert context.bot.messages == []


def test_worker_resiste_a_oggetti_non_raggiungibili(context, monkeypatch):
    main.add_item(42, "111111111111", 100.0, "Oggetto offline", "u")
    monkeypatch.setattr(main, "get_ebay_info", lambda item_id: None)
    run(main.check_prices_job(context))
    assert context.bot.messages == []
    assert main.list_items(42)[0].last_price == 100.0


def test_build_application_registra_handler_e_job(monkeypatch):
    """Verifica l'assemblaggio reale: handler del testo + job queue pianificata."""
    monkeypatch.setenv("CHECK_INTERVAL_MINUTES", "30")
    monkeypatch.setattr(main, "CHECK_INTERVAL_MINUTES", 30)

    import importlib

    main_module = importlib.reload(main)
    app = main_module.build_application("123456:token-di-prova")

    assert len(app.handlers[0]) == 1
    assert isinstance(app.handlers[0][0], main_module.MessageHandler)
    assert app.job_queue is not None
    job_names = [job.name for job in app.job_queue.get_jobs_by_name("check_prices")]
    assert job_names == ["check_prices"]


# ---------------------------------------------------------------------------
# Smoke test: l'handler registrato riceve veri oggetti telegram.Update
# ---------------------------------------------------------------------------

def _real_update(text: str, chat_id: int = 42) -> "object":
    """Costruisce un Update reale (stesso tipo che arriva dal polling)."""
    import datetime

    from telegram import Chat, Message, Update, User

    chat = Chat(id=chat_id, type=Chat.PRIVATE)
    message = Message(message_id=1, date=datetime.datetime.now(), chat=chat, text=text)
    return Update(update_id=1, message=message)


def test_handler_reale_con_update_telegram(monkeypatch):
    """Fa passare messaggi veri nell'handler registrato dentro l'Application."""
    info = main.EbayInfo(
        item_id="167017705623",
        title="Apple iPhone 13 - 128GB - Blu (Sbloccato)",
        price=529.68,
        currency="EUR",
        url="https://www.ebay.it/itm/167017705623",
    )
    monkeypatch.setattr(main, "get_ebay_info", lambda item_id: info)

    app = main.build_application("123456:token-di-prova")
    handler = app.handlers[0][0]
    context = SimpleNamespace(bot=FakeBot(), application=app)

    script = [
        "/start",
        "https://www.ebay.it/itm/167017705623?_ul=IT",
        "/LISTA",
        "1",
        "cancella 1",
        "l",
        "/changelog",
    ]
    for text in script:
        run(handler.callback(_real_update(text), context))

    inviati = context.bot.all_text
    assert "Versione: 0.0.1" in inviati                              # /start
    assert "✅ Aggiunto al tracciamento come numero 1" in inviati      # link eBay
    assert "Apple iPhone 13 - 128GB - Blu (Sbloccato)" in inviati
    assert "🗑️ Ho smesso di controllare" in inviati                  # cancella 1
    assert "Nessun oggetto sotto controllo" in inviati                # l (lista vuota)
    assert "📒 Changelog MiaNonnaBot" in inviati                      # /changelog
    # L'azione "sto scrivendo..." viene mostrata durante il recupero del prezzo.
    assert (42, "typing") in context.bot.actions


def test_worker_aggiorna_il_titolo_nel_database(context, monkeypatch):
    """Se il venditore cambia il titolo, il worker allinea anche il database."""
    main.add_item(42, "111111111111", 100.0, "Titolo vecchio", "https://www.ebay.it/itm/111111111111")

    def fake_get(item_id):
        return main.EbayInfo(
            item_id=item_id, title="Titolo nuovo aggiornato dal venditore", price=100.0,
            currency="EUR", url=f"https://www.ebay.it/itm/{item_id}",
        )

    monkeypatch.setattr(main, "get_ebay_info", fake_get)
    run(main.check_prices_job(context))

    assert main.list_items(42)[0].title == "Titolo nuovo aggiornato dal venditore"
    assert context.bot.messages == []  # prezzo invariato: nessuna notifica


def test_handler_non_bloccante(monkeypatch):
    """block=False: una richiesta eBay lenta non mette in coda gli altri utenti."""
    app = main.build_application("123456:token-di-prova")
    handler = app.handlers[0][0]
    assert handler.block is False
    # PTB traduce concurrent_updates(True) nel numero massimo di update paralleli.
    assert app.concurrent_updates
    assert int(app.concurrent_updates) > 1
