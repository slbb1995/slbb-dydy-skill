#!/usr/bin/env python3
"""Check candidate records, not the truth of their evidence. No network or writes."""
import argparse
import json
import math
import re
from pathlib import Path
from urllib.parse import urlsplit


def check_candidates(data, max_seconds=90):
    if isinstance(max_seconds, bool) or not isinstance(max_seconds, (int, float)) or not math.isfinite(max_seconds) or max_seconds <= 0:
        raise ValueError('max_seconds must be a positive finite number')
    if not isinstance(data, dict) or not isinstance(data.get('candidates'), list):
        raise ValueError('Expected an object with candidates array')
    eligible, pending, seen = [], [], set()
    for index, candidate in enumerate(data['candidates'], 1):
        errors = []
        if not isinstance(candidate, dict):
            pending.append({'index': index, 'errors': ['candidate is not an object']})
            continue
        vid = candidate.get('video_id')
        if not isinstance(vid, str) or not re.fullmatch(r'\d+', vid):
            errors.append('missing verified numeric video_id')
        elif vid in seen:
            errors.append('duplicate video_id')
        else:
            seen.add(vid)
        try:
            url = urlsplit(candidate.get('url', ''))
            allowed = url.scheme == 'https' and url.hostname in {'www.douyin.com', 'douyin.com', 'www.iesdouyin.com', 'iesdouyin.com'}
            expected = f'/share/video/{vid}' if url.hostname in {'www.iesdouyin.com', 'iesdouyin.com'} else f'/video/{vid}'
            if not allowed or url.path.rstrip('/') != expected:
                errors.append('source URL does not match video_id')
        except (TypeError, ValueError, AttributeError):
            errors.append('invalid source URL')
        for field in ('title', 'author', 'duration_evidence', 'content_evidence', 'suggested_topic', 'observation_scope'):
            if not isinstance(candidate.get(field), str) or not candidate[field].strip():
                errors.append(f'missing {field}')
        if isinstance(candidate.get('author'), str) and any(word in candidate['author'] for word in ('未读', '未在', '未知', '待核验', '缺失')):
            errors.append('author field contains an unknown placeholder')
        if candidate.get('identity_verified') is not True:
            errors.append('identity not verified')
        duration = candidate.get('duration_seconds')
        if isinstance(duration, bool) or not isinstance(duration, (float, int)) or not math.isfinite(duration) or duration <= 0:
            errors.append('missing measured duration')
        elif duration > max_seconds:
            errors.append(f'duration exceeds {max_seconds}s')
        if candidate.get('duration_source') not in {'player', 'tool_duration'}:
            errors.append('duration is not from player/tool duration')
        if candidate.get('content_source') not in {'video_observation', 'verified_subtitles', 'video_understanding'}:
            errors.append('content source is not verified video content')
        methods = {'video_observation': {'browser_screenshot', 'video_reader'}, 'video_understanding': {'video_reader'}, 'verified_subtitles': {'subtitle_read'}}
        if candidate.get('observation_method') not in methods.get(candidate.get('content_source'), set()):
            errors.append('observation method does not support content source')
        if errors:
            pending.append({'index': index, 'video_id': vid, 'errors': errors})
        else:
            eligible.append(vid)
    return {'eligible_ids': eligible, 'eligible_count': len(eligible), 'pending_or_excluded': pending,
            'note': 'Record checks only; real evidence must have been observed.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--max-seconds', type=float, default=90)
    args = parser.parse_args()
    try:
        result = check_candidates(json.loads(args.input.read_text(encoding='utf-8')), args.max_seconds)
    except (ValueError, OSError) as error:
        parser.exit(2, f'Invalid input: {error}\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
