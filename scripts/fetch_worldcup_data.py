from __future__ import annotations

import argparse
import csv
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
SOURCE_COMMIT = "35a8667f518b07469182ae16d35574dd0e7a00fb"
SOURCE_BASE = (
    "https://raw.githubusercontent.com/jfjelstul/worldcup/"
    f"{SOURCE_COMMIT}/data-csv"
)
FILES = {
    "matches.csv": {"tournament_id", "match_id", "home_team_name", "away_team_name"},
    "goals.csv": {"tournament_id", "goal_id", "match_id", "player_id"},
    "player_appearances.csv": {
        "tournament_id",
        "match_id",
        "player_id",
        "team_name",
    },
}


def fetch_worldcup_data(force: bool = False) -> list[Path]:
    destination = ROOT / "dataset" / "FIFA dataset" / "jfjelstul"
    destination.mkdir(parents=True, exist_ok=True)
    downloaded = []

    for filename, required_columns in FILES.items():
        target = destination / filename
        if target.is_file() and target.stat().st_size > 0 and not force:
            print(f"Using existing source file: {target}")
            continue

        url = f"{SOURCE_BASE}/{filename}"
        try:
            with urlopen(url, timeout=45) as response:
                content = response.read()
        except (HTTPError, URLError, TimeoutError) as exc:
            raise RuntimeError(f"Unable to download required source data from {url}: {exc}") from exc

        if not content:
            raise RuntimeError(f"The source returned an empty file: {url}")
        header = next(csv.reader(content.decode("utf-8-sig").splitlines()), [])
        if not required_columns.issubset(header):
            raise ValueError(
                f"Unexpected columns in {filename}: missing "
                f"{sorted(required_columns.difference(header))}"
            )

        temporary = target.with_suffix(target.suffix + ".part")
        temporary.write_bytes(content)
        temporary.replace(target)
        downloaded.append(target)
        print(f"Downloaded {filename} ({len(content):,} bytes)")

    return downloaded


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Fetch pinned match-level CSV sources for the FIFA 2022 KG."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace local copies with the pinned upstream files.",
    )
    args = parser.parse_args()
    fetch_worldcup_data(force=args.force)


if __name__ == "__main__":
    main()
