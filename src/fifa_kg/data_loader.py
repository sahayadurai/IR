from __future__ import annotations

from pathlib import Path

import pandas as pd


def load_world_cup_summary(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def load_player_stats(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    raw_cols = [str(c) for c in df.columns]
    df.columns = raw_cols

    # Keep original schema and provide stripped aliases for compatibility with downstream code.
    aliases = {
        'Nationality ': 'Nationality',
        'Player Name ': 'Player Name',
        'Club ': 'Club',
    }
    for old_name, new_name in aliases.items():
        if old_name in df.columns and new_name not in df.columns:
            df[new_name] = df[old_name]
    return df


def load_all_players(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df.columns = [str(c).strip() for c in df.columns]
    return df
