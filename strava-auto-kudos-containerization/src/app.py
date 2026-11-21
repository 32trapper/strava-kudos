import os

from dotenv import load_dotenv

from strava_controller import StravaController
from feed_watcher import StravaFeedWatcher


def main():
    print("Starting strava-auto-kudos...")

    load_dotenv()

    # Preserve the previous interactive default for host runs; Compose sets
    # STRAVA_HEADLESS=true for unattended container operation.
    headless = os.getenv("STRAVA_HEADLESS", "false").lower() in (
        "true", "1", "yes"
    )
    controller = StravaController(headless=headless)

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