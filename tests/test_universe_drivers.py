from core.universe import drivers_for, sector_for


def test_sector_for_known_and_unknown_symbols():
    assert sector_for("TCS") == "IT"
    assert sector_for("hdfcbank") == "BANKING"  # case-insensitive
    assert sector_for("SOME_UNMAPPED_STOCK") == "GENERAL"


def test_drivers_for_symbol_resolves_via_sector():
    assert drivers_for("TCS") == ["NASDAQ", "SEMICONDUCTOR", "KOSPI"]
    assert drivers_for("RELIANCE") == ["BRENT", "USDINR"]


def test_drivers_for_sector_name_directly():
    assert drivers_for("IT") == ["NASDAQ", "SEMICONDUCTOR", "KOSPI"]
    assert drivers_for("BANKING") == ["BRENT", "USDINR"]


def test_drivers_for_unmapped_falls_back_to_general():
    assert drivers_for("SOME_UNMAPPED_STOCK") == drivers_for("GENERAL")
