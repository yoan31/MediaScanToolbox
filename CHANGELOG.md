# Changelog

Toutes les modifications notables de ce projet sont documentées ici.
Format basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/).

---

## [1.0.0] — 2026-03-25

### Fonctionnalités de base

- **Scan de dossier** — découverte récursive des fichiers vidéo (`.mkv`, `.mp4`, `.avi`, `.mov`, `.m4v`, `.webm`)
- **Analyse ffprobe** — extraction du codec vidéo, résolution, débit, durée, taille et pistes audio
- **Classification automatique** — fichiers "Optimisés" (HEVC / AV1) vs "À transcoder" (H.264, MPEG-2, etc.)
- **Navigation dossiers** — browser intégré pour parcourir l'arborescence sans saisir le chemin manuellement
- **Statistiques** — total, fichiers optimisés, fichiers à transcoder, taille cumulée
- **Filtres et tri** — filtrage par nom, codec, résolution, statut ; tri sur toutes les colonnes
- **Interface dark mode** — UI vanilla HTML/CSS/JS, pas de framework

### Transcodage

- **Codecs cibles** — HEVC (H.265) via `libx265` ou AV1 via `libsvtav1`
- **Encodage GPU** — support NVIDIA NVENC (`hevc_nvenc`, `av1_nvenc`) détecté automatiquement au démarrage
- **Mode qualité** — CRF (CPU) ou constQP (GPU), preset de vitesse configurable
- **Audio** — copie sans réencodage ou réencodage AAC 192k
- **Estimation de taille** — fourchette calculée à partir du débit source et du CRF cible
- **Mapping intelligent des flux** — exclusion automatique des sous-titres non supportés et des flux `attachment` pour éviter les erreurs ffmpeg
- **Fichier de sortie** — choix entre écraser l'original ou créer un nouveau fichier à côté
  - Mode écrasement : transcodage vers un fichier temporaire, puis remplacement atomique (`os.replace`)
  - Mode nouveau fichier : nommage `original.hevc.mkv` / `original.av1.nvenc.mkv`, auto-incrémenté si le nom existe déjà

### Édition des pistes audio

- **Suppression sélective** — conserver ou supprimer des pistes audio individuelles sans réencodage (stream copy)
- **Taille estimée par piste** — affichage de la taille réelle (via tag MKV `NUMBER_OF_BYTES`) ou estimée (`BPS × durée / 8`) pour chaque piste
- **Métadonnées** — langue, codec, canaux, titre, piste par défaut / forcée

### Progression en temps réel (SSE)

- **Scan progressif** — la découverte des fichiers est instantanée (rglob), puis chaque fichier est sondé dans un thread ; la liste se peuple au fil de l'eau
- **Barre de progression de scan** — affiche `N / total` fichiers, pourcentage et nom du fichier en cours d'analyse
- **Bouton Arrêter** — interruption du scan à tout moment
- **Progression transcodage / édition audio** — barre de progression en temps réel parsée depuis la sortie ffmpeg (`time=HH:MM:SS`)
- **Log ffmpeg** — console défilante affichant la sortie brute de ffmpeg
- **Annulation** — arrêt du processus ffmpeg en cours via `SIGTERM`

### UX modale Éditer

- **Bouton contextuel** — "Annuler" au repos, "⏹ Annuler le traitement" pendant un job, "Fermer" une fois le job terminé (succès, erreur ou annulation)
- **Résultat inline** — affichage de la taille avant/après et de l'économie réalisée directement dans la modale
