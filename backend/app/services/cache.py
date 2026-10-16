import time


class TtlCache:
    def __init__(self) -> None:
        self._values: dict[str, tuple[float, object]] = {}

    def get(self, key: str):
        item = self._values.get(key)
        if item is None:
            return None
        expires, value = item
        if expires < time.monotonic():
            self._values.pop(key, None)
            return None
        return value

    def set(self, key: str, value: object, ttl_seconds: int = 300) -> None:
        self._values[key] = (time.monotonic() + ttl_seconds, value)

    def clear(self) -> None:
        self._values.clear()


cache = TtlCache()
