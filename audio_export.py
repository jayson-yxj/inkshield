"""Sample-aligned local audio export using PyAV's LGPL FFmpeg wheel."""
from fractions import Fraction
from pathlib import Path
import numpy as np


def has_audio(source):
    import av
    with av.open(str(source)) as container:
        return bool(container.streams.audio)


def mux_segment_audio(silent_video, original, output, start_seconds, duration):
    """Copy protected video, encode first original audio stream for selected interval.

    Audio timestamps are mapped to original presentation time, trimmed at sample
    boundaries, and padded for gaps. Never copy source video into the output.
    """
    import av
    silent_video, original, output = map(Path, (silent_video, original, output))
    audio_path = output.with_name('segment-audio.m4a')
    try:
        with av.open(str(original)) as source:
            if not source.streams.audio:
                silent_video.replace(output)
                return False
            stream = source.streams.audio[0]
            rate = 48000
            total = max(1, round(duration * rate))
            start = round(start_seconds * rate)
            origin = Fraction(source.start_time or 0, av.time_base)
            # Seek to a preceding audio packet; decoder preroll is trimmed below.
            source.seek(max(0, int((origin + Fraction(start, rate)) / stream.time_base)),
                        stream=stream, backward=True)
            resampler = av.AudioResampler(format='fltp', layout='stereo', rate=rate)
            with av.open(str(audio_path), 'w') as encoded:
                target = encoded.add_stream('aac', rate=rate)
                target.layout = 'stereo'
                target.bit_rate = 192000
                cursor = 0
                def emit(values):
                    nonlocal cursor
                    # Keep working buffers bounded even for large timestamp gaps.
                    for offset in range(0, values.shape[1], 4096):
                        part = values[:, offset:offset+4096]
                        frame = av.AudioFrame.from_ndarray(np.ascontiguousarray(part), format='fltp', layout='stereo')
                        frame.sample_rate = rate
                        frame.time_base = Fraction(1, rate)
                        frame.pts = cursor
                        for packet in target.encode(frame): encoded.mux(packet)
                        cursor += part.shape[1]
                def silence(until):
                    while cursor < until:
                        emit(np.zeros((2, min(4096, until-cursor)), dtype=np.float32))
                def consume(frame):
                    if frame.pts is None:
                        raise RuntimeError('原音轨缺少时间戳，无法可靠裁切')
                    position = round((frame.pts * frame.time_base - origin) * rate) - start
                    values = frame.to_ndarray()
                    end = position + values.shape[1]
                    if end <= cursor or position >= total: return
                    silence(min(total, max(cursor, position)))
                    offset = max(0, cursor-position)
                    emit(values[:, offset:offset+max(0,min(total-cursor, values.shape[1]-offset))])
                for decoded in source.decode(stream):
                    for frame in resampler.resample(decoded): consume(frame)
                    if cursor >= total: break
                if cursor < total:
                    for frame in resampler.resample(None): consume(frame)
                silence(total)
                for packet in target.encode(None): encoded.mux(packet)
        # Interleave one pending packet per input; timestamps stay independent.
        with av.open(str(silent_video)) as video, av.open(str(audio_path)) as audio, av.open(str(output), 'w', options={'movflags':'+faststart'}) as destination:
            video_out = destination.add_stream_from_template(video.streams.video[0])
            audio_out = destination.add_stream_from_template(audio.streams.audio[0])
            def packets(container, stream):
                for packet in container.demux(stream):
                    if packet.dts is not None: yield packet
            streams = [(iter(packets(video,video.streams.video[0])),video_out),
                       (iter(packets(audio,audio.streams.audio[0])),audio_out)]
            pending = [next(iterator,None) for iterator,_ in streams]
            while any(packet is not None for packet in pending):
                index = min((i for i,p in enumerate(pending) if p is not None), key=lambda i: pending[i].dts*pending[i].time_base)
                packet = pending[index]
                packet.stream = streams[index][1]
                destination.mux(packet)
                pending[index] = next(streams[index][0],None)
        if not has_audio(output): raise RuntimeError('合成后缺少音轨')
        return True
    except Exception as exc:
        output.unlink(missing_ok=True)
        raise RuntimeError('原音轨处理失败，导出未完成：' + str(exc)) from exc
    finally:
        audio_path.unlink(missing_ok=True)
