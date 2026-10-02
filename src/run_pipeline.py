import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / 'src'
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fifa_kg.data_loader import (
    load_all_players,
    load_player_stats,
    load_team_standings,
    load_world_cup_appearances,
    load_world_cup_goals,
    load_world_cup_matches,
    load_world_cup_summary,
)
from fifa_kg.graph_builder import build_knowledge_graph


def dataframe_audit(df) -> dict:
    return {
        'rows': int(len(df)),
        'columns': [str(column) for column in df.columns],
        'duplicate_rows': int(df.duplicated().sum()),
        'missing_by_column': {
            str(column): int(count)
            for column, count in df.isna().sum().items()
            if count
        },
    }


def find_dataset_file(name: str) -> Path:
    candidates = [
        ROOT / 'dataset' / 'FIFA dataset' / name,
        ROOT / 'FIFA dataset' / name,
        ROOT / 'dataset' / 'FIFA2022' / name,
        ROOT / 'dataset' / 'FIFA2022Playerstatistics' / name,
        ROOT / 'FIFA2022Playerstatistics' / name,
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(f'Could not find dataset file: {name}')


def find_jfjelstul_file(name: str) -> Path:
    path = ROOT / 'dataset' / 'FIFA dataset' / 'jfjelstul' / name
    if not path.is_file():
        raise FileNotFoundError(
            f'Missing required World Cup source file: {path}. '
            'Run `python scripts/fetch_worldcup_data.py` first.'
        )
    return path


def main():
    summary_path = find_dataset_file('FIFA - World Cup Summary.csv')
    stats_path = find_dataset_file('FIFA WC 2022 Players Stats.csv')
    team_path = find_dataset_file('FIFA - 2022.csv')
    roster_path = find_dataset_file('List Of All Players Names.csv')
    matches_path = find_jfjelstul_file('matches.csv')
    goals_path = find_jfjelstul_file('goals.csv')
    appearances_path = find_jfjelstul_file('player_appearances.csv')
    image_root = ROOT / 'dataset' / 'FIFA2022' / 'Images' / 'Images'

    summary = load_world_cup_summary(summary_path)
    stats = load_player_stats(stats_path)
    teams = load_team_standings(team_path)
    roster = load_all_players(roster_path)
    matches = load_world_cup_matches(matches_path)
    goals = load_world_cup_goals(goals_path)
    appearances = load_world_cup_appearances(appearances_path)
    if not image_root.is_dir():
        raise FileNotFoundError(f'Missing required FIFA 2022 image dataset: {image_root}')

    graph = build_knowledge_graph(
        summary,
        stats,
        image_root=image_root,
        team_df=teams,
        matches_df=matches,
        goals_df=goals,
        appearances_df=appearances,
        all_players_df=roster,
    )

    ttl_path = ROOT / 'fifa_kg.ttl'
    graph.serialize(destination=str(ttl_path), format='turtle')
    image_folders = [
        path for path in image_root.rglob('Images_*') if path.is_dir()
    ]
    image_files = sum(
        1
        for player_dir in image_folders
        for path in player_dir.iterdir()
        if path.is_file() and path.suffix.casefold() in {'.jpg', '.jpeg'}
    )
    audit = {
        'preprocessing': {
            'missing_value_policy': 'Whitespace and common empty/dash markers are normalized to missing; optional facts are omitted, not rows.',
            'source_commit': 'jfjelstul/worldcup@35a8667f518b07469182ae16d35574dd0e7a00fb',
            'datasets': {
                'historical_world_cup_summary': dataframe_audit(summary),
                'fifa_2022_team_standings': dataframe_audit(teams),
                'fifa_2022_player_statistics': dataframe_audit(stats),
                'fifa_2022_player_roster': dataframe_audit(roster),
                'world_cup_2022_matches': dataframe_audit(matches),
                'world_cup_2022_goals': dataframe_audit(goals),
                'world_cup_2022_player_appearances': dataframe_audit(appearances),
            },
            'fifa_2022_images': {
                'player_folders': len(image_folders),
                'jpg_files': image_files,
                'representative_images_featured': len(image_folders),
            },
        },
        'rdf_triples': len(graph),
        'ttl_file': str(ttl_path.relative_to(ROOT)),
    }
    output_dir = ROOT / 'output'
    output_dir.mkdir(exist_ok=True)
    audit_path = output_dir / 'data_quality.json'
    audit_path.write_text(
        json.dumps(audit, indent=2, ensure_ascii=False) + '\n',
        encoding='utf-8',
    )
    print('Input coverage:')
    print(f'  tournaments: {len(summary)}')
    print(f'  2022 teams: {len(teams)}')
    print(f'  2022 player statistics: {len(stats)}')
    print(f'  2022 roster names: {len(roster)}')
    print(f'  2022 matches: {len(matches)}')
    print(f'  2022 goals: {len(goals)}')
    print(f'  2022 player appearances: {len(appearances)}')
    print(f'  image folders/files: {len(image_folders)}/{image_files}')
    print(f'Graph built with {len(graph):,} triples. Saved to {ttl_path}')
    print(f'Data quality audit saved to {audit_path}')


if __name__ == '__main__':
    main()
