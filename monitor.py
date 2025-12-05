import logging
import subprocess
import threading
from queue import Queue
from typing import override

import pydantic
from prometheus_client import Counter
from pydantic_settings import BaseSettings, SettingsConfigDict

import models


class Settings(BaseSettings):
    model_config: SettingsConfigDict = SettingsConfigDict(env_prefix="METERREADER_")
    rtl_tcp_address: str = "127.0.0.1:1234"
    rtlamr_path: str = "rtlamr"


SETTINGS = Settings()
INVALID_READINGS = Counter(
    "rtlamr_invalid_reading_count", "Invalid readings received from rtlamr"
)
VALID_READINGS = Counter(
    "rtlamr_valid_reading_count", "Valid readings received from rtlamr"
)
LOG = logging.getLogger("__name__")


class Monitor(threading.Thread):
    """Monitor spawns rtlamr as a subprocess, reads messages, parses them into
    models.Reading instances, and then returns them to callers via the iterator
    protocol"""

    rtl_tcp_address: str
    rtlamr_path: str
    readings: Queue[models.Reading]

    def __init__(
        self, rtl_tcp_address: str | None = None, rtlamr_path: str | None = None
    ):
        super().__init__(daemon=True)

        self.rtl_tcp_address = rtl_tcp_address or SETTINGS.rtl_tcp_address
        self.rtlamr_path = rtlamr_path or SETTINGS.rtlamr_path
        self.readings = Queue()

    def __iter__(self):
        return self

    def __next__(self):
        reading = self.readings.get(block=True)
        return reading

    @override
    def run(self):
        LOG.info("start reading from rtl_tcp @ %s", self.rtl_tcp_address)
        p = subprocess.Popen(
            [
                self.rtlamr_path,
                "-msgtype=scm,scm+",
                "-format=json",
                f"-server={self.rtl_tcp_address}",
            ],
            stdout=subprocess.PIPE,
        )

        if p.stdout is None:
            return

        try:
            line: bytes
            for line in p.stdout:
                try:
                    reading = models.Reading.model_validate_json(line)
                except pydantic.ValidationError:
                    INVALID_READINGS.inc()
                    continue
                else:
                    VALID_READINGS.inc()

                self.readings.put(reading)
        finally:
            LOG.warning("rtlamr has stopped")
            self.readings.shutdown()
