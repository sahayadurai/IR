import unittest
from pathlib import Path

from src.fifa_kg.data_loader import load_world_cup_summary, load_player_stats
from src.fifa_kg.graph_builder import build_knowledge_graph


class TestKGPipeline(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]

    def test_history_summary_loads(self):
        df = load_world_cup_summary(self.root / 'FIFA dataset' / 'FIFA - World Cup Summary.csv')
        self.assertIn('YEAR', df.columns)
        self.assertGreater(len(df), 20)
        self.assertIn('Uruguay', df['CHAMPION'].tolist())

    def test_player_stats_loads(self):
        df = load_player_stats(self.root / 'FIFA2022Playerstatistics' / 'FIFA WC 2022 Players Stats.csv')
        self.assertIn('Player Name', df.columns)
        self.assertIn('Nationality', df.columns)
        self.assertGreater(len(df), 700)
        self.assertIn('Emiliano Martinez', df['Player Name'].tolist())

    def test_knowledge_graph_builds_triples(self):
        summary = load_world_cup_summary(self.root / 'FIFA dataset' / 'FIFA - World Cup Summary.csv')
        players = load_player_stats(self.root / 'FIFA2022Playerstatistics' / 'FIFA WC 2022 Players Stats.csv')
        graph = build_knowledge_graph(summary, players)
        self.assertGreater(len(graph), 20)
        self.assertTrue(any('Argentina' in str(obj) for _, _, obj in graph.triples((None, None, None)) if isinstance(obj, str)))


if __name__ == '__main__':
    unittest.main()
