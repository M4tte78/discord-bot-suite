FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/
RUN pip install --no-cache-dir -e . --no-deps

# Never run a bot as root.
RUN useradd --create-home --uid 10001 bot && chown -R bot:bot /app
USER bot

# Default: the offline simulator, so `docker run` shows something without a token.
# Override with:  docker run --env-file .env <image> python -m botsuite.adapters.discord_adapter.bot
CMD ["python", "-m", "botsuite.sim", "all"]
