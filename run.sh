#!/bin/bash
# MediaScan - Launcher

echo ""
echo "  MediaScan — Film Codec Scanner"
echo "  ──────────────────────────────"
echo ""

DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

# Vérifier ffprobe
if ! command -v ffprobe &> /dev/null; then
    echo "  [ERREUR] ffprobe introuvable. Installez ffmpeg :"
    echo "    Ubuntu/Debian : sudo apt install ffmpeg"
    echo "    macOS         : brew install ffmpeg"
    exit 1
fi

# Créer le venv si absent
if [ ! -f "venv/bin/python" ]; then
    echo "  [INFO] Création du virtualenv..."
    python3 -m venv venv
fi

# Installer les dépendances si nécessaire
if ! venv/bin/python -c "import flask" &> /dev/null; then
    echo "  [INFO] Installation des dépendances..."
    venv/bin/pip install -r requirements.txt -q
fi

echo "  [OK] ffprobe détecté"
echo "  [OK] virtualenv prêt  ($(venv/bin/python --version))"
echo ""
echo "  → http://localhost:5000"
echo "  Ctrl+C pour arrêter"
echo ""

venv/bin/python app.py
