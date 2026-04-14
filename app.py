import os
import re
import json
import time
import uuid
import subprocess
import threading
from flask import Flask, render_template, request, jsonify, Response, stream_with_context
from pathlib import Path

app = Flask(__name__)

APP_VERSION = "1.2.0-beta"

SUPPORTED_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.mov', '.m4v', '.webm'}

# jobs[job_id] = { 'lines': [...], 'done': bool, 'error': str|None, 'result': dict|None }
jobs = {}
jobs_lock = threading.Lock()

# scan_jobs[job_id] = { 'total': N, 'n': N, 'current': str, 'results': [...], 'errors': [...], 'done': bool, 'cancelled': bool }
scan_jobs = {}
scan_jobs_lock = threading.Lock()

# ── HELPERS ───────────────────────────────────────────────

def format_size(b):
    if b < 1024:        return f"{b} B"
    if b < 1024**2:     return f"{b/1024:.1f} KB"
    if b < 1024**3:     return f"{b/1024**2:.1f} MB"
    return f"{b/1024**3:.2f} GB"

def format_bitrate(s):
    try:
        bps = int(s)
        if bps >= 1_000_000: return f"{bps/1_000_000:.1f} Mb/s"
        if bps >= 1_000:     return f"{bps/1_000:.0f} Kb/s"
        return f"{bps} b/s"
    except (ValueError, TypeError):
        return "N/A"

def res_label_from(width, height):
    """Détecte la vraie catégorie. Seuil 4K: width>=3200 couvre DCI 4K, UHD scope (3832x...)."""
    if width >= 3200 or height >= 2160: return "4K"
    if width >= 1920 or height >= 1080: return "1080p"
    if width >= 1280 or height >= 720:  return "720p"
    if height >= 480:                   return "480p"
    return "SD"

# ── PROBE ─────────────────────────────────────────────────

def probe_file(filepath):
    try:
        cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json',
               '-show_streams', '-show_format', str(filepath)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if r.returncode != 0: return None
        data = json.loads(r.stdout)
    except Exception:
        return None

    video_stream = None
    audio_tracks = []
    audio_streams_detail = []
    subtitle_tracks = []
    subtitle_streams_detail = []

    for stream in data.get('streams', []):
        stype = stream.get('codec_type')
        idx   = stream.get('index', 0)

        if stype == 'video' and video_stream is None:
            video_stream = stream
        elif stype == 'subtitle':
            codec   = stream.get('codec_name', '?').upper()
            lang    = stream.get('tags', {}).get('language', '')
            title   = stream.get('tags', {}).get('title', '')
            default = stream.get('disposition', {}).get('default', 0) == 1
            forced  = stream.get('disposition', {}).get('forced',  0) == 1
            parts   = [codec]
            if lang and lang not in ('und', 'unk', ''): parts.append(lang.upper())
            label = ' '.join(parts)
            subtitle_tracks.append(label)
            subtitle_streams_detail.append({
                'index': idx, 'codec': codec,
                'lang': lang.upper() if lang and lang not in ('und', 'unk', '') else '',
                'title': title, 'default': default, 'forced': forced, 'label': label,
            })
        elif stype == 'audio':
            codec    = stream.get('codec_name', '?').upper()
            lang     = stream.get('tags', {}).get('language', '')
            title    = stream.get('tags', {}).get('title', '')
            channels = stream.get('channels', 0)
            ch_str   = {1:'1.0',2:'2.0',6:'5.1',8:'7.1'}.get(channels, f'{channels}ch') if channels else ''
            default  = stream.get('disposition', {}).get('default', 0) == 1
            forced   = stream.get('disposition', {}).get('forced',  0) == 1
            tags     = stream.get('tags', {})
            # MKV stocke souvent NUMBER_OF_BYTES (exact) ou BPS (bitrate exact) par piste
            nb      = tags.get('NUMBER_OF_BYTES', '')
            bps_tag = tags.get('BPS', '')
            br_raw  = stream.get('bit_rate') or bps_tag or '0'
            br_int  = int(br_raw) if br_raw and str(br_raw).isdigit() else 0
            size_approx = int(nb) if nb and str(nb).isdigit() else None
            parts = [codec]
            if ch_str: parts.append(ch_str)
            if lang and lang not in ('und','unk',''): parts.append(lang.upper())
            label = ' '.join(parts)
            audio_tracks.append(label)
            audio_streams_detail.append({
                'index': idx, 'codec': codec, 'channels': channels,
                'ch_str': ch_str, 'lang': lang.upper() if lang and lang not in ('und','unk','') else '',
                'title': title, 'default': default, 'forced': forced, 'label': label,
                'bitrate_raw': br_int,
                'size_exact':  size_approx,   # int (bytes) si NUMBER_OF_BYTES dispo, sinon None
            })

    if not video_stream: return None

    fmt    = data.get('format', {})
    size_b = os.path.getsize(filepath)
    codec  = video_stream.get('codec_name', 'unknown').upper()
    width  = video_stream.get('width', 0)
    height = video_stream.get('height', 0)
    br_raw = fmt.get('bit_rate', video_stream.get('bit_rate', '0'))
    br_int = int(br_raw) if br_raw and str(br_raw).isdigit() else 0
    dur    = float(fmt.get('duration', 0))
    label  = res_label_from(width, height)
    is_opt = 'HEVC' in codec or 'AV1' in codec or '265' in codec

    return {
        'name':           Path(filepath).name,
        'path':           str(filepath),
        'relative_path':  str(Path(filepath).parent),
        'codec':          codec,
        'audio_codec':       ' · '.join(audio_tracks) if audio_tracks else 'N/A',
        'audio_streams':     audio_streams_detail,
        'subtitle_tracks':   ' · '.join(subtitle_tracks) if subtitle_tracks else '',
        'subtitle_streams':  subtitle_streams_detail,
        'resolution':     f"{width}x{height}" if width and height else "N/A",
        'res_label':      label,
        'width':          width,
        'height':         height,
        'bitrate':        format_bitrate(br_raw),
        'bitrate_raw':    br_int,
        'size':           format_size(size_b),
        'size_raw':       size_b,
        'duration':       f"{int(dur//60)}:{int(dur%60):02d}" if dur > 0 else "N/A",
        'duration_raw':   dur,
        'optimized':      is_opt,
        'status':         'OPTIMISÉ' if is_opt else 'À TRANSCODER',
    }

# ── SCAN ──────────────────────────────────────────────────

def discover_files(directory):
    """Découverte rapide des fichiers vidéo (sans ffprobe)."""
    path = Path(directory)
    if not path.exists() or not path.is_dir():
        return None, f"Chemin invalide : {directory}"
    files = sorted(set(
        f for ext in SUPPORTED_EXTENSIONS
        for f in list(path.rglob(f'*{ext}')) + list(path.rglob(f'*{ext.upper()}'))
    ))
    return files, None

def run_scan_job(job_id, files):
    """Thread : probe chaque fichier et stocke les résultats progressivement."""
    for n, f in enumerate(files, 1):
        with scan_jobs_lock:
            if scan_jobs[job_id].get('cancelled'):
                break
            scan_jobs[job_id]['n']       = n
            scan_jobs[job_id]['current'] = f.name
        info = probe_file(f)
        with scan_jobs_lock:
            if info: scan_jobs[job_id]['results'].append(info)
            else:    scan_jobs[job_id]['errors'].append(str(f))

    with scan_jobs_lock:
        r = scan_jobs[job_id]['results']
        total_size = sum(x['size_raw'] for x in r)
        scan_jobs[job_id]['stats'] = {
            'total':          len(r),
            'optimized':      sum(1 for x in r if x['optimized']),
            'to_transcode':   sum(1 for x in r if not x['optimized']),
            'total_size':     total_size,
            'total_size_fmt': format_size(total_size),
        }
        scan_jobs[job_id]['done'] = True

    # Fix #2 — nettoyer le job de la mémoire après 60 s (#2)
    def _cleanup_scan():
        time.sleep(60)
        with scan_jobs_lock:
            scan_jobs.pop(job_id, None)
    threading.Thread(target=_cleanup_scan, daemon=True).start()

# ── JOB RUNNER (thread) ───────────────────────────────────

def run_ffmpeg_job(job_id, cmd, src, tmp, size_before, duration_sec):
    """Exécute ffmpeg dans un thread, parse la progression, stocke dans jobs[]."""
    def push(line):
        with jobs_lock:
            jobs[job_id]['lines'].append(line)

    push(f"CMD: {' '.join(cmd)}\n")

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        # Stocker le process pour pouvoir l'annuler
        with jobs_lock:
            jobs[job_id]['proc'] = proc

        for line in proc.stdout:
            push(line)
            # Parser la progression ffmpeg : "frame=... time=HH:MM:SS.ss ..."
            if duration_sec > 0:
                m = re.search(r'time=(\d+):(\d+):([\d.]+)', line)
                if m:
                    elapsed = int(m.group(1))*3600 + int(m.group(2))*60 + float(m.group(3))
                    pct = min(99, int(elapsed / duration_sec * 100))
                    with jobs_lock:
                        jobs[job_id]['progress'] = pct

        proc.wait()

        if proc.returncode != 0:
            if tmp.exists(): tmp.unlink()
            with jobs_lock:
                jobs[job_id]['done']  = True
                jobs[job_id]['error'] = f"ffmpeg a retourné le code {proc.returncode}"
            return

        # Succès : remplacer l'original
        size_after = tmp.stat().st_size
        src.unlink()
        tmp.rename(src)
        new_info = probe_file(src)

        with jobs_lock:
            jobs[job_id]['done']     = True
            jobs[job_id]['progress'] = 100
            jobs[job_id]['result']   = {
                'ok':          True,
                'size_before': format_size(size_before),
                'size_after':  format_size(size_after),
                'saved':       format_size(max(0, size_before - size_after)),
                'file':        new_info,
            }

    except Exception as e:
        if tmp.exists(): tmp.unlink()
        with jobs_lock:
            jobs[job_id]['done']  = True
            jobs[job_id]['error'] = str(e)

# ── ROUTES ────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html', version=APP_VERSION)

@app.route('/api/browse')
def api_browse():
    requested = request.args.get('path', '').strip() or str(Path.home())
    path = Path(requested).resolve()
    if not path.exists() or not path.is_dir():
        return jsonify({'error': 'Chemin invalide', 'path': str(path), 'dirs': [], 'parent': None})
    try:
        dirs = sorted(
            [str(p) for p in path.iterdir() if p.is_dir() and not p.name.startswith('.')],
            key=lambda x: x.lower()
        )
    except PermissionError:
        dirs = []
    parent = str(path.parent) if path != path.parent else None
    return jsonify({'path': str(path), 'dirs': dirs, 'parent': parent})

@app.route('/api/scan', methods=['POST'])
def api_scan():
    data = request.get_json(silent=True)
    if not data: return jsonify({'error': 'JSON invalide'}), 400
    directory = data.get('path', '').strip()
    if not directory:
        return jsonify({'error': 'Chemin requis'}), 400

    files, err = discover_files(directory)
    if err:
        return jsonify({'error': err}), 400
    if not files:
        return jsonify({'files': [], 'errors': [], 'stats': {
            'total': 0, 'optimized': 0, 'to_transcode': 0,
            'total_size': 0, 'total_size_fmt': '0 B',
        }})

    job_id = str(uuid.uuid4())
    with scan_jobs_lock:
        scan_jobs[job_id] = {
            'total': len(files), 'n': 0, 'current': '',
            'results': [], 'errors': [], 'stats': None,
            'done': False, 'cancelled': False,
        }
    threading.Thread(target=run_scan_job, args=(job_id, files), daemon=True).start()
    return jsonify({'job_id': job_id, 'total': len(files)})

@app.route('/api/scan/<job_id>/stream')
def api_scan_stream(job_id):
    def generate():
        with scan_jobs_lock:
            if job_id not in scan_jobs:
                yield f"data: {json.dumps({'type':'error','error':'Job introuvable'})}\n\n"
                return
            total = scan_jobs[job_id]['total']
        sent = 0
        while True:
            with scan_jobs_lock:
                job      = scan_jobs[job_id]
                snapshot = list(job['results'])
                n        = job['n']
                current  = job['current']
                done     = job['done']
                stats    = job.get('stats')
                errors   = job.get('errors', [])
            new_files = snapshot[sent:]
            for f in new_files:
                yield f"data: {json.dumps({'type':'file','file':f,'n':n,'total':total,'current':current})}\n\n"
            sent = len(snapshot)
            if done:
                yield f"data: {json.dumps({'type':'done','stats':stats,'errors':errors})}\n\n"
                return
            time.sleep(0.2)
    return Response(stream_with_context(generate()), mimetype='text/event-stream',
                    headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})

@app.route('/api/scan/<job_id>/cancel', methods=['POST'])
def api_scan_cancel(job_id):
    with scan_jobs_lock:
        if job_id in scan_jobs:
            scan_jobs[job_id]['cancelled'] = True
    return jsonify({'ok': True})

@app.route('/api/probe', methods=['POST'])
def api_probe():
    data = request.get_json(silent=True)
    if not data: return jsonify({'error': 'JSON invalide'}), 400
    filepath = data.get('path', '').strip()
    if not filepath: return jsonify({'error': 'path requis'}), 400
    info = probe_file(filepath)
    if not info: return jsonify({'error': 'Impossible de lire le fichier'}), 400
    return jsonify(info)

# ── EDIT AUDIO (avec progression SSE) ────────────────────

@app.route('/api/edit/audio', methods=['POST'])
def api_edit_audio():
    data = request.get_json(silent=True)
    if not data: return jsonify({'error': 'JSON invalide'}), 400
    filepath     = data.get('path', '').strip()
    try:
        keep_indices = [int(i) for i in data.get('keep_indices', [])]
    except (ValueError, TypeError):
        return jsonify({'error': 'Indices invalides'}), 400

    if not filepath:     return jsonify({'error': 'path requis'}), 400
    if not keep_indices: return jsonify({'error': 'Impossible de supprimer toutes les pistes audio'}), 400

    src = Path(filepath)
    if not src.exists(): return jsonify({'error': 'Fichier introuvable'}), 404

    job_id   = str(uuid.uuid4())
    tmp      = src.with_name(src.stem + f'.__tmp_{job_id}__' + src.suffix)
    size_bef = src.stat().st_size
    info     = probe_file(src)
    dur_sec  = info['duration_raw'] if info else 0

    cmd = ['ffmpeg', '-y', '-i', str(src), '-map', '0:v']
    for idx in keep_indices:
        cmd += ['-map', f'0:{idx}']
    cmd += ['-map', '0:s?', '-c', 'copy', '-map_metadata', '0', str(tmp)]

    with jobs_lock:
        jobs[job_id] = {'lines': [], 'done': False, 'progress': 0, 'error': None, 'result': None}

    t = threading.Thread(target=run_ffmpeg_job,
                         args=(job_id, cmd, src, tmp, size_bef, dur_sec),
                         daemon=True)
    t.start()
    return jsonify({'job_id': job_id})

# ── EDIT STREAMS : audio + sous-titres en une passe ──────

@app.route('/api/edit/streams', methods=['POST'])
def api_edit_streams():
    """Supprime des pistes audio et/ou sous-titres en une seule passe ffmpeg."""
    data = request.get_json(silent=True)
    if not data: return jsonify({'error': 'JSON invalide'}), 400
    filepath = data.get('path', '').strip()
    try:
        keep_audio    = [int(i) for i in data.get('keep_audio', [])]
        keep_subtitle = [int(i) for i in data.get('keep_subtitle', [])]
    except (ValueError, TypeError):
        return jsonify({'error': 'Indices invalides'}), 400

    if not filepath:   return jsonify({'error': 'path requis'}), 400
    if not keep_audio: return jsonify({'error': 'Impossible de supprimer toutes les pistes audio'}), 400

    src = Path(filepath)
    if not src.exists(): return jsonify({'error': 'Fichier introuvable'}), 404

    job_id   = str(uuid.uuid4())
    tmp      = src.with_name(src.stem + f'.__tmp_{job_id}__' + src.suffix)
    size_bef = src.stat().st_size
    info     = probe_file(src)
    dur_sec  = info['duration_raw'] if info else 0

    cmd = ['ffmpeg', '-y', '-i', str(src), '-map', '0:v']
    for idx in keep_audio:
        cmd += ['-map', f'0:{idx}']
    for idx in keep_subtitle:
        cmd += ['-map', f'0:{idx}']
    cmd += ['-c', 'copy', '-map_metadata', '0', str(tmp)]

    with jobs_lock:
        jobs[job_id] = {'lines': [], 'done': False, 'progress': 0, 'error': None, 'result': None}

    t = threading.Thread(target=run_ffmpeg_job,
                         args=(job_id, cmd, src, tmp, size_bef, dur_sec),
                         daemon=True)
    t.start()
    return jsonify({'job_id': job_id})

# ── TRANSCODE (avec progression SSE) ─────────────────────

# ── Détection GPU NVENC au démarrage ─────────────────────
def detect_nvenc():
    """Retourne les encodeurs NVENC disponibles."""
    try:
        r = subprocess.run(['ffmpeg', '-encoders'], capture_output=True, text=True, timeout=5)
        out = r.stdout + r.stderr
        return {
            'hevc': 'hevc_nvenc' in out,
            'av1':  'av1_nvenc'  in out,
        }
    except Exception:
        return {'hevc': False, 'av1': False}

NVENC = detect_nvenc()

@app.route('/api/caps')
def api_caps():
    """Retourne les capacités d'encodage disponibles."""
    return jsonify({'nvenc': NVENC})

def run_transcode_job(job_id, cmd, out_path, size_b, dur_sec, replace_src=None):
    """Thread de transcodage avec suivi SSE.
    Si replace_src est fourni, le fichier out_path est renommé vers replace_src après succès
    (mode écrasement de l'original).
    """
    def push(line):
        with jobs_lock:
            jobs[job_id]['lines'].append(line)
    push(f"CMD: {' '.join(cmd)}\n")
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1)
        with jobs_lock:
            jobs[job_id]['proc'] = proc
        for line in proc.stdout:
            push(line)
            if dur_sec > 0:
                m = re.search(r'time=(\d+):(\d+):([\d.]+)', line)
                if m:
                    el = int(m.group(1))*3600 + int(m.group(2))*60 + float(m.group(3))
                    with jobs_lock:
                        jobs[job_id]['progress'] = min(99, int(el/dur_sec*100))
        proc.wait()
        if proc.returncode != 0:
            if out_path.exists(): out_path.unlink()
            with jobs_lock:
                jobs[job_id]['done']  = True
                jobs[job_id]['error'] = f"ffmpeg a retourné le code {proc.returncode}"
            return
        # Mode écrasement : remplacer l'original par le fichier transcodé
        if replace_src:
            os.replace(str(out_path), str(replace_src))
            final_path = replace_src
        else:
            final_path = out_path
        new_size = final_path.stat().st_size
        new_info = probe_file(final_path)
        with jobs_lock:
            jobs[job_id]['done']     = True
            jobs[job_id]['progress'] = 100
            jobs[job_id]['result']   = {
                'ok':          True,
                'output_path': str(final_path),
                'size_before': format_size(size_b),
                'size_after':  format_size(new_size),
                'saved':       format_size(max(0, size_b - new_size)),
                'ratio':       round((1 - new_size/size_b)*100, 1) if size_b else 0,
                'file':        new_info,
            }
    except Exception as e:
        if out_path.exists(): out_path.unlink()
        with jobs_lock:
            jobs[job_id]['done']  = True
            jobs[job_id]['error'] = str(e)

@app.route('/api/transcode', methods=['POST'])
def api_transcode():
    """
    Lance un transcodage vidéo.
    Body JSON: { path, codec, crf, preset, audio, encoder }
      codec:   hevc | av1
      encoder: cpu | gpu
      crf:     qualité (16-32 pour CPU, 20-36 pour NVENC)
      preset:  slow | medium | fast | ultrafast
      audio:   copy | aac
    """
    data = request.get_json(silent=True)
    if not data: return jsonify({'error': 'JSON invalide'}), 400
    filepath  = data.get('path', '').strip()
    codec     = data.get('codec', 'hevc')
    encoder   = data.get('encoder', 'cpu')   # cpu | gpu
    try:
        crf = int(data.get('crf', 22))
    except (ValueError, TypeError):
        return jsonify({'error': 'CRF invalide'}), 400
    CRF_LIMITS = {'hevc': (1, 51), 'av1': (1, 63)}
    lo, hi = CRF_LIMITS.get(codec, (1, 63))
    if not (lo <= crf <= hi):
        return jsonify({'error': f'CRF hors limites ({lo}-{hi})'}), 400
    preset    = data.get('preset', 'medium')
    audio     = data.get('audio', 'copy')
    overwrite = bool(data.get('overwrite', True))

    if not filepath: return jsonify({'error': 'path requis'}), 400
    src = Path(filepath)
    if not src.exists(): return jsonify({'error': 'Fichier introuvable'}), 404

    job_id = str(uuid.uuid4())

    # Nom du fichier de sortie
    if overwrite:
        out         = src.with_name(src.stem + f'.__tc_tmp_{job_id}__' + src.suffix)
        replace_src = src   # renommé vers src après succès
    else:
        tag = ('hevc' if codec == 'hevc' else 'av1') + ('.nvenc' if encoder == 'gpu' else '')
        out = src.with_name(src.stem + f'.{tag}' + src.suffix)
        n = 1
        while out.exists():
            out = src.with_name(src.stem + f'.{tag}.{n}' + src.suffix)
            n += 1
        replace_src = None

    info    = probe_file(src)
    dur_sec = info['duration_raw'] if info else 0
    size_b  = src.stat().st_size

    # ── Construire les arguments vidéo ────────────────────
    if encoder == 'gpu':
        # NVENC : le mode VBR avec -b:v 0 seul ne contraint pas le débit.
        # On utilise -rc constqp (qualité constante par QP) qui est l'équivalent
        # réel du CRF pour NVENC : chaque frame est encodée au QP demandé,
        # ce qui produit un débit variable calé sur le contenu, donc une vraie
        # réduction de taille.
        # CRF 22 ≈ QP 22 pour libx265. NVENC QP est une échelle similaire.
        nvenc_preset = {'ultrafast':'p1','fast':'p2','medium':'p4','slow':'p6'}.get(preset,'p4')
        if codec == 'hevc':
            vid_args = ['-c:v', 'hevc_nvenc',
                        '-rc', 'constqp',      # qualité constante = débit vraiment réduit
                        '-qp', str(crf),        # QP cible (équivalent CRF)
                        '-preset', nvenc_preset,
                        '-tag:v', 'hvc1']
        else:  # av1
            vid_args = ['-c:v', 'av1_nvenc',
                        '-rc', 'constqp',
                        '-qp', str(crf),
                        '-preset', nvenc_preset]
    else:  # cpu
        if codec == 'hevc':
            vid_args = ['-c:v', 'libx265', '-crf', str(crf), '-preset', preset, '-tag:v', 'hvc1']
        else:  # av1
            svt_preset = {'slow':'4','medium':'6','fast':'9','ultrafast':'12'}.get(preset,'6')
            vid_args = ['-c:v', 'libsvtav1', '-crf', str(crf), '-preset', svt_preset]

    aud_args = ['-c:a', 'copy'] if audio == 'copy' else ['-c:a', 'aac', '-b:a', '192k']

    # ── Mapper sélectivement les flux valides ─────────────
    # -map 0 copie tout y compris les flux inconnus (WebVTT, pièces jointes)
    # et fait échouer ffmpeg. On inspecte les flux via ffprobe et on ne
    # mappe que vidéo principale + audio + sous-titres décodables.
    SAFE_SUBTITLE_CODECS = {
        'subrip', 'srt', 'ass', 'ssa', 'mov_text',
        'hdmv_pgs_subtitle', 'dvd_subtitle', 'dvb_subtitle',
        'webvtt',  # webvtt est parfois supporté selon le conteneur cible
    }

    map_args = []
    try:
        probe_cmd = ['ffprobe', '-v', 'quiet', '-print_format', 'json',
                     '-show_streams', str(src)]
        probe_res = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
        streams   = json.loads(probe_res.stdout).get('streams', [])

        video_mapped = False
        for s in streams:
            idx   = s.get('index')
            stype = s.get('codec_type', '')
            codec_name = s.get('codec_name', 'none').lower()

            if stype == 'video':
                # Ne mapper que la première vraie piste vidéo (pas les MJPEG/attachments)
                if not video_mapped and codec_name not in ('mjpeg', 'png', 'gif', 'bmp'):
                    map_args += ['-map', f'0:{idx}']
                    video_mapped = True
                # ignorer les images attachées (poster, thumb…)

            elif stype == 'audio':
                map_args += ['-map', f'0:{idx}']

            elif stype == 'subtitle':
                # Exclure les codecs non supportés en sortie MKV/MP4
                if codec_name in SAFE_SUBTITLE_CODECS:
                    map_args += ['-map', f'0:{idx}']
                # else: on ignore silencieusement

            # Ignorer 'attachment' et 'data' entièrement

        if not map_args:
            # Fallback minimal si rien détecté
            map_args = ['-map', '0:v:0', '-map', '0:a?']

    except Exception:
        # En cas d'erreur probe, fallback sûr
        map_args = ['-map', '0:v:0', '-map', '0:a?', '-map', '0:s?']

    cmd = (['ffmpeg', '-y', '-i', str(src)]
           + vid_args + aud_args
           + map_args
           + ['-map_metadata', '0', str(out)])

    with jobs_lock:
        jobs[job_id] = {'lines':[], 'done':False, 'progress':0, 'error':None, 'result':None}

    t = threading.Thread(target=run_transcode_job,
                         args=(job_id, cmd, out, size_b, dur_sec, replace_src), daemon=True)
    t.start()
    return jsonify({'job_id': job_id})

# ── SSE : suivi de progression ────────────────────────────

@app.route('/api/job/<job_id>/stream')
def job_stream(job_id):
    """Server-Sent Events : envoie la progression ligne par ligne jusqu'à la fin."""
    def generate():
        import time
        sent = 0
        while True:
            with jobs_lock:
                job   = jobs.get(job_id)
                if not job:
                    yield f"data: {json.dumps({'error':'job inconnu'})}\n\n"
                    return
                lines    = job['lines'][sent:]
                progress = job['progress']
                done     = job['done']
                error    = job['error']
                result   = job['result']

            for line in lines:
                sent += 1
                payload = json.dumps({'type':'log','line': line.rstrip(),'progress': progress})
                yield f"data: {payload}\n\n"

            if done:
                if error:
                    yield f"data: {json.dumps({'type':'error','error':error})}\n\n"
                else:
                    yield f"data: {json.dumps({'type':'done','result':result})}\n\n"
                # Nettoyer le job après 60 s
                def cleanup():
                    time.sleep(60)
                    with jobs_lock:
                        jobs.pop(job_id, None)
                threading.Thread(target=cleanup, daemon=True).start()
                return

            time.sleep(0.2)

    return Response(stream_with_context(generate()),
                    mimetype='text/event-stream',
                    headers={'Cache-Control':'no-cache','X-Accel-Buffering':'no'})

@app.route('/api/job/<job_id>/cancel', methods=['POST'])
def job_cancel(job_id):
    with jobs_lock:
        job = jobs.get(job_id)
        if job and not job['done']:
            proc = job.get('proc')
            if proc: proc.terminate()
            job['done']  = True
            job['error'] = 'Annulé par l\'utilisateur'
    return jsonify({'ok': True})

if __name__ == '__main__':
    debug_mode = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(debug=debug_mode, port=5000, threaded=True)
