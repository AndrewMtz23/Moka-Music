FROM python:3.11-slim-bookworm

LABEL org.opencontainers.image.source="https://github.com/AndrewMtz23/Moka-Music" \
      org.opencontainers.image.description="MokaMusic development environment" \
      org.opencontainers.image.licenses="MIT"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/opt/venv \
    PATH="/opt/venv/bin:$PATH"

RUN apt-get update && apt-get install -y --no-install-recommends \
        ca-certificates git sudo tk libgl1 libglib2.0-0 libasound2 \
        libpulse0 ffmpeg xvfb xauth fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash --uid 1000 vscode \
    && echo 'vscode ALL=(root) NOPASSWD:ALL' > /etc/sudoers.d/vscode \
    && chmod 0440 /etc/sudoers.d/vscode \
    && python -m venv /opt/venv

COPY requirements.txt requirements-dev.txt /tmp/requirements/
RUN pip install --no-cache-dir -r /tmp/requirements/requirements.txt \
        -r /tmp/requirements/requirements-dev.txt \
    && chown -R vscode:vscode /opt/venv \
    && mkdir -p /workspace && chown vscode:vscode /workspace

USER vscode
WORKDIR /workspace
CMD ["bash"]
