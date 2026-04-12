# Changelog

Toutes les modifications notables de ce projet sont documentées ici.
Format basé sur [Keep a Changelog](https://keepachangelog.com/fr/1.0.0/).

---

## [1.4.0] — 2026-04-13

### UX — Modale d'édition

- **Fenêtre élargie** — la modale "Éditer le fichier" passe de 700 px à 860 px de large (max-height 92 vh) et les listes de pistes gagnent 60 px de hauteur supplémentaire
- **Bouton "Tout décocher"** dans l'onglet CC Sous-titres — apparaît dès qu'au moins une piste est cochée ; disparaît automatiquement quand tout est déjà décoché

### Édition par lot

- **Cases à cocher** sur chaque ligne du tableau de résultats (+ case "Tout sélectionner" dans l'en-tête avec état indéterminé)
- **Barre de sélection** — s'affiche dès que ≥ 2 fichiers sont cochés ; affiche le compteur et un bouton "Éditer la sélection"
- **Mode lot dans la modale** — quand plusieurs fichiers sont sélectionnés, la modale indique "Modifier N fichiers" et utilise le premier fichier comme gabarit de pistes
- **Avertissement contextuel** — banderole dans les onglets Audio et Sous-titres rappelant que les mêmes indices de pistes seront appliqués à tous les fichiers sélectionnés
- **Bouton "+ File ×N"** — remplace les boutons d'application directe en mode lot ; ajoute une tâche en file d'attente pour chacun des N fichiers sélectionnés (audio, sous-titres ou transcodage)
- Conçu pour les séries où tous les épisodes partagent la même structure de pistes

---

## [1.3.0] — 2026-04-07

### Favoris

- **Bouton ☆/★** à côté du champ de chemin — ajoute ou retire le dossier courant des favoris en un clic (étoile dorée = déjà favori)
- **Section "Favoris" dans la sidebar** — liste des dossiers favoris, cliquables pour charger le chemin ; bouton ✕ au survol pour retirer un favori ; section masquée automatiquement si la liste est vide
- **Persistance localStorage** — clé `mst_favorites`, indépendante de l'historique récent (`mst_recent_dirs`)
- **Mise à jour automatique de l'étoile** — l'état du bouton se synchronise dans tous les cas : saisie clavier, browser de dossiers, chips récents, drag & drop

### Lancement

- **Ouverture automatique du navigateur** — `run.sh` ouvre `http://localhost:5000` dans le navigateur par défaut 1,5 s après le démarrage de Flask (`xdg-open` Linux / `open` macOS)

---

## [1.1.0] — 2026-03-26

### Sous-titres

- **Affichage des pistes de sous-titres** — nouvelle colonne dans le tableau principal avec drapeaux de langue et codec (SRT, ASS, PGS, etc.) pour chaque piste
- **Extraction ffprobe** — langue, codec, titre, piste par défaut / forcée pour chaque flux sous-titre
- **Onglet "CC Sous-titres"** dans la modale d'édition — liste interactive des pistes avec les mêmes badges et styles que l'onglet audio
- **Suppression sélective** — possibilité de supprimer certaines ou toutes les pistes de sous-titres (contrairement aux pistes audio, supprimer toutes les pistes est autorisé)

### Édition groupée audio + sous-titres

- **Route `/api/edit/streams`** — nouvelle route backend qui prend `keep_audio` et `keep_subtitle` et exécute une seule passe ffmpeg atomique
- **Bouton "Appliquer" unifié** — depuis n'importe quel onglet (Audio ou Sous-titres), le bouton vérifie les changements en attente dans les **deux** onglets et les applique ensemble en une seule opération
- **Confirmation groupée** — la boîte de dialogue liste explicitement toutes les suppressions audio et sous-titres avant de procéder

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
