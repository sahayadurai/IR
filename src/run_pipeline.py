from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fifa_kg.data_loader import load_player_stats, load_world_cup_summary
from fifa_kg.graph_builder import build_knowledge_graph


def main():
    summary = load_world_cup_summary(ROOT / 'FIFA dataset' / 'FIFA - World Cup Summary.csv')
    stats = load_player_stats(ROOT / 'FIFA2022Playerstatistics' / 'FIFA WC 2022 Players Stats.csv')
    graph = build_knowledge_graph(summary, stats)

    ttl_path = ROOT / 'fifa_kg.ttl'
    graph.serialize(destination=str(ttl_path), format='turtle')
    print(f'Graph built with {len(graph)} triples. Saved to {ttl_path}')


if __name__ == '__main__':
    main()
