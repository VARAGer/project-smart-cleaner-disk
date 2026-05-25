import logging

from middleware import request_id_var


def test_external_log_records_get_request_id_field():
    import main  # noqa: F401 - importing installs the LogRecordFactory

    token = request_id_var.set("rid-test")
    try:
        record = logging.getLogger("httpx").makeRecord(
            "httpx",
            logging.INFO,
            __file__,
            1,
            'HTTP Request: %s %s "%s %d %s"',
            ("POST", "https://example.test", "HTTP/1.1", 200, "OK"),
            None,
        )
    finally:
        request_id_var.reset(token)

    assert record.request_id == "rid-test"
