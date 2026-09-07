from app.chain_clients.base import Chain, is_valid_address, normalize_address


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


# ── base58 character class ────────────────────────────────────────────────

def test_legacy_bitcoin_addresses_are_accepted():
    """The regression that mattered most: the base58 class was written
    "[1-9A-HJ-NP-Za-k-z]", where "a-k-z" parses as a-k, a literal hyphen and
    z. Every letter from m to y was excluded, so most real legacy Bitcoin
    addresses were rejected the moment an investigator pasted one."""
    for address in (
        "1CRLGcaXajtWVF5EopZgQUqE12dKn8Rtuh",
        "3GopZWttbQXxFx1QakC2MvXVwFMfRTzCHk",
        "1NDyJtNTjmwk5xPNhjgAMu4HDHigtobu1s",
    ):
        assert is_valid_address(address, Chain.BITCOIN), address


def test_base58_still_rejects_the_ambiguous_glyphs():
    """Base58 exists to drop 0, O, I and l. Widening the class must not
    have let them back in."""
    for bad in ("1CRLGcaXajtW0F5EopZgQUqE12dKn8Rtuh",   # zero
                "1CRLGcaXajtWOF5EopZgQUqE12dKn8Rtuh",   # capital O
                "1CRLGcaXajtWIF5EopZgQUqE12dKn8Rtuh",   # capital I
                "1CRLGcaXajtWlF5EopZgQUqE12dKn8Rtuh"):  # lowercase l
        assert not is_valid_address(bad, Chain.BITCOIN), bad


def test_tron_addresses_are_accepted():
    assert is_valid_address("TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t", Chain.TRON)
    assert is_valid_address("TMuA6YqfCeX8EhbfYEg5y7S4DqzSJireY9", Chain.TRON)


def test_tron_rejects_other_chains_addresses():
    assert not is_valid_address("0xeb2d2f1b8c558a40207669291fda468e50c8a0bb", Chain.TRON)
    assert not is_valid_address("bc1qg24yztysu68rj5vqszpka5cfl04w49h296h8jp", Chain.TRON)
    # Right prefix, wrong length.
    assert not is_valid_address("TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6", Chain.TRON)


def test_tron_addresses_are_not_lowercased():
    """Tron is base58 and case-sensitive - lowercasing one produces a
    different, invalid address."""
    address = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
    assert normalize_address(address) == address
