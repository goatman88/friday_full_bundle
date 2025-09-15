#!/usr/bin/env bash
set -o errexit  # Exit on error

# Always install from root-level requirements.txt
pip install -r requirements.txt
