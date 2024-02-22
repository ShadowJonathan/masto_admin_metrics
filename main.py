import os
import time
from datetime import datetime, timedelta

from mastodon import Mastodon
from prometheus_client import Gauge, start_wsgi_server

ONE_DAY = timedelta(days=1)
SEVEN_DAYS = timedelta(days=7)
THIRTY_DAYS = timedelta(days=30)


class FakeCounter(Gauge):
    _type = "counter"


class CounterMeasure:
    def __init__(self, name):
        self.name = name
        self.c = FakeCounter(f"mastodon_measure_{name}", f"Count of {name} from the last day")

    def update_with_measure(self, count: int):
        self.c.set(count)


class UniqueMeasure:
    def __init__(self, name):
        self.name = name
        self.g_1d = FakeCounter(
            f"mastodon_measure_{name}_unique_1d", f"Unique instances of {name} from the last day"
        )
        self.g_7d = Gauge(
            f"mastodon_measure_{name}_unique_7d", f"Unique instances of {name} from the last 7 days"
        )
        self.g_30d = Gauge(
            f"mastodon_measure_{name}_unique_30d", f"Unique instances of {name} from the last 30 days"
        )

    def update(self, mastodon: Mastodon):
        kw = {self.name: True}

        one_day = mastodon.admin_measures(
            datetime.now() - ONE_DAY, datetime.now(), **kw
        )[0]
        seven_days = mastodon.admin_measures(
            datetime.now() - SEVEN_DAYS, datetime.now(), **kw
        )[0]
        thirty_days = mastodon.admin_measures(
            datetime.now() - THIRTY_DAYS, datetime.now(), **kw
        )[0]

        self.g_1d.set(one_day["total"])
        self.g_7d.set(seven_days["total"])
        self.g_30d.set(thirty_days["total"])


MEASURE_NAMES = {
    # Just a counter, just fetch the last day
    "counter": [
        "interactions",
        "new_users",
        "opened_reports",
        "resolved_reports",
    ],
    # Unique is different, it tracks unique occurrences across the last X period,
    # and so fetching a period will get unique instances of it.
    # We fetch: 1d, 7d, 30d, to tail the gauge for each
    "unique": [
        "active_users",
    ],
}

MEASURES = {
    "counter": {name: CounterMeasure(name) for name in MEASURE_NAMES["counter"]},
    "unique": {name: UniqueMeasure(name) for name in MEASURE_NAMES["unique"]},
}


def update_all(mastodon: Mastodon):
    update_counters(mastodon)

    for unique in MEASURES["unique"].values():
        unique.update(mastodon)


def update_counters(mastodon: Mastodon):
    kw = {name: True for name in MEASURES["counter"].keys()}
    counts = {
        data["key"]: data["total"]
        for data in mastodon.admin_measures(
            datetime.now() - timedelta(hours=24), datetime.now(), **kw
        )
    }

    for name, count in counts.items():
        MEASURES["counter"][name].update_with_measure(count)


def get_mastodon() -> Mastodon:
    BASE_URL = os.environ["MASTODON_BASE_URL"]
    CLIENT_KEY = os.environ["MASTODON_CLIENT_KEY"]
    CLIENT_SECRET = os.environ["MASTODON_CLIENT_SECRET"]
    ACCESS_TOKEN = os.environ["MASTODON_ACCESS_TOKEN"]

    mastodon = Mastodon(
        client_id=CLIENT_KEY,
        client_secret=CLIENT_SECRET,
        access_token=ACCESS_TOKEN,
        api_base_url=BASE_URL
    )

    app_name = mastodon.app_verify_credentials().name
    version = mastodon.retrieve_mastodon_version()

    print(f"Logged into mastodon version {version}, application {app_name}, base URL {mastodon.api_base_url}")

    return mastodon


def main():
    mastodon = get_mastodon()
    update_all(mastodon)

    PORT = os.environ.get("PORT") or 9876

    # Start server only after retrieving all stats for the first time, to prevent set-to-zero contamination
    start_wsgi_server(PORT)

    print(f"Started server on port {PORT}")

    while True:
        time.sleep(30)
        update_all(mastodon)


if __name__ == "__main__":
    main()
