#!/usr/bin/env python
import subprocess
import sys
import numpy as np
# import onnx
import onnxruntime as ort
from typing import Generator, Any

from utils import FFMPEG_PATH
from proglog import default_bar_logger

SAMPLE_RATE = 32000

is_windows = sys.platform.startswith('win')


def subsample(frame: np.ndarray, scale_factor: int) -> np.ndarray:
    subframe = frame[:len(frame) - (len(frame) % scale_factor)].reshape(
        -1, scale_factor)
    subframe_mean = subframe.max(axis=1)

    subsample = subframe_mean

    if len(frame) % scale_factor != 0:
        residual_frame = frame[len(frame) - (len(frame) % scale_factor):]
        residual_mean = residual_frame.max()
        subsample = np.append(subsample, residual_mean)

    return subsample


def get_segments(
    scores: np.ndarray,
    precision: int,
    threshold: float,
    offset: int
) -> Generator[Any, Any, Any]:

    seq_iter = iter(np.where(scores > threshold)[0])
    try:
        seq = next(seq_iter)
        pred = scores[seq]
        segment = {'start': seq, 'end': seq, 'pred': pred}
    except StopIteration:
        return

    for seq in seq_iter:
        pred = scores[seq]
        if seq - 1 == segment['end']:
            segment['end'] = seq
            segment['pred'] = max(segment['pred'], pred)
        else:
            segment['start'] = segment['start']
            segment['end'] = segment['end']

            yield segment
            segment = {'start': seq, 'end': seq, 'pred': pred}

    yield segment


def compute_timestamps(
    framewise_output: np.ndarray,
    precision: int,
    threshold: float,
    focus_idx: int,
    offset: int,
):
    focus = framewise_output[:, focus_idx]
    # precision in the amount of milliseconds per timestamp sample (higher values will result in less precise timestamps)

    subsampled_scores = subsample(focus, precision)
    segments = map(
        lambda segment: {
            'start': segment['start'] * precision / 100 + offset,
            'end': segment['end'] * precision / 100 + offset + 1,
            'pred': round(float(segment['pred']), 6)
        }, get_segments(subsampled_scores, precision, threshold, offset))
    return segments


def pad_array_if_needed(arr, desired_size, pad_value=0):
    current_size = arr.shape[0]
    if current_size < desired_size:
        padding_needed = desired_size - current_size
        padded_array = np.pad(
            arr, (0, padding_needed), "constant", constant_values=(pad_value,)
        )
        return padded_array
    else:
        return arr


def load_audio(file: str, sr: int, frame_count: int):
    cmd = [
        FFMPEG_PATH, '-hide_banner', '-loglevel', 'warning', '-i', file,
        '-filter_complex', '[0:a]aresample=32000:async=1,asetpts=PTS-STARTPTS,atempo=1,pan=mono|c0=c0[audio]', '-map',
        '[audio]', '-f', 's16le', '-acodec', 'pcm_s16le', '-ar', str(
            sr), '-ac', '1', '-bufsize', '128k', '-'
    ]

    # Specify subprocess options to suppress the command prompt on Windows
    subprocess_options = {
        'stdout': subprocess.PIPE,
        'stderr': subprocess.PIPE,
    }

    if is_windows:
        subprocess_options['creationflags'] = subprocess.CREATE_NO_WINDOW

    chunk_size = frame_count * 2

    process = subprocess.Popen(
        cmd, bufsize=1, **subprocess_options)

    try:
        while True:
            chunk = process.stdout.read(chunk_size)
            if not chunk:
                break
            yield chunk
    except GeneratorExit:
        # Thrown if the user cancels the process (i.e. kills the thread)
        process.terminate()
        process.wait()
        return

    process.stdout.close()
    return_code = process.wait()
    if return_code:
        if process.returncode != 0:
            raise Exception(
                "Failed to process the file. Either the file does not exist or is corrupted.")
        raise subprocess.CalledProcessError(return_code, cmd)


def get_timestamps(file, precision=100, block_size=600, threshold=0.90, focus_idx=60, model="bdetectionmodel_05_01_23", logger=None):
    # Input checking
    if precision < 0:
        raise Exception("Precision must be a positive number!")

    if not (threshold >= 0 and threshold <= 1):
        raise Exception("Threshold must be between 0 and 1!")

    if block_size < 0:
        raise Exception("Block size must be a positive number!")
    
    if focus_idx not in [58, 60]:
        raise Exception("Focus index must be 58 (B) or 60 (F)")

    sess_options = ort.SessionOptions()
    sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL

    ort_session = ort.InferenceSession(
        model,
        sess_options,
        providers=ort.get_available_providers()
    )

    offset = 0

    blocks = list(load_audio(file, SAMPLE_RATE, SAMPLE_RATE * block_size))

    info = {'filename': file, 'timestamps': []}

    frame_count = SAMPLE_RATE * block_size

    if logger:
        bar_logger = default_bar_logger(logger)
        blocks = bar_logger.iter_bar(block=blocks)

    for block in blocks:
        samples = np.frombuffer(block, dtype=np.int16)
        samples = pad_array_if_needed(samples, frame_count)
        samples = samples.reshape(1, -1)
        samples = samples / (2**15)
        samples = samples.astype(np.float32)

        ort_inputs = {"input": samples}
        framewise_output = ort_session.run(["output"], ort_inputs)[0]

        preds = framewise_output[0]
        info["timestamps"].extend(
            compute_timestamps(
                preds, precision, threshold, focus_idx, offset
            )
        )

        offset += block_size

    return info
