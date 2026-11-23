from src.strava_controller import StravaController

controller = StravaController(headless=False)

try:
    controller.login()
    print("\nStrava authentication completed.")
    input("Press Enter to close Firefox...")
finally:
    controller.close()
