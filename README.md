# Strava Auto-Kudos

Strava Auto-Kudos watches the Strava Following feed and gives kudos to
activities uploaded by other athletes. It can optionally post a random comment
and keeps track of processed activity IDs so it does not interact with the
same activity repeatedly.

The containerized setup uses Firefox and Selenium in Docker. It does not use
the older Strava webhook/ngrok workflow.

## Container files

- `strava-auto-kudos-containerization/Dockerfile` builds the Python, Firefox,
  and GeckoDriver image.
- `strava-auto-kudos-containerization/compose.yaml` starts the application,
  loads environment variables, and mounts persistent state.
- `strava-auto-kudos-containerization/.env` contains container credentials
  and settings.
- `strava-auto-kudos-containerization/authenticate.py` opens Firefox on the
  host for initial login or MFA.
- `strava-auto-kudos-containerization/CONTAINERIZATION.md` contains additional
  container notes.

## Requirements

- Docker with Docker Compose
- A Strava account
- Internet access for image/build downloads and Strava
- Disk space for the Firefox profile and Docker image

## Quick start

1. Create or update the container environment file:

   ```bash
   cp .env strava-auto-kudos-containerization/.env
   ```

   The container setup requires `STRAVA_EMAIL` and `STRAVA_PASSWORD`. It also
   reads `STRAVA_ATHLETE_ID`, `STRAVA_POLL_INTERVAL`,
   `STRAVA_AUTO_COMMENT`, and `STRAVA_STATE_FILE`.

2. Build and start the container:

   ```bash
   docker compose -f strava-auto-kudos-containerization/compose.yaml up -d --build
   ```

3. Follow startup and login output:

   ```bash
   docker compose -f strava-auto-kudos-containerization/compose.yaml logs -f strava-auto-kudos
   ```

4. Check container status:

   ```bash
   docker compose -f strava-auto-kudos-containerization/compose.yaml ps
   ```

5. Stop the container:

   ```bash
   docker compose -f strava-auto-kudos-containerization/compose.yaml down
   ```

## Configuration

Configure these variables in `strava-auto-kudos-containerization/.env`:

| Variable | Default | Description |
| --- | --- | --- |
| `STRAVA_EMAIL` | required | Strava login email |
| `STRAVA_PASSWORD` | required | Strava login password |
| `STRAVA_ATHLETE_ID` | `128175714` | Your athlete ID; activities owned by this athlete are skipped |
| `STRAVA_POLL_INTERVAL` | `300` | Seconds between feed checks |
| `STRAVA_AUTO_COMMENT` | `false` | Set to `true` to post a random comment after kudos |
| `STRAVA_STATE_FILE` | `strava_processed.json` | Processed activity-ID state file |

The Compose file intentionally sets:

- `STRAVA_HEADLESS=true`
- `STRAVA_FIREFOX_PROFILE=/data/firefox-profile`

Do not commit `.env` or the Firefox profile. Both contain private or
authentication-related data.

## Persistent data

Compose mounts these host paths into the container:

| Host path | Container path | Purpose |
| --- | --- | --- |
| `firefox-profile/` | `/data/firefox-profile` | Firefox session, cookies, and profile |
| `strava_processed.json` | `/data/strava_processed.json` | Processed activity IDs |
| `state.json` | `/data/state.json` | Additional application state |

Back up the Firefox profile and state files before major changes. The profile
must not be in use by another Firefox process when the container starts.

## First login or MFA

The container normally starts Firefox in headless mode. Use a host browser for
initial authentication or if Strava requests MFA:

1. Stop the container:

   ```bash
   docker compose -f strava-auto-kudos-containerization/compose.yaml down
   ```

2. Create a Python environment and install dependencies if needed:

   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements/requirements.txt
   ```

3. Run the authentication helper from the container directory:

   ```bash
   cd strava-auto-kudos-containerization
   STRAVA_FIREFOX_PROFILE=../firefox-profile python3 authenticate.py
   ```

4. Complete login or MFA in the Firefox window, then press Enter in the terminal
   to close Firefox.

5. Start the container again:

   ```bash
   cd ..
   docker compose -f strava-auto-kudos-containerization/compose.yaml up -d
   ```

Do not run the host application and container simultaneously against the same
Firefox profile.

## Logs and maintenance

View live logs:

```bash
docker compose -f strava-auto-kudos-containerization/compose.yaml logs -f strava-auto-kudos
```

Rebuild after changing the Dockerfile or application files:

```bash
docker compose -f strava-auto-kudos-containerization/compose.yaml up -d --build
```

Remove the container while preserving mounted profile and state files:

```bash
docker compose -f strava-auto-kudos-containerization/compose.yaml down
```

## Running on the host

The original host setup can still be run with Python:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements/requirements.txt
python3 src/app.py
```

Configure the root `.env` before starting. The host app uses:

- `firefox-profile/` by default
- `strava_processed.json` by default
- `state.json` where used by application code

## Troubleshooting

- **Container exits immediately:** run the logs command and verify
  `STRAVA_EMAIL` and `STRAVA_PASSWORD` in
  `strava-auto-kudos-containerization/.env`.
- **MFA or login challenge:** stop the container and authenticate interactively
  using the host helper described above.
- **Profile lock errors:** stop the container and make sure no other Firefox
  process is using `firefox-profile/`.
- **Your own activities receive kudos:** set `STRAVA_ATHLETE_ID` to the numeric
  athlete ID shown in your Strava athlete URL.
- **GeckoDriver or Firefox failures:** rebuild the image to refresh Firefox,
  GeckoDriver, and Python dependencies.

## Security

Keep `.env` values private. Never bake credentials into `Dockerfile`,
`compose.yaml`, source files, or container images. Restrict access to the
mounted Firefox profile because it contains an authenticated browser session.
