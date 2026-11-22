"""Synthetic real-FFmpeg, fail-closed codec and contract controls."""
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import artifact_video_fit as av


@pytest.fixture
def clip(tmp_path):
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        pytest.skip('FFmpeg/ffprobe absent: no false positive quality claim')
    source = tmp_path / 'source.mp4'
    subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-f','lavfi',
                    '-i','testsrc2=size=320x180:rate=15','-t','1.2','-c:v','libx264',
                    '-crf','12','-pix_fmt','yuv420p','-an',str(source)],check=True,timeout=20)
    root = tmp_path / 'artifact'
    (root/'media/video').mkdir(parents=True)
    shutil.copy2(source,root/'media/video/hero-wide.mp4')
    return root


def test_real_ffmpeg_quality_gate_reduces_bytes_preserves_geometry_and_frames(clip):
    source = clip/'media/video/hero-wide.mp4'
    before=av.probe(source)
    n=source.stat().st_size
    result=av.fit_copies(clip,need_bytes=1024,candidates=('media/video/hero-wide.mp4',))
    assert result['target_met'] and result['saved_bytes']>=1024
    entry=result['attempts'][0]
    assert entry['accepted'] and entry['pass']
    assert entry['mean_ssim']>=av.MIN_MEAN_SSIM
    assert entry['min_frame_ssim']>=av.MIN_FRAME_SSIM
    assert len(entry['input_sha256'])==len(entry['output_sha256'])==64
    assert av.probe(source)==before and source.stat().st_size==n-result['saved_bytes']


def test_report_fails_closed_when_target_is_unreachable(clip):
    result=av.fit_copies(clip,need_bytes=10**8,candidates=('media/video/hero-wide.mp4',))
    assert not result['target_met'] and result['saved_bytes']<10**8


def test_invalid_input_and_symlink_destination_rejected(clip,tmp_path):
    for val in (True,-1,0.5,None,'1000'):
        with pytest.raises(ValueError): av.fit_copies(clip,need_bytes=val)
    (clip/'media/video/hero-wide.mp4').unlink()
    (clip/'media/video/hero-wide.mp4').symlink_to(tmp_path/'source.mp4')
    with pytest.raises(ValueError,match='symlink'):
        av.fit_copies(clip,need_bytes=1,candidates=('media/video/hero-wide.mp4',))


def test_invalid_candidate_path_does_not_scan_other_directories(clip):
    with pytest.raises(ValueError,match='candidate_not_allowlisted'):
        av.fit_copies(clip,need_bytes=1,candidates=('../user-secrets.mp4',))


def test_incomplete_framewise_comparison_does_not_return_pass(clip,monkeypatch,tmp_path):
    source=clip/'media/video/hero-wide.mp4'
    original_exec = av._execute
    def fake_exec(args,**kwargs):
        if args[0]=='ffprobe':
            return original_exec(args,**kwargs)
        if args[0]=='ffmpeg':
            for item in args:
                if item.startswith('ssim=stats_file='):
                    Path(item.split('=',2)[-1]).write_text('n:1 Y:1 U:1 V:1 All:1.0\n')
        return subprocess.CompletedProcess(args,0,stdout='')
    monkeypatch.setattr(av,'_execute',fake_exec)
    with pytest.raises(ValueError,match='incomplete_framewise_quality_evidence'):
        av.quality(source,source,tmp_path/'stats.log')


def test_real_ffmpeg_rejects_heavily_degraded_video(clip, tmp_path):
    source=clip/'media/video/hero-wide.mp4'
    candidate=tmp_path/'bad.mp4'
    subprocess.run(['ffmpeg','-nostdin','-v','error','-y','-i',str(source),
                    '-c:v','libx264','-preset','medium','-crf','46',str(candidate)],
                   check=True,timeout=20)
    report=av.quality(source,candidate,tmp_path/'poor.ssim')
    assert report['pass'] is False
    assert report['mean_ssim'] < av.MIN_MEAN_SSIM


def test_no_accepted_candidate_does_not_mutate_asset(clip, monkeypatch):
    source=clip/'media/video/hero-wide.mp4'
    raw=source.read_bytes()
    actual=av.quality
    def decline(src, candidate, stats, **kwargs):
        measured=actual(src,candidate,stats,**kwargs)
        return {**measured, 'pass':False}
    monkeypatch.setattr(av,'quality',decline)
    result=av.fit_copies(clip,need_bytes=1000,candidates=('media/video/hero-wide.mp4',))
    assert not result['target_met'] and result['saved_bytes']==0
    assert source.read_bytes()==raw
    assert result['attempts'] and all(x['accepted'] is False for x in result['attempts'])


def test_bounded_attempt_limit_does_not_modify_clips(clip, monkeypatch):
    source=clip/'media/video/hero-wide.mp4'
    raw=source.read_bytes()
    monkeypatch.setattr(av,'MAX_ATTEMPTS',0)
    result=av.fit_copies(clip,need_bytes=1,candidates=('media/video/hero-wide.mp4',))
    assert result['budget_exhausted'] and not result['target_met']
    assert result['attempts']==[]
    assert source.read_bytes()==raw
