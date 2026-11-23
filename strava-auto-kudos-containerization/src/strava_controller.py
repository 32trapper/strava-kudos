import os
import sys
import time
from pathlib import Path

from dotenv import dotenv_values
from selenium import webdriver
from selenium.common.exceptions import (
    ElementClickInterceptedException,
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


class StravaController:
    def __init__(self, headless=None) -> None:

        self.secrets = {**dotenv_values(".env"), **os.environ}

        # ---------------------------------------------------------
        # Persistent Firefox profile
        # ---------------------------------------------------------

        project_dir = Path(__file__).resolve().parent.parent

        self.firefox_profile = Path(
            os.getenv(
                "STRAVA_FIREFOX_PROFILE",
                str(project_dir / "firefox-profile"),
            )
        )

        self.firefox_profile.mkdir(
            parents=True,
            exist_ok=True,
        )

        # ---------------------------------------------------------
        # Headless setting
        # ---------------------------------------------------------

        if headless is None:
            headless = (
                self.secrets.get(
                    "STRAVA_HEADLESS",
                    "true",
                ).lower()
                in ("true", "1", "yes")
            )

        self.headless = headless

        # ---------------------------------------------------------
        # Firefox
        # ---------------------------------------------------------

        options = Options()

        if self.headless:
            options.add_argument("--headless")

        options.add_argument("--no-remote")
        options.add_argument("--disable-gpu")

        # IMPORTANT:
        # Use the profile directly instead of options.profile.
        options.add_argument("-profile")
        options.add_argument(str(self.firefox_profile))

        # Disable unnecessary notifications.
        options.set_preference(
            "dom.webnotifications.enabled",
            False,
        )

        options.set_preference(
            "media.volume_scale",
            "0.0",
        )

        executable = "/usr/local/bin/geckodriver"

        print(f"Firefox profile: {self.firefox_profile}", flush=True)
        print(f"GeckoDriver: {executable}", flush=True)
        print(f"Headless: {self.headless}", flush=True)

        service = Service(
            executable_path=executable,
            service_args=["--log", "debug"],
            log_output=sys.stdout,
        )

        self.driver = webdriver.Firefox(
            service=service,
            options=options,
        )

        self.wait = WebDriverWait(
            self.driver,
            20,
        )

        print(
            "Firefox started with persistent profile:"
        )
        print(
            f"  {self.firefox_profile}"
        )

    # -------------------------------------------------------------
    # Browser cleanup
    # -------------------------------------------------------------

    def close(self) -> None:
        """Close Firefox safely."""

        try:
            self.driver.quit()
        except Exception:
            pass

    # -------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------

    def _find_visible_element(
        self,
        selectors,
        timeout=20,
    ):
        """
        Try multiple selectors and return the first visible element.
        """

        end_time = time.time() + timeout

        while time.time() < end_time:

            for by, selector in selectors:

                try:

                    elements = self.driver.find_elements(
                        by,
                        selector,
                    )

                    for element in elements:

                        try:

                            if element.is_displayed():
                                return element

                        except Exception:
                            continue

                except Exception:
                    continue

            time.sleep(0.5)

        raise NoSuchElementException(
            "Could not find a visible element."
        )

    def _click_element(self, element) -> None:
        """
        Scroll an element into view and click it.
        """
        self.driver.execute_script(
            """
            arguments[0].scrollIntoView({
                behavior: 'instant',
                block: 'center'
            });
            """,
            element,
        )

        time.sleep(0.5)

        try:
            element.click()

        except ElementClickInterceptedException:

            self.driver.execute_script(
                "arguments[0].click();",
                element,
            )

    def _handle_cookie_consent(self, timeout=8) -> None:
        """
        Accept Strava's Cookiebot consent dialog if it appears.
        """
        print("Checking for cookie consent dialog...")

        dialog_selector = "#CybotCookiebotDialog"

        accept_selectors = [
            (By.CSS_SELECTOR, "#CybotCookiebotDialogBodyLevelButtonLevelOptinAllowAll"),
            (By.CSS_SELECTOR, "#CybotCookiebotDialogBodyButtonAccept"),
        ]

        end_time = time.time() + timeout

        while time.time() < end_time:
            try:
                dialogs = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    dialog_selector,
                )

                visible_dialog = any(
                    dialog.is_displayed()
                    for dialog in dialogs
                )

                if not visible_dialog:
                    time.sleep(0.5)
                    continue

                print("Cookie consent dialog detected.")

                for by, selector in accept_selectors:
                    buttons = self.driver.find_elements(by, selector)

                    for button in buttons:
                        if button.is_displayed() and button.is_enabled():
                            self._click_element(button)

                            print("Cookie consent accepted.")

                            WebDriverWait(self.driver, 10).until(
                                lambda driver: not any(
                                    dialog.is_displayed()
                                    for dialog in driver.find_elements(
                                        By.CSS_SELECTOR,
                                        dialog_selector,
                                    )
                                )
                            )

                            return

                print("Cookie dialog visible, but accept button not found.")
                break

            except StaleElementReferenceException:
                continue

            except Exception as exc:
                print(f"Cookie consent handling warning: {exc}")
                break

        print("No actionable cookie consent dialog found.")

    def _save_screenshot(self, filename) -> None:
        """
        Save a screenshot in the project directory.
        """

        path = (
            Path(__file__).resolve().parent.parent
            / filename
        )

        try:

            self.driver.save_screenshot(
                str(path)
            )

            print(
                f"Screenshot saved to: {path}"
            )

        except Exception as e:

            print(
                f"Could not save screenshot: {e}"
            )

    # -------------------------------------------------------------
    # Authentication detection
    # -------------------------------------------------------------

    def _is_logged_in(self) -> bool:
        """
        Determine whether the current Firefox session appears
        to be authenticated with Strava.
        """

        try:

            url = self.driver.current_url.lower()

        except Exception:

            return False

        if "/login" in url:
            return False

        if "strava.com" not in url:
            return False

        # Look for common authenticated-page elements.
        selectors = [
            (
                By.CSS_SELECTOR,
                'a[href="/dashboard"]',
            ),
            (
                By.CSS_SELECTOR,
                'a[href*="/athletes/"]',
            ),
            (
                By.CSS_SELECTOR,
                '[data-testid="user-menu"]',
            ),
            (
                By.CSS_SELECTOR,
                '[data-cy="user-menu"]',
            ),
        ]

        for by, selector in selectors:

            try:

                elements = self.driver.find_elements(
                    by,
                    selector,
                )

                if any(
                    element.is_displayed()
                    for element in elements
                ):
                    return True

            except Exception:
                pass

        return False

    # -------------------------------------------------------------
    # Manual MFA handling
    # -------------------------------------------------------------

    def _wait_for_manual_authentication(
        self,
        timeout=300,
    ) -> None:
        """
        Wait for the user to complete MFA/authentication manually.

        The bot does NOT read or bypass MFA.
        """

        if self.headless:

            raise RuntimeError(
                "Strava requires additional authentication/MFA, "
                "but Firefox is running headless. "
                "Set STRAVA_HEADLESS=false and run again."
            )

        print()
        print("=" * 65)
        print("STRAVA AUTHENTICATION REQUIRED")
        print("=" * 65)
        print(
            "Complete the Strava login/MFA process in Firefox."
        )
        print(
            "The bot will continue automatically after "
            "authentication succeeds."
        )
        print("=" * 65)
        print()

        end_time = time.time() + timeout

        while time.time() < end_time:

            try:

                if self._is_logged_in():

                    print(
                        "Strava authentication successful."
                    )

                    time.sleep(2)

                    return

            except Exception:
                pass

            time.sleep(2)

        raise TimeoutException(
            "Timed out waiting for Strava authentication."
        )

    # -------------------------------------------------------------
    # Login
    # -------------------------------------------------------------

    def login(self) -> None:
        """
        Log into Strava using the persistent Firefox profile.

        If the profile already has a valid Strava session,
        no login is performed.

        If Strava requires MFA, the user completes it manually.
        """

        print("Checking existing Strava session...")

        # First try the dashboard.
        self.driver.get(
            "https://www.strava.com/dashboard"
        )

        time.sleep(3)

        if self._is_logged_in():

            print(
                "Already authenticated with Strava."
            )

            return

        print(
            "No active Strava session found."
        )

        print(
            "Opening Strava login page..."
        )

        self.driver.get(
            "https://www.strava.com/login"
        )

        time.sleep(3)

        email = self.secrets.get(
            "STRAVA_EMAIL"
        )

        password = self.secrets.get(
            "STRAVA_PASSWORD"
        )

        if not email:
            raise RuntimeError(
                "STRAVA_EMAIL is missing from .env"
            )

        if not password:
            raise RuntimeError(
                "STRAVA_PASSWORD is missing from .env"
            )


        # ---------------------------------------------------------
        # Cookie consent
        # ---------------------------------------------------------

        self._handle_cookie_consent()

        # ---------------------------------------------------------
        # Email
        # ---------------------------------------------------------

        print(
            "Looking for Strava email field..."
        )

        email_selectors = [
            (
                By.XPATH,
                './/*[@data-cy="email"]',
            ),
            (
                By.CSS_SELECTOR,
                '[data-cy="email"]',
            ),
            (
                By.CSS_SELECTOR,
                'input[type="email"]',
            ),
            (
                By.CSS_SELECTOR,
                'input[name="email"]',
            ),
        ]

        try:

            email_field = (
                self._find_visible_element(
                    email_selectors,
                    timeout=20,
                )
            )

        except NoSuchElementException:

            print(
                "Could not find the Strava email field."
            )

            self._save_screenshot(
                "strava_email_error.png"
            )

            # It may already be an authentication challenge.
            self._wait_for_manual_authentication()

            return

        print(
            "Email field found."
        )

        WebDriverWait(
            self.driver,
            15,
        ).until(
            EC.element_to_be_clickable(email_field)
        )

        self._click_element(email_field)

        email_field.clear()

        email_field.send_keys(email)

        print(
            "Strava email entered."
        )

        email_field.send_keys(Keys.ENTER)

        print(
            "Email submitted."
        )

        # Give Strava time to transition.
        time.sleep(3)

        # ---------------------------------------------------------
        # Password
        # ---------------------------------------------------------

        print(
            "Looking for password field..."
        )

        password_selectors = [
            (
                By.XPATH,
                './/*[@data-cy="password"]',
            ),
            (
                By.CSS_SELECTOR,
                '[data-cy="password"]',
            ),
            (
                By.CSS_SELECTOR,
                'input[type="password"]',
            ),
            (
                By.CSS_SELECTOR,
                'input[name="password"]',
            ),
        ]

        password_field = None

        for by, selector in password_selectors:

            try:

                password_field = (
                    WebDriverWait(
                        self.driver,
                        8,
                    ).until(
                        EC.visibility_of_element_located(
                            (
                                by,
                                selector,
                            )
                        )
                    )
                )

                break

            except TimeoutException:

                continue

        # ---------------------------------------------------------
        # No password field = likely MFA/auth challenge
        # ---------------------------------------------------------

        if password_field is None:

            print(
                "Password field was not found."
            )

            print(
                "Strava may be requesting MFA or "
                "another authentication step."
            )

            self._save_screenshot(
                "strava_authentication_required.png"
            )

            if self._is_logged_in():

                print(
                    "Strava already appears authenticated."
                )

                return

            self._wait_for_manual_authentication()

            return

        # ---------------------------------------------------------
        # Password
        # ---------------------------------------------------------

        print(
            "Password field found."
        )

        password_field.click()

        password_field.clear()

        password_field.send_keys(password)

        print(
            "Strava password entered."
        )

        password_field.send_keys(Keys.ENTER)

        print(
            "Password submitted."
        )

        time.sleep(4)

        # ---------------------------------------------------------
        # MFA / final authentication
        # ---------------------------------------------------------

        if not self._is_logged_in():

            print(
                "Strava has not completed authentication yet."
            )

            self._wait_for_manual_authentication()

        print(
            "Strava login complete."
        )

    # -------------------------------------------------------------
    # Give kudos
    # -------------------------------------------------------------

    def give_kudos(self, activity_id: int):
        """
        Give kudos and verify that Strava registered the action.

        Returns:
            "given"         - Kudos successfully applied and verified.
            "already_given" - Kudos already existed.
            None            - Could not verify kudos.
        """

        activity_url = (
            f"https://www.strava.com/activities/{activity_id}"
        )

        print(f"Opening activity {activity_id}...")

        self.driver.get(activity_url)

        WebDriverWait(self.driver, 20).until(
            EC.presence_of_element_located(
                (By.TAG_NAME, "body")
            )
        )

        time.sleep(3)

        if "/login" in self.driver.current_url:
            print("Strava session expired. Logging in...")
            self.login()
            self.driver.get(activity_url)

            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located(
                    (By.TAG_NAME, "body")
                )
            )

            time.sleep(3)

        # These selectors indicate kudos already exist.
        remove_selectors = [
            (By.CSS_SELECTOR, 'button[title="Remove kudos"]'),
            (By.CSS_SELECTOR, 'button[aria-label="Remove kudos"]'),
            (By.XPATH, "//button[contains(@title, 'Remove kudos')]"),
        ]

        def kudos_confirmed(driver):
            # Current Strava UI: filled kudos icon means we already gave kudos.
            filled_kudos = driver.find_elements(
                By.CSS_SELECTOR,
                '[data-testid="filled_kudos"]'
            )

            for element in filled_kudos:
                try:
                    if element.is_displayed():
                        return True
                except Exception:
                    continue

            # Older Strava UI fallback.
            for by, selector in remove_selectors:
                elements = driver.find_elements(by, selector)

                for element in elements:
                    try:
                        if element.is_displayed():
                            return True
                    except Exception:
                        continue

            return False

        # Check whether we already gave kudos.
        if kudos_confirmed(self.driver):
            print(f"Activity {activity_id} already has your kudos.")
            return "already_given"

        print("Looking for Give kudos button...")

        give_selectors = [
            (By.CSS_SELECTOR, 'button[title="Give kudos"]'),
            (By.CSS_SELECTOR, 'button[aria-label="Give kudos"]'),
            (By.XPATH, "//button[normalize-space()='Give kudos']"),
        ]

        try:
            kudos_button = self._find_visible_element(
                give_selectors,
                timeout=20,
            )

        except NoSuchElementException:
            print("Could not find Give kudos button.")
            self._save_screenshot("strava_kudos_error.png")
            return None

        print(f"Clicking kudos for activity {activity_id}...")

        self._click_element(kudos_button)

        # IMPORTANT: Wait for Strava to confirm the action.
        try:
            WebDriverWait(self.driver, 10).until(
                lambda driver: kudos_confirmed(driver)
            )

            print(
                f"VERIFIED: Kudos successfully given "
                f"to activity {activity_id}."
            )

            return "given"

        except TimeoutException:
            print(
                f"ERROR: Kudos could not be verified "
                f"for activity {activity_id}."
            )

            self._save_screenshot("strava_kudos_error.png")

            return None

    # -------------------------------------------------------------
    # Comment
    # -------------------------------------------------------------

    def post_comment(self, activity_id: int, comment: str) -> bool:
        """Post a comment on a Strava activity."""

        print(f"Opening activity {activity_id} for comment...")

        self.driver.get(
            f"https://www.strava.com/activities/{activity_id}"
        )

        try:
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located(
                    (By.TAG_NAME, "body")
                )
            )

            time.sleep(2)

            print("Looking for comment button...")

            # The comment field is not displayed until the
            # comment button at the top of the activity is clicked.
            comment_button = self._find_visible_element(
                [
                    (
                        By.CSS_SELECTOR,
                        "button[aria-label*='comment' i]",
                    ),
                    (
                        By.CSS_SELECTOR,
                        "button[title*='comment' i]",
                    ),
                    (
                        By.XPATH,
                        "//button[contains("
                        "translate(@aria-label,"
                        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ',"
                        "'abcdefghijklmnopqrstuvwxyz'),"
                        "'comment')]",
                    ),
                    (
                        By.XPATH,
                        "//button[contains("
                        "translate(@title,"
                        "'ABCDEFGHIJKLMNOPQRSTUVWXYZ',"
                        "'abcdefghijklmnopqrstuvwxyz'),"
                        "'comment')]",
                    ),
                ],
                timeout=10,
            )

            print("Clicking comment button...")
            self._click_element(comment_button)

            time.sleep(1)

            print("Looking for comment field...")

            comment_box = self._find_visible_element(
                [
                    (
                        By.CSS_SELECTOR,
                        "textarea",
                    ),
                    (
                        By.CSS_SELECTOR,
                        "[contenteditable='true']",
                    ),
                    (
                        By.CSS_SELECTOR,
                        "[role='textbox']",
                    ),
                    (
                        By.CSS_SELECTOR,
                        "input[placeholder*='comment' i]",
                    ),
                    (
                        By.CSS_SELECTOR,
                        "textarea[placeholder*='comment' i]",
                    ),
                ],
                timeout=15,
            )

            print("Found comment field.")

            self._click_element(comment_box)
            comment_box.send_keys(comment)

            time.sleep(1)

            print("Looking for Post button...")

            post_button = self._find_visible_element(
                [
                    (
                        By.XPATH,
                        "//button[normalize-space()='Post']",
                    ),
                    (
                        By.CSS_SELECTOR,
                        'button[type="submit"]',
                    ),
                ],
                timeout=10,
            )

            print("Clicking Post...")
            self._click_element(post_button)

            time.sleep(2)

            print("Comment posted.")

            return True

        except (NoSuchElementException, TimeoutException) as error:
            print(f"Could not post comment: {error}")
            self._save_screenshot("strava_comment_error.png")
            return False

        except Exception as error:
            print(f"Comment error: {error}")
            self._save_screenshot("strava_comment_error.png")
            return False