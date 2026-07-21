#!/bin/bash
cd "$(dirname "$0")"

if ! command -v uv >/dev/null 2>&1; then
    echo "Instaluje uv (menedzer Pythona), prosze czekac..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

uv run python app.py

echo ""
echo "Forum zostalo zamkniete. Mozesz zamknac to okno."
read -r -p "Nacisnij Enter..."
