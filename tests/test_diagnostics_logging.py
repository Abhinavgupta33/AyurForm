import logging

from utils import diagnostics


def _clear_handlers():
    for handler in list(diagnostics.LOGGER.handlers):
        diagnostics.LOGGER.removeHandler(handler)
        handler.close()


def test_development_file_handler_creation_and_configuration(tmp_path):
    _clear_handlers()
    assert diagnostics.configure_file_logging(log_dir=tmp_path, development=True)
    handler = diagnostics.LOGGER.handlers[0]
    assert handler.maxBytes == 5 * 1024 * 1024
    assert handler.backupCount == 3
    diagnostics.LOGGER.info("correlation=abc safe diagnostic")
    handler.flush()
    assert (tmp_path / "rag_diagnostics.log").exists()
    _clear_handlers()


def test_duplicate_handlers_are_prevented(tmp_path):
    _clear_handlers()
    diagnostics.configure_file_logging(log_dir=tmp_path, development=True)
    diagnostics.configure_file_logging(log_dir=tmp_path, development=True)
    assert len(diagnostics.LOGGER.handlers) == 1
    _clear_handlers()


def test_production_does_not_install_file_handler(tmp_path):
    _clear_handlers()
    assert diagnostics.configure_file_logging(log_dir=tmp_path, development=False) is False
    assert not diagnostics.LOGGER.handlers


def test_sensitive_values_are_redacted(tmp_path):
    _clear_handlers()
    diagnostics.configure_file_logging(log_dir=tmp_path, development=True)
    diagnostics.LOGGER.warning("password=secret token=abc cookie=xyz")
    handler = diagnostics.LOGGER.handlers[0]
    handler.flush()
    text = (tmp_path / "rag_diagnostics.log").read_text(encoding="utf-8")
    assert "secret" not in text and "abc" not in text and "xyz" not in text
    assert "[REDACTED]" in text
    _clear_handlers()
