# pyright: reportUnusedCallResult=false

import logging
import argparse
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


class ArgsNamespace(argparse.Namespace):
    verbose: int = 0
    rtl_tcp_address: str = ""


class Settings(BaseSettings):
    model_config: SettingsConfigDict = SettingsConfigDict(env_prefix="METERREADER_")
    rtl_tcp_address: str = "127.0.0.1:1234"


class MeterReader(Collector):
    rtl_tcp_address: str
    readings: dict[int, Reading]
    lock: threading.Lock
    reader_thread: threading.Thread
    metric_valid_reading_count: Counter
    metric_invalid_reading_count: Counter

    def __init__(self, rtl_tcp_address: str | None = None):
        self.rtl_tcp_address = rtl_tcp_address or SETTINGS.rtl_tcp_address
        self.readings = {}
        self.lock = threading.Lock()

        self.metric_invalid_reading_count = Counter(
            "rtlamr_invalid_reading_count", "Invalid messages received from rtlamr"
        )
        self.metric_valid_reading_count = Counter(
            "rtlamr_valid_reading_count", "Valid messages received from rtlamr"
        )

        # Start reader thread
        self.reader_thread = threading.Thread(target=self.reader)
        self.reader_thread.start()

    def reader(self):
        LOG.info("using rtl_tcp service at %s", self.rtl_tcp_address)
        p = subprocess.Popen(
            [
                "rtlamr",
                "-msgtype=scm,scm+,idm,netidm",
                "-format=json",
                f"-server={self.rtl_tcp_address}",
            ],
            stdout=subprocess.PIPE,
        )

        if p.stdout is None:
            return

        line: bytes
        for line in p.stdout:
            LOG.debug("message: %s", line)
            try:
                reading = Reading.model_validate_json(line)
            except pydantic.ValidationError:
                self.metric_invalid_reading_count.inc()
                LOG.warning("failed to validate: %s", line)
                continue

            self.metric_valid_reading_count.inc()
            with self.lock:
                self.readings[reading.Message.ID] = reading

    @override
    def collect(self):
        metric_consumption = CounterMetricFamily(
            "consumption", "Energy consumed", labels=["meterid", "metertype"]
        )
        with self.lock:
            for reading in self.readings.values():
                metric_consumption.add_metric(
                    [str(reading.Message.ID), str(reading.Message.Type)],
                    reading.Message.Consumption,
                )

        yield metric_consumption


SETTINGS = Settings()
LOG = logging.getLogger("meterreader")


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--verbose", "-v", action="count")
    p.add_argument("--rtl-tcp-address", "-a", help="<address:port> for rtl_tcp service")
    return p.parse_args(namespace=ArgsNamespace)


def main():
    args = parse_args()
    loglevel = next(
        (x for i, x in enumerate(["WARNING", "INFO", "DEBUG"]) if i == args.verbose),
        "DEBUG",
    )
    logging.basicConfig(level=loglevel)
    REGISTRY.register(MeterReader(rtl_tcp_address=args.rtl_tcp_address))
    _, t = start_http_server(9000)
    t.join()


if __name__ == "__main__":
    main()
