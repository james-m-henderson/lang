#!/bin/bash
cd "$(dirname "$0")/../python"
poetry run python tests/harness.py "$@"
