#!/usr/bin/env bash
# Install Python deps + Quarto CLI into /tmp/quarto during Vercel's install
# step. Kept out of vercel.json because installCommand is capped at 256
# characters.
set -euo pipefail

QUARTO_VERSION="${QUARTO_VERSION:-1.9.37}"

pip install --break-system-packages -e ".[docs]"

curl --fail --silent --show-error --location \
  --output /tmp/quarto.tar.gz \
  "https://github.com/quarto-dev/quarto-cli/releases/download/v${QUARTO_VERSION}/quarto-${QUARTO_VERSION}-linux-amd64.tar.gz"
mkdir -p /tmp/quarto
tar -xzf /tmp/quarto.tar.gz -C /tmp/quarto --strip-components=1
