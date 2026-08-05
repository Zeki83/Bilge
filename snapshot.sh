#!/usr/bin/env bash

set -euo pipefail

cd ~/Bilge

MESSAGE="${*:-Bilge snapshot}"

echo
echo "Bilge snapshot starten..."
echo

git add .

if git diff --cached --quiet; then
    echo "Geen nieuwe wijzigingen om op te slaan."
else
    git commit -m "$MESSAGE"
fi

git push origin main

echo
echo "Snapshot voltooid en naar GitHub gestuurd."
