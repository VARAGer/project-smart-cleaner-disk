import config


def test_config_has_no_legacy_provider_settings():
    legacy_provider_symbol = "AI" + "_" + "PROVIDER"
    legacy_url_symbol = "G" + "ROQ" + "_" + "API_URL"

    assert not hasattr(config, legacy_provider_symbol)
    assert not hasattr(config, legacy_url_symbol)
