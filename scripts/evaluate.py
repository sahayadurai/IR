from __future__ import annotations

import argparse
import json
import os
import unicodedata
from pathlib import Path
from statistics import median
from time import perf_counter
from typing import Any

import pandas as pd
from dotenv import load_dotenv
from neo4j import GraphDatabase, READ_ACCESS

from src.fifa_kg.data_loader import (
    load_all_players,
    load_player_stats,
    load_team_standings,
    load_world_cup_appearances,
    load_world_cup_goals,
    load_world_cup_matches,
    load_world_cup_summary,
)


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "dataset"
PLAYER_NAME = "Lionel Messi"


def _person_key(value) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii").casefold()
    return "".join(character for character in text if character.isalnum())


def _source_counts() -> dict:
    summary = load_world_cup_summary(DATASET / "FIFA dataset" / "FIFA - World Cup Summary.csv")
    teams = load_team_standings(DATASET / "FIFA dataset" / "FIFA - 2022.csv")
    players = load_player_stats(
        DATASET / "FIFA2022Playerstatistics" / "FIFA WC 2022 Players Stats.csv"
    )
    roster = load_all_players(DATASET / "FIFA2022" / "List Of All Players Names.csv")
    jfjelstul = DATASET / "FIFA dataset" / "jfjelstul"
    matches = load_world_cup_matches(jfjelstul / "matches.csv")
    goals = load_world_cup_goals(jfjelstul / "goals.csv")
    appearances = load_world_cup_appearances(jfjelstul / "player_appearances.csv")
    image_root = DATASET / "FIFA2022" / "Images" / "Images"
    image_folders = sorted(path for path in image_root.rglob("Images_*") if path.is_dir())

    goal_names = goals.apply(
        lambda row: f"{row.get('given_name', '')} {row.get('family_name', '')}".strip(),
        axis=1,
    )
    appearance_names = appearances.apply(
        lambda row: f"{row.get('given_name', '')} {row.get('family_name', '')}".strip(),
        axis=1,
    )
    player_row = players.loc[
        players["Player Name"].map(_person_key).eq(_person_key(PLAYER_NAME))
    ]
    team_row = teams.loc[teams["Team"].eq("Argentina")]
    summary_row = summary.loc[summary["YEAR"].astype(str).str.strip().eq("2022")]
    if len(player_row) != 1 or len(team_row) != 1 or len(summary_row) != 1:
        raise ValueError("Expected source records for Lionel Messi, Argentina, and FIFA 2022.")

    image_files = sum(
        1
        for player_dir in image_folders
        for path in player_dir.iterdir()
        if path.is_file() and path.suffix.casefold() in {".jpg", ".jpeg"}
    )
    return {
        "tournaments": len(summary),
        "teams_2022": len(teams),
        "player_statistics_2022": len(players),
        "roster_names_2022": len(roster),
        "matches_2022": len(matches),
        "goals_2022": len(goals),
        "player_appearances_2022": len(appearances),
        "image_folders": len(image_folders),
        "image_files": image_files,
        "champion_2022": str(summary_row.iloc[0]["CHAMPION"]),
        "argentina_points_2022": int(team_row.iloc[0]["Points"]),
        "messi_nationality": str(player_row.iloc[0]["Nationality"]),
        "messi_position": str(player_row.iloc[0]["Position"]),
        "messi_club_uri": str(player_row.iloc[0]["Club"]).strip().replace(" ", "_"),
        "messi_goals_2022": int(
            sum(_person_key(name) == _person_key(PLAYER_NAME) for name in goal_names)
        ),
        "messi_appearances_2022": int(
            sum(
                _person_key(name) == _person_key(PLAYER_NAME)
                for name in appearance_names
            )
        ),
    }


def _benchmarks(source: dict) -> list[dict]:
    return [
        {
            "name": "Historical FIFA 2022 champion",
            "dataset": "World Cup summary",
            "query": (
                "MATCH (t:Resource)-[:hasChampion]->(v:Literal) "
                "WHERE t.uri ENDS WITH '/Tournament/2022' "
                "RETURN v.value AS champion"
            ),
            "expected": [{"champion": source["champion_2022"]}],
        },
        {
            "name": "Argentina tournament points",
            "dataset": "FIFA 2022 team standings",
            "query": (
                "MATCH (team:Resource)-[:hasTournamentStatistics]->(stats:Resource)"
                "-[:inTournament]->(t:Resource), "
                "(stats)-[:hasPoints]->(points:Literal) "
                "WHERE t.uri ENDS WITH '/Tournament/2022' "
                "AND team.uri ENDS WITH '/Team/Argentina' "
                "RETURN toInteger(points.value) AS points"
            ),
            "expected": [{"points": source["argentina_points_2022"]}],
        },
        {
            "name": "Player profile and club",
            "dataset": "FIFA 2022 player statistics",
            "query": (
                "MATCH (p:Resource)-[:hasName]->(n:Literal) "
                "WHERE n.value = 'Lionel Messi' "
                "OPTIONAL MATCH (p)-[:hasNationality]->(country:Literal) "
                "OPTIONAL MATCH (p)-[:hasPosition]->(position:Literal) "
                "OPTIONAL MATCH (p)-[:playsForClub]->(club:Resource) "
                "RETURN collect(DISTINCT country.value) AS nationality, "
                "collect(DISTINCT position.value) AS position, "
                "collect(DISTINCT replace(club.uri, "
                "'http://example.org/fifa/Club/', '')) AS club"
            ),
            "expected": [
                {
                    "nationality": [source["messi_nationality"]],
                    "position": [source["messi_position"]],
                    "club": [source["messi_club_uri"]],
                }
            ],
        },
        {
            "name": "FIFA 2022 match coverage",
            "dataset": "jfjelstul matches.csv",
            "query": (
                "MATCH (m:Resource)-[:matchOf]->(t:Resource) "
                "WHERE t.uri ENDS WITH '/Tournament/2022' "
                "RETURN count(DISTINCT m) AS matches"
            ),
            "expected": [{"matches": source["matches_2022"]}],
        },
        {
            "name": "Lionel Messi goal events",
            "dataset": "jfjelstul goals.csv",
            "query": (
                "MATCH (m:Resource)-[:matchOf]->(t:Resource), "
                "(m)-[:hasGoal]->(g:Resource)-[:scoredBy]->(p:Resource), "
                "(p)-[:hasName]->(n:Literal) "
                "WHERE n.value = 'Lionel Messi' "
                "AND t.uri ENDS WITH '/Tournament/2022' "
                "RETURN count(DISTINCT g) AS goals"
            ),
            "expected": [{"goals": source["messi_goals_2022"]}],
        },
        {
            "name": "Lionel Messi match appearances",
            "dataset": "jfjelstul player_appearances.csv",
            "query": (
                "MATCH (a:Resource)-[:appearanceOf]->(p:Resource), "
                "(p)-[:hasName]->(n:Literal) "
                "WHERE n.value = 'Lionel Messi' "
                "AND a.uri CONTAINS '/Appearance/' "
                "RETURN count(DISTINCT a) AS appearances"
            ),
            "expected": [{"appearances": source["messi_appearances_2022"]}],
        },
        {
            "name": "Player image feature coverage",
            "dataset": "FIFA 2022 all-player images",
            "query": (
                "MATCH (image:Resource)-[:hasColorHistogramRgb8]->(feature:Literal) "
                "WITH DISTINCT image "
                "OPTIONAL MATCH (image)-[:hasImageCount]->(files:Literal) "
                "RETURN count(DISTINCT image) AS images, "
                "sum(toInteger(files.value)) AS source_files"
            ),
            "expected": [
                {
                    "images": source["image_folders"],
                    "source_files": source["image_files"],
                }
            ],
        },
    ]


def _canonical_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def normalize(value: Any) -> Any:
        if isinstance(value, list):
            return sorted((normalize(item) for item in value), key=lambda item: json.dumps(item, sort_keys=True))
        if isinstance(value, dict):
            return {key: normalize(value[key]) for key in sorted(value)}
        return value

    normalized: list[dict[str, Any]] = [normalize(row) for row in rows]
    return sorted(normalized, key=lambda row: json.dumps(row, sort_keys=True))


def evaluate(output: Path, repeats: int = 5) -> dict:
    load_dotenv(ROOT / ".env")
    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        auth=(
            os.getenv("NEO4J_USER", "neo4j"),
            os.getenv("NEO4J_PASSWORD", "fifa2022"),
        ),
    )
    source = _source_counts()
    results = []
    try:
        with driver.session(
            database=os.getenv("NEO4J_DATABASE") or None,
            default_access_mode=READ_ACCESS,
        ) as session:
            for benchmark in _benchmarks(source):
                session.run(benchmark["query"]).consume()
                durations = []
                actual = []
                for _ in range(repeats):
                    started = perf_counter()
                    actual = session.run(benchmark["query"]).data()
                    durations.append((perf_counter() - started) * 1000)
                expected = _canonical_rows(benchmark["expected"])
                returned = _canonical_rows(actual)
                results.append(
                    {
                        **benchmark,
                        "returned": returned,
                        "correct": returned == expected,
                        "median_response_ms": round(median(durations), 3),
                        "repeats": repeats,
                    }
                )
    finally:
        driver.close()

    report = {
        "project": "FIFA World Cup 2022 Multimedia Knowledge Graph",
        "evaluation_method": (
            "Neo4j read-only queries; one warm-up followed by repeated runs; "
            "median wall-clock latency reported."
        ),
        "source_counts": source,
        "results": results,
        "all_correct": all(result["correct"] for result in results),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run reproducible read-only Neo4j benchmarks.")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "output" / "evaluation.json",
        help="Evaluation JSON output path.",
    )
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be at least 1.")

    report = evaluate(args.output, repeats=args.repeats)
    for result in report["results"]:
        status = "PASS" if result["correct"] else "FAIL"
        print(
            f"{status:4} | {result['median_response_ms']:>9.3f} ms | "
            f"{result['name']}: expected={result['expected']} returned={result['returned']}"
        )
    print(f"Saved benchmark results to {args.output}")
    if not report["all_correct"]:
        raise SystemExit("One or more benchmark results do not match the source data.")


if __name__ == "__main__":
    main()
