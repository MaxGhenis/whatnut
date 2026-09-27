#!/usr/bin/env bash
# Install the Quarto CLI into /tmp/quarto during Vercel's install step (kept
# out of vercel.json because installCommand is capped at 256 characters).
#
# The build needs no Python: paper/index.qmd is committed already filled, and
# Quarto renders it without executing anything.
set -euo pipefail

QUARTO_VERSION="${QUARTO_VERSION:-1.9.37}"

curl --fail --silent --show-error --location \
  --output /tmp/quarto.tar.gz \
  "https://github.com/quarto-dev/quarto-cli/releases/download/v${QUARTO_VERSION}/quarto-${QUARTO_VERSION}-linux-amd64.tar.gz"
mkdir -p /tmp/quarto
tar -xzf /tmp/quarto.tar.gz -C /tmp/quarto --strip-components=1
/tmp/quarto/bin/quarto --version
