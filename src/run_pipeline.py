from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fifa_kg.data_loader import load_player_stats, load_world_cup_summary
from fifa_kg.graph_builder import build_knowledge_graph


def find_dataset_file(name: str) -> Path:
    candidates = [
        ROOT / 'dataset' / 'FIFA dataset' / name,
        ROOT / 'FIFA dataset' / name,
        ROOT / 'dataset' / 'FIFA2022Playerstatistics' / name,
        ROOT / 'FIFA2022Playerstatistics' / name,
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(f'Could not find dataset file: {name}')


def main():
    summary_path = find_dataset_file('FIFA - World Cup Summary.csv')
    stats_path = find_dataset_file('FIFA WC 2022 Players Stats.csv')

    summary = load_world_cup_summary(summary_path)
    stats = load_player_stats(stats_path)
    graph = build_knowledge_graph(summary, stats)

    ttl_path = ROOT / 'fifa_kg.ttl'
    graph.serialize(destination=str(ttl_path), format='turtle')
    print(f'Graph built with {len(graph)} triples. Saved to {ttl_path}')


if __name__ == '__main__':
    main()
