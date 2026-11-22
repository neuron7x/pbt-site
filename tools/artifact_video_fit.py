#!/usr/bin/env python3
"""Bounded, quality-gated MP4 optimization for *copied* portable media.

Never writes source web/media. A successful conversion must strictly shrink the
copied MP4 while preserving dimensions, decoded frame count, and strict SSIM.
Its report is supplementary; final artifact byte and SHA gate remains mandatory.
"""
from __future__ import annotations

import json
import hashlib
import os
from pathlib import Path
import re
import subprocess
import tempfile

MIN_MEAN_SSIM = 0.995
MIN_FRAME_SSIM = 0.985
CRFS = (17, 19, 21)
# First largest hero, then other large clips. No source loss, dropped asset or resolution change.
CANDIDATES = (
    'media/video/hero-wide.mp4', 'media/video/hero-tall.mp4',
    'media/video/hero-wide-720.mp4', 'media/cine/voda-w.mp4',
    'media/cine/vyviz-w.mp4', 'media/cine/demont-w.mp4',
)


def _execute(args, *, timeout=150) -> subprocess.CompletedProcess:
    return subprocess.run(args, check=True, capture_output=True, text=True, timeout=timeout)


def probe(path: Path) -> tuple[int, int, int]:
    raw = _execute(['ffprobe', '-v', 'error', '-select_streams', 'v:0',
                    '-count_frames', '-show_entries', 'stream=width,height,nb_read_frames',
                    '-of', 'json', str(path)], timeout=40).stdout
    streams = json.loads(raw).get('streams', [])
    if len(streams) != 1:
        raise ValueError('ambiguous_video_stream')
    d = streams[0]
    dimensions = (int(d['width']), int(d['height']), int(d['nb_read_frames']))
    if min(dimensions) < 1:
        raise ValueError('invalid_video_geometry')
    return dimensions


def quality(source: Path, candidate: Path, stats: Path) -> dict:
    """Compare all decoded frames; reject a perfect mean hiding poor individual frames."""
    if probe(source) != probe(candidate):
        raise ValueError('geometry_or_decoded_frame_count_changed')
    _execute(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(source), '-i', str(candidate),
              '-lavfi', 'ssim=stats_file=' + str(stats), '-an', '-f', 'null', '-'], timeout=180)
    rows = [float(v) for v in re.findall(r'\bAll:([0-9]+(?:\.[0-9]+)?)', stats.read_text())]
    frames = probe(source)[2]
    if len(rows) != frames or any(not (0 <= n <= 1) for n in rows):
        raise ValueError('incomplete_framewise_quality_evidence')
    score = {'mean_ssim': sum(rows) / len(rows), 'min_frame_ssim': min(rows),
             'decoded_frames': frames, 'width': probe(source)[0], 'height': probe(source)[1]}
    score['pass'] = score['mean_ssim'] >= MIN_MEAN_SSIM and score['min_frame_ssim'] >= MIN_FRAME_SSIM
    return score


def fit_copies(root: Path, *, need_bytes: int, candidates=CANDIDATES) -> dict:
    """Try bounded transcodes. Return deterministic evidence; final byte gate is separate.

    Failure is not disguised: caller must reject the export if bytes still exceed.
    """
    if type(need_bytes) is not int or need_bytes < 0:
        raise ValueError('invalid_target_savings')
    if root.is_symlink() or not root.is_dir():
        raise ValueError('invalid_artifact_root')
    outcome = {'schema_version': 1, 'measurement': 'decoded-frame SSIM, not VMAF or human review',
               'target_savings_bytes': need_bytes, 'saved_bytes': 0, 'attempts': [],
               'target_met': not need_bytes}
    if not need_bytes:
        return outcome
    # Safe by construction: only whitelisted repository-relative filenames.
    for rel in candidates:
        if outcome['saved_bytes'] >= need_bytes:
            break
        if not (re.fullmatch(r'media/(?:video|cine)/[a-z0-9-]+\.mp4', rel)):
            raise ValueError('candidate_not_allowlisted')
        src = root / rel
        if src.is_symlink() or not src.is_file():
            raise ValueError('candidate_absent_or_symlinked:' + rel)
        if not src.resolve(strict=True).is_relative_to(root.resolve(strict=True)):
            raise ValueError('candidate_escapes_artifact_root')
        original_size = src.stat().st_size
        original_sha = hashlib.sha256(src.read_bytes()).hexdigest()
        accepted = False
        for crf in CRFS:
            with tempfile.TemporaryDirectory(prefix='pbt-fit-', dir=str(root.parent)) as td:
                temp = Path(td)
                proposed = temp / 'candidate.mp4'
                stats = temp / 'ssim.log'
                _execute(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-i', str(src),
                          '-map', '0:v:0', '-map', '0:a?', '-c:v', 'libx264',
                          '-preset', 'medium', '-threads', '2', '-crf', str(crf),
                          '-pix_fmt', 'yuv420p', '-c:a', 'copy', '-movflags', '+faststart',
                          str(proposed)], timeout=150)
                reduced = original_size - proposed.stat().st_size
                log = {'source': rel, 'crf': crf, 'old_bytes': original_size,
                       'new_bytes': proposed.stat().st_size, 'saved_bytes': max(0, reduced),
                       'input_sha256': original_sha}
                if reduced > 0:
                    q = quality(src, proposed, stats)
                    log.update(q)
                    if q['pass']:
                        # atomic replacement of *copied* file only; originals stay in web/media.
                        new_sha = hashlib.sha256(proposed.read_bytes()).hexdigest()
                        os.replace(proposed, src)
                        log['output_sha256'] = new_sha
                        outcome['saved_bytes'] += reduced
                        log['accepted'] = True
                        accepted = True
                if not accepted:
                    log['accepted'] = False
                outcome['attempts'].append(log)
            if accepted:
                break
    outcome['target_met'] = outcome['saved_bytes'] >= need_bytes
    return outcome
