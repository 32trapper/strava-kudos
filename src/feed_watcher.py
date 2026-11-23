import os
import re
import json
import time
from pathlib import Path

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


class StravaFeedWatcher:
    def __init__(self, controller):
        self.controller = controller
        self.driver = controller.driver

        self.poll_interval = int(
            os.getenv("STRAVA_POLL_INTERVAL", "300")
        )

        self.auto_comment = (
            os.getenv(
                "STRAVA_AUTO_COMMENT",
                "false",
            ).lower()
            == "true"
        )

        self.my_athlete_id = os.getenv(
            "STRAVA_ATHLETE_ID",
            "128175714",
        )

        self.state_file = Path(
            os.getenv(
                "STRAVA_STATE_FILE",
                "strava_processed.json",
            )
        )

        self.processed = self._load_state()

    # ---------------------------------------------------------
    # State
    # ---------------------------------------------------------

    def _load_state(self):
        if not self.state_file.exists():
            return set()

        try:
            with self.state_file.open(
                "r",
                encoding="utf-8",
            ) as file:
                data = json.load(file)

            return set(str(x) for x in data)

        except Exception as error:
            print(
                f"Could not load state file: {error}"
            )
            return set()

    def _save_state(self):
        try:
            with self.state_file.open(
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    sorted(self.processed),
                    file,
                    indent=2,
                )

        except Exception as error:
            print(
                f"Could not save state file: {error}"
            )

    # ---------------------------------------------------------
    # Feed
    # ---------------------------------------------------------

    def open_following_feed(self):
        print("Opening Strava Following feed...")

        self.driver.get(
            "https://www.strava.com/dashboard"
            "?feed_type=following"
        )

        WebDriverWait(
            self.driver,
            20,
        ).until(
            EC.presence_of_element_located(
                (By.TAG_NAME, "body")
            )
        )

        time.sleep(3)

    def find_activity_ids(self):
        links = self.driver.find_elements(
            By.CSS_SELECTOR,
            "a[href*='/activities/']",
        )

        activities = []
        seen = set()

        print("\n--- ACTIVITIES FOUND ---")

        for link in links:
            try:
                href = link.get_attribute("href")
                if not href:
                    continue

                match = re.search(r"/activities/(\d+)", href)
                if not match:
                    continue

                activity_id = match.group(1)

                if activity_id in seen:
                    continue

                seen.add(activity_id)

                owner_id = None
                owner_name = None

                # Walk upward looking for the activity's card/container.
                element = link

                for _ in range(12):
                    try:
                        element = element.find_element(By.XPATH, "..")
                    except Exception:
                        break

                    # Look for athlete links INSIDE this activity card.
                    athlete_links = element.find_elements(
                        By.CSS_SELECTOR,
                        "a[href*='/athletes/']",
                    )

                    for athlete_link in athlete_links:
                        athlete_href = athlete_link.get_attribute("href")

                        if not athlete_href:
                            continue

                        athlete_match = re.search(
                            r"/athletes/(\d+)",
                            athlete_href,
                        )

                        if not athlete_match:
                            continue

                        candidate_id = athlete_match.group(1)

                        # Ignore navigation/profile links that aren't
                        # associated with this activity card.
                        if candidate_id == self.my_athlete_id:
                            owner_id = candidate_id

                            try:
                                name_element = element.find_element(
                                    By.CSS_SELECTOR,
                                    "[data-testid='dashboard-athlete-name']",
                                )
                                owner_name = name_element.text.strip()
                            except Exception:
                                owner_name = "Nathan Phillips"

                            break

                        # For someone else's activity, get their name
                        # from the athlete link itself.
                        try:
                            candidate_name = athlete_link.text.strip()
                        except Exception:
                            candidate_name = ""

                        if candidate_name:
                            owner_id = candidate_id
                            owner_name = candidate_name
                            break

                    if owner_id:
                        break

                activities.append({
                    "id": activity_id,
                    "owner_id": owner_id,
                    "owner_name": owner_name,
                })

                print(
                    f"Activity {activity_id} | "
                    f"Owner: {owner_id} | {owner_name}"
                )

            except Exception as error:
                print(f"Activity parsing error: {error}")

        return activities

    # ---------------------------------------------------------
    # Processing
    # ---------------------------------------------------------

    def process_activity(
        self,
        activity_id,
        owner_id,
        owner_name,
    ):
        activity_id = str(activity_id)
        owner_id = str(owner_id) if owner_id else None

        if activity_id in self.processed:
            return

        print("")
        print(
            f"Activity {activity_id}"
        )
        print(
            f"Owner: {owner_name or 'Unknown'} "
            f"({owner_id or 'Unknown'})"
        )

        # Safety first.
        # If we can't determine the owner, don't interact.
        if not owner_id:
            print(
                "Could not determine activity owner. "
                "Skipping for safety."
            )
            return

        # Skip our own activities.
        if owner_id == self.my_athlete_id:
            print("→ YOUR ACTIVITY — SKIP")
            self.processed.add(activity_id)
            self._save_state()
            return

        print(
            f"→ OTHER ATHLETE — GIVING KUDOS"
        )
        try:
            result = self.controller.give_kudos(
                int(activity_id)
            )

            if result in (None, False):
                print(
                    f"Could not give kudos to "
                    f"activity {activity_id}."
                )
                return

            if result == "already_given":
                print(
                    f"→ Already gave kudos to "
                    f"activity {activity_id}."
                )
                return

            print(
                f"✓ Kudos given to {owner_name}'s "
                f"activity {activity_id}."
            )

            if self.auto_comment:
                from comments import fetch_random_comment

                comment = fetch_random_comment()

                if comment:
                    print(
                        f"Posting comment on "
                        f"{activity_id}..."
                    )

                    comment_result = (
                        self.controller.post_comment(
                            int(activity_id),
                            comment,
                        )
                    )

                    if comment_result:
                        print("✓ Comment posted.")
                    else:
                        print("Could not post comment.")

            self.processed.add(activity_id)
            self._save_state()

        except Exception as error:
            print(
                f"Error processing activity "
                f"{activity_id}: {error}"
            )

    # ---------------------------------------------------------
    # Determine activity owner
    # ---------------------------------------------------------

    def is_my_activity(self, activity_id):
        """
        Open the activity and inspect the athlete profile
        link to determine who owns it.
        """

        self.driver.get(
            f"https://www.strava.com/activities/"
            f"{activity_id}"
        )

        WebDriverWait(
            self.driver,
            15,
        ).until(
            EC.presence_of_element_located(
                (By.TAG_NAME, "body")
            )
        )

        time.sleep(1)

        athlete_links = self.driver.find_elements(
            By.CSS_SELECTOR,
            "a[href*='/athletes/']",
        )

        for link in athlete_links:
            try:
                href = link.get_attribute("href")

                if not href:
                    continue

                match = re.search(
                    r"/athletes/(\d+)",
                    href,
                )

                if match:
                    athlete_id = match.group(1)

                    return (
                        athlete_id
                        == self.my_athlete_id
                    )

            except Exception:
                continue

        print(
            f"WARNING: Could not determine owner "
            f"of activity {activity_id}."
        )

        # Safety first: if we can't determine who owns
        # the activity, don't interact with it.
        return True

    # ---------------------------------------------------------
    # One polling pass
    # ---------------------------------------------------------

    def check_once(self):
        print("")
        print("=" * 60)
        print(
            "Checking Strava feed..."
        )
        print("=" * 60)

        self.open_following_feed()

        activities = self.find_activity_ids()

        print(
            f"Found {len(activities)} "
            "activities in feed."
        )

        for activity in activities:
            self.process_activity(
                activity["id"],
                activity["owner_id"],
                activity["owner_name"],
            )

    # ---------------------------------------------------------
    # Main loop
    # ---------------------------------------------------------

    def run(self):
        print(
            "Starting Strava feed watcher."
        )

        print(
            f"Polling every "
            f"{self.poll_interval} seconds."
        )

        print(
            f"Automatic comments: "
            f"{self.auto_comment}"
        )

        while True:
            try:
                self.check_once()

            except KeyboardInterrupt:
                print(
                    "Stopping Strava feed watcher."
                )
                break

            except Exception as error:
                print(
                    f"Feed watcher error: {error}"
                )

            print(
                f"Sleeping for "
                f"{self.poll_interval} seconds..."
            )

            time.sleep(
                self.poll_interval
            )