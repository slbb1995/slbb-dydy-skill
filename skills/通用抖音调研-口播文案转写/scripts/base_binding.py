#!/usr/bin/env python3
"""Persist client-to-Base bindings outside skill and per-chat directories.

This helper only stores local coordinates. The caller must verify the current
Feishu identity, resource access and client ownership before using a binding.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import unicodedata
from urllib.parse import urlparse


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('get', 'register'))
    parser.add_argument('--client', required=True)
    parser.add_argument('--registry-root', type=Path)
    parser.add_argument('--base-token')
    parser.add_argument('--table-id')
    parser.add_argument('--url')
    parser.add_argument('--replace', action='store_true',
                        help='Use only when the user requested changing this client target.')
    args = parser.parse_args()
    client = unicodedata.normalize('NFKC', args.client).strip()
    if not client:
        parser.error('client must not be empty')
    root = args.registry_root or Path.home() / '.local/share/slbb-dydy/bindings'
    key = hashlib.sha256(client.encode('utf-8')).hexdigest()
    path = root / (key + '.json')
    existing = None
    if path.exists():
        existing = json.loads(path.read_text(encoding='utf-8'))
        if existing.get('client') != client:
            raise ValueError('client mismatch; do not reuse this binding')
    if args.action == 'get':
        print(json.dumps({'found': existing is not None, 'binding': existing,
                          'binding_path': str(path),
                          'next_step': 'verify_remote_access_and_client' if existing else
                          'recover_existing_binding_or_search_feishu_before_creating'},
                         ensure_ascii=False))
        return
    if not args.base_token or not re.fullmatch(r'[A-Za-z0-9]+', args.base_token):
        parser.error('register requires a valid --base-token')
    if not args.table_id or not re.fullmatch(r'tbl[A-Za-z0-9]+', args.table_id):
        parser.error('register requires a valid --table-id')
    parsed = urlparse(args.url or '')
    if parsed.scheme != 'https' or parsed.path != '/base/' + args.base_token:
        parser.error('register requires the verified HTTPS Base URL')
    host = (parsed.hostname or '').lower()
    if not any(host.endswith('.' + domain) for domain in ('feishu.cn', 'larksuite.com')):
        parser.error('URL must use the verified Feishu/Lark domain')
    if existing and not args.replace and (
            existing['base_token'], existing['table_id']) != (args.base_token, args.table_id):
        parser.error('client already bound to a different table; verify user intent before --replace')
    binding = {'client': client, 'base_token': args.base_token,
               'table_id': args.table_id, 'url': args.url}
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.binding-', dir=root)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as output:
            json.dump(binding, output, ensure_ascii=False, indent=2)
            output.write('\n')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    if json.loads(path.read_text(encoding='utf-8')) != binding:
        raise ValueError('binding readback failed')
    print(json.dumps({'registered': True, 'binding': binding,
                      'binding_path': str(path)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
