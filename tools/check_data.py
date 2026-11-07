"""ROM-free checks of the published contracts, translations, graph and patch."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'source'))
from build_graph import load_graph, translations


def check():
    graph = load_graph()
    assert not graph['unknown_nodes'] and not graph['invalid_anchors']
    translated, batches = translations(graph)
    expected = {row['id'] for row in graph['literal_spans']}
    assert set(translated) == expected and len(expected) == 4768
    assert all(text.strip() for text in translated.values())
    nodes = {row['source_cpu']: row for row in graph['nodes']}
    edges = 0
    for address, node in nodes.items():
        end = address & 65535
        for token in node['tokens']:
            assert token['offset'] == end
            end += len(bytes.fromhex(token['raw']))
        for edge in node['edges']:
            assert edge['target'] in nodes
            assert edge['target'] >> 16 == address >> 16
            edges += 1
        if node['fallthrough']:
            assert node['fallthrough'] in nodes
    menus = 0
    for folder in ['zcode-menu', 'zcode-extra-menu', 'zcode-mixed-menu']:
        data = json.loads((ROOT / 'work' / folder / 'input.json').read_text(encoding='utf-8-sig'))
        out = json.loads((ROOT / 'work' / folder / 'translations.json').read_text(encoding='utf-8-sig'))
        expected_rows = {row['id']: row for row in data['entries']}
        rows = {row['id']: row for row in out['entries']}
        assert len(rows) == len(out['entries']) and set(rows) == set(expected_rows)
        assert out['source_rom_sha256'] == data['source_rom_sha256'] == graph['source_sha256']
        for key, row in rows.items():
            assert row['japanese'] == expected_rows[key]['japanese']
            assert row['translation'].strip()
        menus += len(rows)
    identity = json.loads((ROOT / 'patches/R1/identity.json').read_text(encoding='utf-8'))
    patch = (ROOT / 'patches/R1/remix4-cn.bps').read_bytes()
    assert hashlib.sha256(patch).hexdigest() == identity['patch_sha256']
    assert len(patch) == identity['patch_size'] and patch.startswith(b'BPS1')
    return {'status': 'pass', 'literal_spans': len(translated), 'graph_edges': edges,
            'menu_input_rows_including_explicit_exclusions': menus, 'translation_batches': len(batches),
            'scope': 'ROM-free data/structure checks; not a ROM build or runtime proof'}


if __name__ == '__main__':
    print(json.dumps(check(), ensure_ascii=False))
