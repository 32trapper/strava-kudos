# Running Strava Auto-Kudos in Docker Compose

This container runs the existing Following-feed watcher. It does not use the
older webhook/ngrok workflow described in the original README.

## Before starting

The Compose file expects these files/directories to exist in the project root:

- `.env` — your existing Strava credentials and settings (never bake this into
  the image or commit it to Git).
- `firefox-profile/` — the persistent Firefox profile used by Selenium.
- `strava_processed.json` and `state.json` — both are mounted so existing
  state is retained. The watcher uses `STRAVA_STATE_FILE` if set in `.env`,
  otherwise it defaults to `strava_processed.json`.

The profile must not be open in another Firefox process while the container is
using it. Back it up before the first container run.

## Build and start

From the project root (the directory containing `src/`, `requirements/`, and
`.env`):

```bash
docker compose up -d --build
```

Follow startup and authentication logs:

```bash
docker compose logs -f strava-auto-kudos
```

Check whether it is running:

```bash
docker compose ps
```

Stop it:

```bash
docker compose down
```

The container restarts automatically after a host/container restart because
`restart: unless-stopped` is configured.

## First login / MFA

The container runs Firefox headlessly. This works when the mounted
`firefox-profile/` already contains a valid Strava session. If Strava expires
the session or requests MFA, authenticate interactively on the host using the
same project and profile:

1. Stop the container: `docker compose down`.
2. Activate the existing virtual environment and run the app on the host with
   `STRAVA_HEADLESS=false` (the updated `app.py` now honors this setting):

   ```bash
   source venv/bin/activate
   STRAVA_HEADLESS=false python src/app.py
   ```

3. Complete Strava login/MFA in the Firefox window.
4. Stop the host app with `Ctrl+C` after authentication succeeds.
5. Start the container again: `docker compose up -d`.

Do not run the host app and container simultaneously against the same Firefox
profile.

## Configuration

The existing `.env` is loaded by Compose and passed into the container. Keep
settings such as `STRAVA_ATHLETE_ID`, `STRAVA_POLL_INTERVAL`, and
`STRAVA_AUTO_COMMENT` there. `STRAVA_HEADLESS` and
`STRAVA_FIREFOX_PROFILE` are intentionally overridden by Compose for
container operation.

The application uses `STRAVA_STATE_FILE` from `.env` if present. Relative
state-file paths are resolved from `/data` in the container. The two state
files shown above are mounted there.

## Notes

- Firefox and the Python dependencies are installed in the image.
- `webdriver_manager` downloads/caches GeckoDriver when Selenium first starts;
  the container therefore needs outbound internet access on first startup.
- Logs are written to stdout/stderr and are available with `docker compose
  logs`.
- Do not add `.env`, Firefox profile contents, or state files to the image.
