import os
import time
from datetime import datetime, timedelta, date

from mastodon import Mastodon
from prometheus_client import Gauge, Counter, start_wsgi_server

ONE_DAY = timedelta(days=1)
SEVEN_DAYS = timedelta(days=7)
THIRTY_DAYS = timedelta(days=30)


# some sanity functions
def today() -> date:
    return datetime.utcnow().date()


def yesterday() -> date:
    return today() - ONE_DAY


def date_as_utc_datetime(d: date) -> datetime:
    from datetime import timezone

    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


class CounterMeasure:
    def __init__(self, name, today: bool = True):
        self.name = name
        base_name = f"mastodon_measure_{name}"
        self.today = Gauge(
            base_name,
            f"Counter of {name} (so far) for today",
        )
        self.yesterday = Gauge(
            f"{base_name}" + "_yesterday",
            f"Counter of {name} from yesterday",
        )

    def update_with_data(self, data: list[dict]):
        t = None
        y = None

        for day in data:
            date = day["date"].date()
            value = day["value"]

            if date == today():
                t = value
            elif date == yesterday():
                y = value

        assert t is not None, "no data from today"
        assert y is not None, "no data from yesterday"

        self.today.set(t)
        self.yesterday.set(y)


def verify_range(data: list[dict], begin_date: date, end_date: date) -> bool:
    earliest = min(item["date"].date() for item in data)
    latest = max(item["date"].date() for item in data)

    return earliest == begin_date and latest == end_date


class UniqueMeasure:
    def __init__(self, name):
        self.name = name
        base_name = f"mastodon_measure_{name}_unique"
        self.today = Gauge(base_name + "_today", f"Unique instances of {name} (so far) today")
        self.yesterday = Gauge(
            base_name + "_yesterday",
            f"Unique instances of {name} yesterday",
        )
        self.last_7d = Gauge(
            base_name + "_last_7d",
            f"Unique instances of {name} the last 7 days (excluding today)",
        )
        self.last_30d = Gauge(
            base_name + "_last_30d",
            f"Unique instances of {name} the last 30 days (excluding today)",
        )

    def update(self, mastodon: Mastodon):
        self.update_day(mastodon, today(), self.today)
        self.update_day(mastodon, yesterday(), self.yesterday)

        self.update_range(mastodon, yesterday() - SEVEN_DAYS, yesterday(), self.last_7d)
        self.update_range(
            mastodon, yesterday() - THIRTY_DAYS, yesterday(), self.last_30d
        )

    def update_day(self, mastodon: Mastodon, d: date, g: Gauge):
        results = mastodon.admin_measures(
            date_as_utc_datetime(d),
            date_as_utc_datetime(d + ONE_DAY),
            **{self.name: True},
        )

        result = results[0]

        data = result["data"]

        assert len(data) == 1, "measures returned data for more than 1 day"

        item = data[0]

        assert item["date"].date() == d

        g.set(item["value"])

    def update_range(
        self, mastodon: Mastodon, start_date: date, end_date: date, g: Gauge
    ):
        results = mastodon.admin_measures(
            date_as_utc_datetime(start_date),
            date_as_utc_datetime(end_date + ONE_DAY),
            **{self.name: True},
        )

        result = results[0]

        data = result["data"]

        assert verify_range(
            data, start_date, end_date
        ), f"range exceeded; wanted {[start_date, end_date]} {[data[0]['date'], data[-1]['date']]}"

        g.set(result["total"])


MEASURE_NAMES = {
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
        data["key"]: data["data"]
        for data in mastodon.admin_measures(
            # Get a wide range so today and yesterday is definitely included
            date_as_utc_datetime(yesterday()),
            date_as_utc_datetime(today() + ONE_DAY),
            **kw,
        )
    }

    for name, data in counts.items():
        MEASURES["counter"][name].update_with_data(data)


def get_mastodon() -> Mastodon:
    BASE_URL = os.environ["MASTODON_BASE_URL"]
    CLIENT_KEY = os.environ["MASTODON_CLIENT_KEY"]
    CLIENT_SECRET = os.environ["MASTODON_CLIENT_SECRET"]
    ACCESS_TOKEN = os.environ["MASTODON_ACCESS_TOKEN"]

    mastodon = Mastodon(
        client_id=CLIENT_KEY,
        client_secret=CLIENT_SECRET,
        access_token=ACCESS_TOKEN,
        api_base_url=BASE_URL,
        user_agent="Mozilla/5.0 (compatible; masto_admin_metrics; mastodonpy)"
    )

    app_name = mastodon.app_verify_credentials().name
    version = mastodon.retrieve_mastodon_version()

    print(
        f"Logged into mastodon version {version}, application {app_name}, base URL {mastodon.api_base_url}"
    )

    return mastodon


def main():
    m = get_mastodon()
    update_all(m)

    PORT = os.environ.get("PORT", 9876)
    UPDATE_SECS = float(os.environ.get("UPDATE_SECS", 30))

    # Start server only after retrieving all stats for the first time, to prevent set-to-zero contamination
    start_wsgi_server(PORT)

    print(f"Started server on port {PORT}")

    up = Gauge(
        "masto_admin_metrics_up",
        f"Whether the last fetch to the measure endpoint succeeded completely. If 0, is using cached results.",
    )
    up.set(1)

    from mastodon.errors import MastodonServerError, MastodonNetworkError

    while True:
        time.sleep(UPDATE_SECS)
        try:
            update_all(m)
        except MastodonServerError as e:
            print(f"Server error {e!r}, using cached results")
            up.set(0)
        except MastodonNetworkError as e:
            print(f"Network Error {e!r}, using cached results")
            up.set(0)
        else:
            up.set(1)


if __name__ == "__main__":
    main()
