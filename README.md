# MediaScan Toolbox

Application web locale pour auditer une vidéothèque et transcoder les fichiers vers des codecs modernes et économes en espace (HEVC / AV1).

## Fonctionnalités

Pointez vers un dossier, et MediaScan Toolbox scannera récursivement tous les fichiers vidéo pour identifier ceux déjà optimisés (HEVC ou AV1) et ceux encore dans des formats anciens (H.264, MPEG-2, etc.) qui gaspillent de l'espace disque.

À partir de là, vous pouvez :

- **Transcoder** n'importe quel fichier en HEVC ou AV1, avec le CPU ou un GPU NVIDIA (NVENC)
- **Éditer les pistes audio** — conserver ou supprimer des pistes individuelles avant ou après le transcodage
- **Éditer les sous-titres** — conserver ou supprimer des pistes de sous-titres individuelles (suppression totale autorisée) ; bouton "Tout décocher" en un clic
- **Combiner les modifications** — les changements audio et sous-titres sont appliqués ensemble en une seule passe ffmpeg
- **Édition par lot** ��� cocher plusieurs fichiers dans le tableau et appliquer les mêmes modifications à tous (idéal pour les séries) ; chaque fichier est ajouté automatiquement à la file d'attente
- **Suivre la progression** en temps réel via une barre de progression live (Server-Sent Events)
- **Annuler** un job en cours à tout moment
- **Gérer des favoris** — épingler des dossiers fréquents dans la sidebar, persistés en localStorage

Chaque fichier scanné affiche son codec, sa résolution, son débit, sa taille, ses pistes audio et ses pistes de sous-titres avec leur langue et codec.

## Prérequis

- Python 3.8+
- [FFmpeg](https://ffmpeg.org/download.html) (fournit `ffprobe` et `ffmpeg`)
- GPU NVIDIA optionnel — active l'encodage matériel accéléré NVENC

## Démarrage rapide

```bash
git clone https://github.com/yourname/mediascan.git
cd mediascan
./run.sh
```

Le navigateur s'ouvre automatiquement. Si ce n'est pas le cas, ouvrez [http://localhost:5000](http://localhost:5000).

`run.sh` crée automatiquement un virtualenv Python et installe les dépendances au premier lancement.

### Installation manuelle

```bash
pip install -r requirements.txt
python app.py
```

## Formats supportés

Entrée : `.mkv` `.mp4` `.avi` `.mov` `.m4v` `.webm`

Sortie : conteneur MKV — `original.hevc.mkv` ou `original.av1.nvenc.mkv` (incrémenté automatiquement si le nom existe déjà)

## Options d'encodage

| Encodeur | Codec | Mode |
|----------|-------|------|
| `libx265` | HEVC (H.265) | CPU — qualité CRF |
| `hevc_nvenc` | HEVC | GPU NVIDIA — constQP |
| `libsvtav1` | AV1 | CPU — qualité CRF |
| `av1_nvenc` | AV1 | GPU NVIDIA — constQP |

## Stack technique

- **Backend** : Python / Flask
- **Frontend** : HTML + CSS + JavaScript vanilla (sans framework)
- **Analyse média** : ffprobe (sortie JSON)
- **Transcodage** : sous-processus ffmpeg avec progression SSE en temps réel

---

# MediaScan Toolbox *(English)*

A local web app to audit a video library and transcode files to modern, space-efficient codecs (HEVC / AV1).

## What it does

Point it at a folder, and MediaScan Toolbox will recursively scan all video files and tell you which ones are already optimized (HEVC or AV1) and which ones are still in older formats (H.264, MPEG-2, etc.) wasting disk space.

From there you can:

- **Transcode** any file to HEVC or AV1, with CPU or NVIDIA GPU (NVENC)
- **Edit audio tracks** — keep or remove individual tracks before or after transcoding
- **Edit subtitle tracks** — keep or remove individual subtitle tracks (removing all is allowed); one-click "Uncheck all" button
- **Combine edits** — audio and subtitle changes are applied together in a single ffmpeg pass
- **Batch editing** — check multiple files in the table and apply the same edits to all of them (ideal for TV series); each file is automatically queued
- **Monitor progress** in real time via a live progress bar (Server-Sent Events)
- **Cancel** a running job at any time
- **Manage favourites** — pin frequently used folders in the sidebar, persisted in localStorage

Each scanned file shows its codec, resolution, bitrate, file size, audio tracks and subtitle tracks with their language and codec.

## Requirements

- Python 3.8+
- [FFmpeg](https://ffmpeg.org/download.html) (provides `ffprobe` and `ffmpeg`)
- NVIDIA GPU optional — enables NVENC hardware-accelerated encoding

## Quick start

```bash
git clone https://github.com/yourname/mediascan.git
cd mediascan
./run.sh
```

The browser opens automatically. If it doesn't, navigate to [http://localhost:5000](http://localhost:5000).

`run.sh` automatically creates a Python virtualenv and installs dependencies on first run.

### Manual setup

```bash
pip install -r requirements.txt
python app.py
```

## Supported formats

Input: `.mkv` `.mp4` `.avi` `.mov` `.m4v` `.webm`

Output: MKV container — `original.hevc.mkv` or `original.av1.nvenc.mkv` (auto-incremented if the name already exists)

## Encoding options

| Encoder | Codec | Mode |
|---------|-------|------|
| `libx265` | HEVC (H.265) | CPU — CRF quality |
| `hevc_nvenc` | HEVC | NVIDIA GPU — constQP |
| `libsvtav1` | AV1 | CPU — CRF quality |
| `av1_nvenc` | AV1 | NVIDIA GPU — constQP |

## Stack

- **Backend**: Python / Flask
- **Frontend**: Vanilla HTML + CSS + JavaScript (no framework)
- **Media analysis**: ffprobe (JSON output)
- **Transcoding**: ffmpeg subprocess with real-time SSE progress
