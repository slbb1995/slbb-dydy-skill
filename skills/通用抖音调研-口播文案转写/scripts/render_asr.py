#!/usr/bin/env python3
"""Render the verified mediakit subtitle JSON shape without rewriting ASR text/timing."""
import argparse
import json
import math
from pathlib import Path


def build_outputs(data):
    segments = data.get('subtitles') if isinstance(data, dict) else None
    if not isinstance(segments, list) or not segments:
        raise ValueError('Expected a non-empty subtitles array from the completed tool response')
    if data.get('status') != 'completed':
        raise ValueError('ASR task is not completed')
    warnings = []
    for i, segment in enumerate(segments):
        if not isinstance(segment, dict) or not isinstance(segment.get('subtitle_text'), str):
            raise ValueError(f'Invalid segment {i + 1}')
        start, end = segment.get('start_time'), segment.get('end_time')
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in (start, end)):
            raise ValueError(f'Invalid timestamps in segment {i + 1}')
        if start < 0 or end < start:
            raise ValueError(f'Invalid interval in segment {i + 1}')
        if i and start < segments[i - 1]['end_time']:
            warnings.append({'segment': i + 1, 'reason': 'raw timestamps overlap or are out of order; preserved'})

    def stamp(seconds):
        milliseconds = round(seconds * 1000)
        hours, milliseconds = divmod(milliseconds, 3600000)
        minutes, milliseconds = divmod(milliseconds, 60000)
        seconds, milliseconds = divmod(milliseconds, 1000)
        return f'{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}'

    text = '\n'.join(s['subtitle_text'] for s in segments) + '\n'
    srt = '\n\n'.join(f"{i}\n{stamp(s['start_time'])} --> {stamp(s['end_time'])}\n{s['subtitle_text']}" for i, s in enumerate(segments, 1)) + '\n'
    rows = []
    for i, segment in enumerate(segments, 1):
        escaped = segment['subtitle_text'].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('|', '&#124;').replace('\n', '<br>')
        rows.append(f"| {i} | {segment['start_time']} | {segment['end_time']} | {escaped} |")
    md = '# 完整ASR稿（机器识别，未逐字听校）\n\n时间戳和文字直接来自工具原始结果，不合并或改写。\n\n| 段落 | 开始秒 | 结束秒 | 原始识别文字 |\n|---|---|---|---|\n' + '\n'.join(rows) + '\n'
    audit = {'task_id': data.get('task_id'), 'segment_count': len(segments),
             'first_start': segments[0]['start_time'], 'last_end': segments[-1]['end_time'],
             'raw_timing_warnings': warnings, 'text_transformation': 'none; newline separators only',
             'proof_limit': 'Preserves the tool result; does not prove ASR recognized every spoken word correctly.'}
    return {'asr-verbatim.txt': text, 'asr-segments.srt': srt, 'asr-segments.md': md,
            'asr-integrity.json': json.dumps(audit, ensure_ascii=False, indent=2) + '\n'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    try:
        outputs = build_outputs(json.loads(args.input.read_text(encoding='utf-8')))
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for name, content in outputs.items():
            target = args.output_dir / name
            if target.resolve() == args.input.resolve():
                raise ValueError('Output cannot replace the raw input')
            target.write_text(content, encoding='utf-8')
            if target.read_text(encoding='utf-8') != content:
                raise OSError(f'Readback mismatch: {target}')
    except (ValueError, OSError) as error:
        parser.exit(2, f'Cannot render ASR: {error}\n')
    print(json.dumps({'output_dir': str(args.output_dir.resolve()), 'files': list(outputs),
                      'readback': 'passed'}, ensure_ascii=False))


if __name__ == '__main__':
    main()
