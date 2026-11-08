ARG PYTHON_BASE=python:3.14.10-slim-trixie@sha256:af8a5aa14780025dbfbcfbc81bd8a91ebd87711dd5b0f48ed71090949dd7cb1d

FROM ${PYTHON_BASE} AS build
WORKDIR /build
COPY pyproject.toml ./
COPY requirements-ha.lock ./
COPY src/vtherm_assistant/ ./src/vtherm_assistant/
RUN python -m pip install --no-cache-dir --no-compile \
    --constraint requirements-ha.lock --build-constraint requirements-ha.lock . \
    && python -m pip check \
    && mkdir -p /usr/local/share/vtherm-assistant \
    && cp requirements-ha.lock /usr/local/share/vtherm-assistant/ \
    && python -m pip list --format=freeze > /usr/local/share/vtherm-assistant/python.txt \
    && dpkg-query -W > /usr/local/share/vtherm-assistant/debian.txt

FROM ${PYTHON_BASE}
LABEL org.opencontainers.image.version="0.1.2" \
    org.opencontainers.image.source="https://github.com/jmcollin78/vtherm_assistant"
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VTHERM_DEPLOYMENT_MODE=ingress \
    VTHERM_DATA_DIR=/data/vtherm-assistant
COPY --from=build /usr/local /usr/local
USER 0:0
EXPOSE 8099
CMD ["python", "-m", "vtherm_assistant"]