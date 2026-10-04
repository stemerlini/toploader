"""The TCGCSV catalogue: telling sealed from singles, search, cards and prices."""

import pytest

from toploader.games.tcgcsv import _clean_name, sealed_kind


async def ids(catalog, query):
    return [int(r.id) for r in await catalog.search(query)]


# -- sync ---------------------------------------------------------------------


def test_sealed_products_are_told_apart_from_unnumbered_cards(catalog):
    rows = dict(catalog.db.execute("SELECT id, sealed FROM products").fetchall())
    assert {pid for pid, s in rows.items() if s} == {201, 202, 303}
    # Vintage cards without a number are still singles.
    assert rows[301] == 0 and rows[302] == 0


async def test_catalogue_is_not_downloaded_again_while_fresh(catalog):
    before = len(catalog.requests)
    await catalog.prepare()
    assert len(catalog.requests) == before


@pytest.mark.parametrize("name, kind", [
    ("Shiny Star V Booster Box", "Booster Box"),
    ("Shiny Star V Booster Pack", "Booster Pack"),
    ("Shiny Star V Booster Box Case", "Case"),
    ("151 Elite Trainer Box", "Elite Trainer Box"),
    ("Mighty Mysterious Tins [Set of 3]", "Tin"),
    ("Starter Set ex Eevee ex", "Deck"),
    ("Starter Deck 1996", "Deck"),
    ("Promo Card Pack 25th Anniversary Edition", "Promo Pack"),
    ("Charizard ex Premium Collection", "Collection Box"),
    ("Holiday Calendar 2025", "Collection Box"),
])
def test_sealed_kind(name, kind):
    assert sealed_kind(name) == kind


@pytest.mark.parametrize("raw, clean", [
    ("Red's Pikachu - 270/SM-P", "Red's Pikachu"),
    ("Rowlet - 001/190 (Mirror Holofoil)", "Rowlet (Mirror Holofoil)"),
    ("Card File Set - Venusaur, Charizard", "Card File Set - Venusaur, Charizard"),
    ("Wimpod (Mirror Holofoil)", "Wimpod (Mirror Holofoil)"),
])
def test_clean_name(raw, clean):
    assert _clean_name(raw) == clean


# -- search ---------------------------------------------------------------------


@pytest.mark.parametrize("query", ["270/SM-P", "270/sm-p", "SM-P 270", "sm-p-270"])
async def test_search_by_number(catalog, query):
    assert await ids(catalog, query) == [101]


async def test_number_search_ignores_leading_zeros_but_not_other_digits(catalog):
    # "71" is 071/SM-P, not 171/SM-P or 271/SM-P.
    assert await ids(catalog, "71/SM-P") == [102]


async def test_set_code_lists_whole_set_with_sealed_first(catalog):
    found = await ids(catalog, "s4a")
    assert set(found) == {201, 202, 203, 204}
    assert set(found[:2]) == {201, 202}
    assert found[2:] == [203, 204]  # then the cards in number order


async def test_set_code_with_sealed_keyword(catalog):
    assert set(await ids(catalog, "s4a sealed")) == {201, 202}


async def test_set_code_with_extra_words_narrows_the_set(catalog):
    assert await ids(catalog, "S4A box") == [201]


async def test_sealed_keyword_alone_lists_all_sealed(catalog):
    assert set(await ids(catalog, "sealed")) == {201, 202, 303}


async def test_name_search_needs_a_match_in_the_product_name(catalog):
    found = set(await ids(catalog, "charizard"))
    assert found == {204, 301, 402}
    # Moltres is in a set called "Charizard VSTAR vs Rayquaza…" but isn't a Charizard.
    assert 401 not in found


async def test_name_search_does_not_put_sealed_first(catalog):
    results = await catalog.search("shiny star")
    # Words may match the set name; only browsing by set code orders sealed first.
    assert {int(r.id) for r in results} >= {201, 202}
    assert all(r.sealed == (int(r.id) in {201, 202}) for r in results)


async def test_search_results_have_clean_names(catalog):
    [result] = await catalog.search("270/SM-P")
    assert result.name == "Red's Pikachu"
    assert result.number == "270/SM-P"
    assert result.set_name == "SM-P: Sun & Moon Promos"
    assert not result.sealed


# -- cards & prices ---------------------------------------------------------------


async def test_fetch_single(catalog):
    card = await catalog.fetch_card("101")
    assert card.name == "Red's Pikachu"
    assert card.local_id == "270/SM-P"
    assert card.category == "Pokemon" and card.types == ["Lightning"]
    assert card.variants["holo"] and not card.is_sealed
    assert card.image_url.endswith("_in_1000x1000.jpg")
    assert catalog.price(card, "holo", "tcgplayer") == 454.66


async def test_price_falls_back_to_the_finish_that_has_one(catalog):
    card = await catalog.fetch_card("101")
    # Only a Holofoil price exists; asking for "normal" still finds it.
    assert catalog.price(card, "normal", "tcgplayer") == 454.66


async def test_card_without_listings_has_no_price(catalog):
    card = await catalog.fetch_card("102")
    assert catalog.price(card, "normal", "tcgplayer") is None


async def test_fetch_sealed(catalog):
    box = await catalog.fetch_card("201")
    assert box.is_sealed
    assert box.rarity == "Booster Box"  # the product type
    assert box.conditions == ["S", "SD", "O"]
    assert catalog.price(box, "normal", "tcgplayer") == 168.17


async def test_trainer_and_energy_categories(catalog):
    assert (await catalog.fetch_card("103")).category == "Trainer"
    assert (await catalog.fetch_card("104")).category == "Energy"


async def test_refresh_keeps_old_card_when_download_fails(catalog, monkeypatch):
    card = await catalog.fetch_card("101")

    async def broken(group_id):
        import httpx
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(catalog, "_prices", broken)
    [fresh] = await catalog.refresh([card])
    assert fresh.pricing == card.pricing
