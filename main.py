import logging
import pydantic
import threading
import subprocess
from typing import override
from prometheus_client import Counter
from pydantic_settings import BaseSettings
from prometheus_client.core import REGISTRY
from prometheus_client import start_http_server
from prometheus_client.registry import Collector
from pydantic_settings import SettingsConfigDict
from prometheus_client.core import CounterMetricFamily

from models import Reading


class Settings(BaseSettings):
    model_config: SettingsConfigDict = SettingsConfigDict(env_prefix="METERREADER_")
    rtl_sdr_address: str = "127.0.0.1:1234"


class MeterReader(Collector):
    readings: dict[int, Reading]
    lock: threading.Lock
    reader_thread: threading.Thread
    metric_consumption: CounterMetricFamily
    metric_messages: Counter

    def __init__(self):
        self.readings = {}
        self.lock = threading.Lock()

        # Configure metrics
        self.metric_consumption = CounterMetricFamily(
            "consumption", "Energy consumed", labels=["meterid", "metertype"]
        )
        self.metric_messages = Counter("messages", "Messages received from rtlamr")

        # Start reader thread
        self.reader_thread = threading.Thread(target=self.reader)
        self.reader_thread.start()

    def reader(self):
        p = subprocess.Popen(
            [
                "rtlamr",
                "-msgtype=scm,scm+,idm,netidm",
                "-format=json",
                f"-server={SETTINGS.rtl_sdr_address}",
            ],
            stdout=subprocess.PIPE,
        )

        if p.stdout is None:
            return

        line: bytes
        for line in p.stdout:
            try:
                reading = Reading.model_validate_json(line)
            except pydantic.ValidationError:
                LOG.warning("failed to validate: %s", line)
                continue

            self.metric_messages.inc()
            with self.lock:
                self.readings[reading.Message.ID] = reading

    @override
    def collect(self):
        with self.lock:
            for reading in self.readings.values():
                self.metric_consumption.add_metric(
                    [str(reading.Message.ID), str(reading.Message.Type)],
                    reading.Message.Consumption,
                )

        yield self.metric_consumption


SETTINGS = Settings()
REGISTRY.register(MeterReader())
LOG = logging.getLogger("meterreader")


def main():
    _, t = start_http_server(9000)
    t.join()


if __name__ == "__main__":
    main()
