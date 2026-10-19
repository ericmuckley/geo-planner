FROM ghcr.io/valhalla/valhalla@sha256:8d656eb79874acb39359425e470d8326f0e3aab95a88e4a5c294e9dfcea4cda4
RUN apt-get update && apt-get install -y --no-install-recommends \
    osmium-tool=1.16.0-1build1 time=1.9-0.2build1 \
    && rm -rf /var/lib/apt/lists/*
