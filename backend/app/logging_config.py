import logging

from pythonjsonlogger.json import JsonFormatter

from app.config import get_settings


class RedactFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        secret = get_settings().openrouter_api_key
        if not secret:
            return True
        message = record.getMessage()
        if secret in message:
            record.msg = message.replace(secret, "[redacted]")
            record.args = ()
        return True


def configure_logging() -> None:
    settings = get_settings()
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.addFilter(RedactFilter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(settings.log_level.upper())
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("neo4j").setLevel(logging.WARNING)
