from app.chain_clients.base import normalize_address


def test_evm_addresses_are_lowercased():
    assert normalize_address("0xAbC0000000000000000000000000000000000A") == "0xabc0000000000000000000000000000000000a"


def test_bitcoin_base58_addresses_are_left_untouched():
    # base58 is case-sensitive - lowercasing would silently produce a
    # different, invalid-looking address.
    addr = "34xp4vRoCGJym3xR7yCVPFHoCNxv4Twseo"
    assert normalize_address(addr) == addr


def test_bitcoin_bech32_addresses_are_left_untouched():
    addr = "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"
    assert normalize_address(addr) == addr
