
FROM python:3.12-slim-bookworm

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Install Firefox, GeckoDriver, and runtime libraries.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates \
      curl \
      xz-utils \
      fonts-liberation \
      libasound2 \
      libatk1.0-0 \
      libatk-bridge2.0-0 \
      libcairo2 \
      libdbus-1-3 \
      libdrm2 \
      libfontconfig1 \
      libfreetype6 \
      libgbm1 \
      libglib2.0-0 \
      libgtk-3-0 \
      libnspr4 \
      libnss3 \
      libpango-1.0-0 \
      libx11-6 \
      libx11-xcb1 \
      libxcb1 \
      libxcomposite1 \
      libxdamage1 \
      libxext6 \
      libxfixes3 \
      libxrandr2 \
      libxt6 \
    && curl -fsSL --retry 3 \
      'https://download.mozilla.org/?product=firefox-latest&os=linux64&lang=en-US' \
      | tar -xJf - -C /opt \
    && ln -s /opt/firefox/firefox /usr/local/bin/firefox \
    && GECKODRIVER_URL="$(curl -fsSL --retry 3 \
      https://api.github.com/repos/mozilla/geckodriver/releases/latest \
      | python -c 'import json,sys; d=json.load(sys.stdin); print(next(a["browser_download_url"] for a in d["assets"] if a["name"].endswith("linux64.tar.gz")))' )" \
    && curl -fsSL --retry 3 "$GECKODRIVER_URL" \
      | tar -xzf - -C /usr/local/bin geckodriver \
    && chmod +x /usr/local/bin/geckodriver \
    && /usr/local/bin/geckodriver --version \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN useradd --create-home --uid 1000 --shell /usr/sbin/nologin app

WORKDIR /app

COPY requirements/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY src/ /app/src/

RUN mkdir -p /data/firefox-profile \
    && chown -R app:app /app /data

USER app

ENV HOME=/home/app \
    STRAVA_HEADLESS=true \
    STRAVA_FIREFOX_PROFILE=/data/firefox-profile

CMD ["python", "/app/src/app.py"]