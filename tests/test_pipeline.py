from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd
from PIL import Image
from rdflib import Literal, URIRef

from src.fifa_kg.data_loader import (
    load_player_stats,
    load_world_cup_matches,
    load_world_cup_summary,
)
from src.fifa_kg.graph_builder import NS, build_knowledge_graph


class TestKGPipeline(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parents[1]

    def test_history_summary_loads_and_cleans_columns(self):
        df = load_world_cup_summary(
            self.root / "dataset" / "FIFA dataset" / "FIFA - World Cup Summary.csv"
        )
        self.assertIn("YEAR", df.columns)
        self.assertGreater(len(df), 20)
        self.assertIn("Uruguay", df["CHAMPION"].tolist())

    def test_player_statistics_normalize_columns_and_missing_values(self):
        df = load_player_stats(
            self.root
            / "dataset"
            / "FIFA2022Playerstatistics"
            / "FIFA WC 2022 Players Stats.csv"
        )
        self.assertIn("Player Name", df.columns)
        self.assertIn("Nationality", df.columns)
        self.assertGreater(len(df), 700)
        self.assertIn("Emiliano Martinez", df["Player Name"].tolist())
        self.assertEqual(df.columns.tolist(), [column.strip() for column in df.columns])
        self.assertTrue(df.isna().any().any())

    def test_match_loader_filters_by_stable_tournament_id(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            path = Path(temporary_dir) / "matches.csv"
            path.write_text(
                "tournament_id,match_id, match_name \n"
                "WC-2018,M-2018-01,Old match\n"
                "WC-2022,M-2022-01,  Argentina vs France  \n",
                encoding="utf-8",
            )
            matches = load_world_cup_matches(path)
        self.assertEqual(matches["match_id"].tolist(), ["M-2022-01"])
        self.assertEqual(matches["match_name"].tolist(), ["Argentina vs France"])

    def test_graph_builds_typed_facts_and_match_event_links(self):
        summary = pd.DataFrame(
            [
                {
                    "YEAR": 2022,
                    "HOST": "Qatar",
                    "CHAMPION": "Argentina",
                    "RUNNER UP": "France",
                    "THIRD PLACE": "Croatia",
                    "TEAMS": 32,
                    "MATCHES PLAYED": 64,
                    "GOALS SCORED": 172,
                    "AVG GOALS PER GAME": 2.69,
                }
            ]
        )
        players = pd.DataFrame(
            [
                {
                    "Player Name": "Lionel Messi",
                    "Nationality": "Argentina",
                    "Position": "Forward",
                    "Club": "Paris Saint-Germain",
                    "Goals Scored": 7,
                    "Save Percentage": "50%",
                }
            ]
        )
        teams = pd.DataFrame(
            [
                {
                    "Position": 1,
                    "Team": "Argentina",
                    "Games Played": 7,
                    "Win": 6,
                    "Draw": 0,
                    "Loss": 1,
                    "Goals For": 15,
                    "Goals Against": 8,
                    "Goal Difference": 7,
                    "Points": 18,
                }
            ]
        )
        matches = pd.DataFrame(
            [
                {
                    "match_id": "M-2022-01",
                    "match_name": "Argentina vs France",
                    "stage_name": "final",
                    "group_name": None,
                    "match_date": "2022-12-18",
                    "match_time": "18:00",
                    "score": "3–3",
                    "home_team_score": 3,
                    "away_team_score": 3,
                    "result": "draw",
                    "extra_time": 1,
                    "penalty_shootout": 1,
                    "score_penalties": "4-2",
                    "home_team_name": "Argentina",
                    "away_team_name": "France",
                    "stadium_id": "S-001",
                    "stadium_name": "Lusail Stadium",
                    "city_name": "Lusail",
                    "country_name": "Qatar",
                }
            ]
        )
        goals = pd.DataFrame(
            [
                {
                    "goal_id": "G-0001",
                    "match_id": "M-2022-01",
                    "given_name": "Lionel",
                    "family_name": "Messi",
                    "player_id": "P-0001",
                    "minute_regulation": 23,
                    "minute_stoppage": 0,
                    "match_period": "first half",
                    "own_goal": 0,
                    "penalty": 1,
                    "team_name": "Argentina",
                }
            ]
        )
        appearances = pd.DataFrame(
            [
                {
                    "match_id": "M-2022-01",
                    "player_id": "P-0001",
                    "given_name": "Lionel",
                    "family_name": "Messi",
                    "shirt_number": 10,
                    "position_name": "forward",
                    "starter": 1,
                    "substitute": 0,
                    "team_name": "Argentina",
                }
            ]
        )

        graph = build_knowledge_graph(
            summary,
            players,
            team_df=teams,
            matches_df=matches,
            goals_df=goals,
            appearances_df=appearances,
        )

        tournament = URIRef("http://example.org/fifa/Tournament/2022")
        match = URIRef("http://example.org/fifa/Match/M-2022-01")
        goal = URIRef("http://example.org/fifa/Goal/G-0001")
        player = URIRef("http://example.org/fifa/Player/Lionel_Messi")
        self.assertIn((tournament, NS.hasChampion, Literal("Argentina")), graph)
        self.assertIn((match, NS.hasGoal, goal), graph)
        self.assertIn((goal, NS.scoredBy, player), graph)
        self.assertIn((match, NS.hasHomeTeamGoals, Literal(3)), graph)
        self.assertIn((player, NS.hasSavePercentage, Literal(0.5)), graph)
        self.assertIn((player, NS.hasNationality, Literal("Argentina")), graph)
        self.assertIn((player, NS.wasDerivedFrom, URIRef(
            "http://example.org/fifa/Dataset/FIFA2022PlayerStatistics"
        )), graph)

    def test_representative_image_has_normalized_color_feature(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            image_root = Path(temporary_dir) / "Images"
            player_dir = image_root / "Group A" / "Images_Lionel Messi"
            player_dir.mkdir(parents=True)
            Image.new("RGB", (20, 10), (255, 0, 0)).save(player_dir / "sample.jpg")

            graph = build_knowledge_graph(
                pd.DataFrame(),
                pd.DataFrame(),
                image_root=image_root,
            )

        image = URIRef("http://example.org/fifa/Image/Lionel_Messi")
        features_literal = graph.value(image, NS.hasColorHistogramRgb8)
        self.assertIsNotNone(features_literal)
        features = json.loads(str(features_literal))
        self.assertEqual(len(features), 24)
        self.assertAlmostEqual(sum(features[:8]), 1.0)
        self.assertAlmostEqual(sum(features[8:16]), 1.0)
        self.assertAlmostEqual(sum(features[16:]), 1.0)


if __name__ == "__main__":
    unittest.main()
