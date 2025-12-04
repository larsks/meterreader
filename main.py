import logging
import threading
import pydantic
import subprocess
from typing import override
from prometheus_client.core import REGISTRY
from prometheus_client import start_http_server
from prometheus_client.registry import Collector
from prometheus_client.core import CounterMetricFamily
from prometheus_client import Counter
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

from models import Event
from models import Sample


class Settings(BaseSettings):
    model_config: SettingsConfigDict = SettingsConfigDict(env_prefix="METERREADER_")
    rtl_sdr_address: str = "127.0.0.1:1234"


class MeterReader(Collector):
    samples: list[Sample]
    lock: threading.Lock
    reader_thread: threading.Thread
    consumption: CounterMetricFamily

    def __init__(self):
        self.samples = []
        self.lock = threading.Lock()
        self.consumption = CounterMetricFamily(
            "consumption", "Energy consumed", labels=["meterid", "metertype"]
        )
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
                evt = Event.model_validate_json(line)
            except pydantic.ValidationError:
                LOG.warning("failed to validate: %s", line)
                continue

            MESSAGES.inc()
            with self.lock:
                self.samples.append(Sample.from_message(evt))

    @override
    def collect(self):
        with self.lock:
            for sample in self.samples:
                self.consumption.add_metric(
                    [str(sample.ID), str(sample.Type)], sample.Consumption
                )

        yield self.consumption


MESSAGES = Counter("rtlamr_messages", "Messages received from rtlamr")
SETTINGS = Settings()
REGISTRY.register(MeterReader())
LOG = logging.getLogger("meterreader")


def main():
    _, t = start_http_server(9000)
    t.join()


if __name__ == "__main__":
    main()
