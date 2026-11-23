import os

from dotenv import load_dotenv

from strava_controller import StravaController
from feed_watcher import StravaFeedWatcher


def main():
    print("Starting strava-auto-kudos...")

    load_dotenv()

    controller = StravaController(
        headless=True
    )

    watcher = StravaFeedWatcher(
        controller
    )

    try:
        controller.login()

        watcher.run()

    finally:
        controller.close()


if __name__ == "__main__":
    main()