from __future__ import annotations

from pathlib import Path

import pandas as pd


MISSING_VALUES = {"", "-", "--", "—", "n/a", "na", "null", "none"}


def _read_clean_csv(path: str | Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    columns = [str(column).strip() for column in df.columns]
    if len(columns) != len(set(columns)):
        raise ValueError(f"Column names are duplicated after whitespace cleanup: {path}")
    df.columns = columns

    for column in df.select_dtypes(include=["object", "string"]).columns:
        values = df[column].map(lambda value: value.strip() if isinstance(value, str) else value)
        missing = values.map(
            lambda value: isinstance(value, str) and value.casefold() in MISSING_VALUES
        )
        df[column] = values.mask(missing, pd.NA)
    return df


def _read_tournament_rows(path: str | Path, tournament_id: str) -> pd.DataFrame:
    df = _read_clean_csv(path)
    if "tournament_id" not in df.columns:
        raise ValueError(f"Dataset is missing the tournament_id column: {path}")
    return df.loc[df["tournament_id"].eq(tournament_id)].copy()


def load_world_cup_summary(path: str | Path) -> pd.DataFrame:
    return _read_clean_csv(path)


def load_player_stats(path: str | Path) -> pd.DataFrame:
    return _read_clean_csv(path)


def load_all_players(path: str | Path) -> pd.DataFrame:
    df = _read_clean_csv(path)
    if "Unnamed: 0" in df.columns:
        df = df.rename(columns={"Unnamed: 0": "source_index"})
    return df


def load_team_standings(path: str | Path) -> pd.DataFrame:
    return _read_clean_csv(path)


def load_world_cup_matches(path: str | Path) -> pd.DataFrame:
    return _read_tournament_rows(path, "WC-2022")


def load_world_cup_goals(path: str | Path) -> pd.DataFrame:
    return _read_tournament_rows(path, "WC-2022")


def load_world_cup_appearances(path: str | Path) -> pd.DataFrame:
    return _read_tournament_rows(path, "WC-2022")
