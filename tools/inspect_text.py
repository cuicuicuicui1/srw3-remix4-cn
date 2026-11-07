"""Inspect original Japanese and accepted Chinese by span ID or CPU address."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'source'))
from build_graph import load_graph, translations


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument('--id', help='Literal/name ID from an input.json')
    selector.add_argument('--address', help='CPU address, e.g. 08:8000')
    args = parser.parse_args()
    graph = load_graph()
    chinese, _ = translations(graph)
    address = int(args.address.replace(':', ''), 16) if args.address else None
    spans = [dict(row, accepted_chinese=chinese.get(row['id'])) for row in graph['literal_spans']
             if row['id'] == args.id or (address is not None and
                (address in row.get('hosts', []) or row.get('source_cpu') == address))]
    hosts = {host for row in spans for host in row.get('hosts', [])}
    if address is not None:
        hosts.add(address)
    nodes = [row for row in graph['nodes'] if row['source_cpu'] in hosts]
    incoming = [{'from': row['source_cpu'], **edge} for row in graph['nodes']
                for edge in row['edges'] if edge['target'] in hosts]
    print(json.dumps({'spans': spans, 'nodes': nodes, 'incoming': incoming}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
