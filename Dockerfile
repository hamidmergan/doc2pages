FROM python:3.12-slim

# LibreOffice is not needed, the readers are pure Python. ffmpeg is not needed either.
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir ".[ui]" \
    && useradd --create-home --uid 1000 app

USER app
EXPOSE 8000

# The web UI: drop material in the browser, get a learning page back.
# Settings come from DOC2PAGES_* environment variables, for example DOC2PAGES_BASE_URL
# and DOC2PAGES_MODEL, or from the fields on the page.
CMD ["doc2pages", "serve", "--host", "0.0.0.0", "--port", "8000"]
