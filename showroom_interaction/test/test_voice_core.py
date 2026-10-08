#!/usr/bin/env python3
"""Deterministic tests for voice segmentation and assistant reply parsing."""

from array import array
import json
from pathlib import Path
import sys
import tempfile
import wave


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))

from showroom_voice_core import (  # noqa: E402
    assistant_reply,
    DuplicateSuppressor,
    meaningful_transcript,
    pcm_rms,
    UtteranceSegmenter,
    WakeWordGate,
    write_pcm_wav,
)


def pcm_frame(value, samples):
    """Build one constant signed 16-bit PCM frame."""
    return array('h', [value] * samples).tobytes()


def main():
    segmenter = UtteranceSegmenter(
        sample_rate=1000,
        frame_ms=20,
        rms_threshold=100,
        start_ms=40,
        end_silence_ms=60,
        min_speech_ms=60,
        max_utterance_sec=2,
        pre_roll_ms=40,
    )
    samples = segmenter.frame_bytes // 2
    silence = pcm_frame(0, samples)
    voice = pcm_frame(1000, samples)
    assert pcm_rms(silence) == 0.0
    assert int(pcm_rms(voice)) == 1000

    output = None
    for frame in [silence, voice, voice, voice, silence, silence, silence]:
        output = segmenter.feed(frame) or output
    assert output is not None
    assert len(output) >= len(voice) * 3

    # Speech uses a lower release threshold after activation, so quiet words
    # inside one sentence do not become artificial silence.
    hysteresis = UtteranceSegmenter(
        sample_rate=1000,
        frame_ms=20,
        rms_threshold=500,
        release_threshold_ratio=0.5,
        start_ms=40,
        end_silence_ms=60,
        min_speech_ms=60,
        max_utterance_sec=2,
        pre_roll_ms=40,
    )
    loud = pcm_frame(800, samples)
    quiet = pcm_frame(300, samples)
    output = None
    frames = [loud, loud, quiet, quiet, quiet, silence, silence, silence]
    for frame in frames:
        output = hysteresis.feed(frame) or output
    assert output is not None
    assert len(output) >= len(loud) * 5

    response = assistant_reply(json.dumps({
        'request_id': 3,
        'intent': 'pause_tour',
        'reply': ' 已提交暂停请求。 ',
    }, ensure_ascii=False))
    assert response == {
        'request_id': 3,
        'intent': 'pause_tour',
        'reply': '已提交暂停请求。',
    }
    assert assistant_reply('not-json') is None
    assert assistant_reply('{"reply":""}') is None

    with tempfile.NamedTemporaryFile(suffix='.wav') as temporary:
        write_pcm_wav(temporary.name, voice * 3, sample_rate=1000)
        with wave.open(temporary.name, 'rb') as stream:
            assert stream.getnchannels() == 1
            assert stream.getsampwidth() == 2
            assert stream.getframerate() == 1000
            assert stream.getnframes() == samples * 3

    # Wake word gating: an empty list disables the gate (legacy behaviour).
    open_gate = WakeWordGate(wake_words=[], session_sec=10.0)
    assert open_gate.accept('随便说点什么', now=0.0)[0] is True
    gate = WakeWordGate(wake_words=['开始', '开始导览'], session_sec=10.0)
    assert gate.accept('不知道说什么', now=1.0) == (
        False, '不知道说什么', 'wake_required')
    accepted, text, reason = gate.accept('开始导览', now=2.0)
    assert accepted and reason == 'wake_word' and text == '开始导览'
    accepted, text, reason = gate.accept('跳过科技舞蹈展厅', now=5.0)
    assert accepted and reason == 'session'
    assert gate.accept('继续参观', now=50.0)[0] is False

    # Repeated identical commands are suppressed within the window.
    dedup = DuplicateSuppressor(window_sec=5.0)
    assert dedup.accept('暂停导览', now=0.0) is True
    assert dedup.accept('暂停导览', now=2.0) is False
    assert dedup.accept('继续参观', now=3.0) is True
    assert dedup.accept('暂停导览', now=9.0) is True

    # Ambient/hallucinated transcripts are rejected before wake gating.
    assert meaningful_transcript('好的') is True
    assert meaningful_transcript('好') is False
    assert meaningful_transcript('谢谢观看') is False
    assert meaningful_transcript('请开始导览吧', no_speech_prob=0.9) is False
    assert meaningful_transcript('开始导览', no_speech_prob=0.1) is True

    # The adaptive noise floor raises the trigger above steady background so a
    # quiet room sound is not segmented as speech, while a loud word still is.
    denoiser = UtteranceSegmenter(
        sample_rate=1000,
        frame_ms=20,
        rms_threshold=100,
        start_ms=40,
        end_silence_ms=60,
        min_speech_ms=60,
        max_utterance_sec=2,
        pre_roll_ms=40,
        adaptive_noise=True,
        noise_gain=3.0,
        noise_floor_alpha=0.5,
    )
    background = pcm_frame(80, samples)
    near = pcm_frame(150, samples)
    output = None
    for _ in range(8):
        output = denoiser.feed(background) or output
    for _ in range(6):
        output = denoiser.feed(near) or output
    assert output is None
    for _ in range(6):
        output = denoiser.feed(pcm_frame(1000, samples)) or output
    for _ in range(4):
        output = denoiser.feed(background) or output
    assert output is not None

    print('Voice VAD, WAV, and assistant reply scenarios: OK')


if __name__ == '__main__':
    main()
