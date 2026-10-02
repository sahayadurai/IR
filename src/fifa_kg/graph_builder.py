from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import quote

import pandas as pd
from PIL import Image
from rdflib import Graph, Literal, Namespace, RDF, URIRef


NS = Namespace("http://example.org/fifa/")
ONTOLOGY = Namespace("http://example.org/fifa/ontology/")

PLAYER_PROPERTIES = {
    "Nationality": "hasNationality",
    "FIFA Ranking": "hasFifaRanking",
    "National Team Kit Sponsor": "hasNationalTeamKitSponsor",
    "Position": "hasPosition",
    "National Team Jersey Number": "hasJerseyNumber",
    "Player DOB": "dateOfBirth",
    "Appearances": "hasAppearances",
    "Goals Scored": "hasGoalsScored",
    "Assists Provided": "hasAssistsProvided",
    "Dribbles per 90": "hasDribblesPer90",
    "Interceptions per 90": "hasInterceptionsPer90",
    "Tackles per 90": "hasTacklesPer90",
    "Total Duels Won per 90": "hasTotalDuelsWonPer90",
    "Save Percentage": "hasSavePercentage",
    "Clean Sheets": "hasCleanSheets",
    "Brand Sponsor/Brand Used": "hasBrandSponsor",
}

TEAM_PROPERTIES = {
    "Position": "hasStandingPosition",
    "Games Played": "hasGamesPlayed",
    "Win": "hasWins",
    "Draw": "hasDraws",
    "Loss": "hasLosses",
    "Goals For": "hasGoalsFor",
    "Goals Against": "hasGoalsAgainst",
    "Goal Difference": "hasGoalDifference",
    "Points": "hasPoints",
}


def _value(value):
    if value is None or pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def _uri(category: str, key: object) -> URIRef:
    normalized = str(key).strip().replace(" ", "_")
    if not normalized:
        raise ValueError(f"Cannot create a {category} URI from an empty identifier.")
    return URIRef(f"{NS}{category}/{quote(normalized, safe='._-')}")


def _add_entity(graph: Graph, entity: URIRef, entity_type: str) -> URIRef:
    graph.add((entity, RDF.type, ONTOLOGY[entity_type]))
    return entity


def _add_fact(graph: Graph, subject: URIRef, predicate: str, value) -> None:
    value = _value(value)
    if value is not None:
        graph.add((subject, NS[predicate], Literal(value)))


def _add_source(graph: Graph, entity: URIRef, source: URIRef) -> None:
    graph.add((entity, NS["wasDerivedFrom"], source))


def _source(graph: Graph, name: str) -> URIRef:
    source = _add_entity(graph, _uri("Dataset", name), "Dataset")
    _add_fact(graph, source, "datasetName", name)
    return source


def _number(value):
    value = _value(value)
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        is_percent = value.endswith("%")
        text = value[:-1].strip() if is_percent else value.replace(",", "").strip()
        try:
            number = float(text)
        except ValueError:
            return value
        if is_percent:
            number /= 100
    else:
        number = float(value)
    if number.is_integer():
        return int(number)
    return number


def _person_key(name: object) -> str:
    value = _value(name)
    if value is None:
        return ""
    folded = unicodedata.normalize("NFKD", str(value))
    ascii_text = folded.encode("ascii", "ignore").decode("ascii").casefold()
    return "".join(character for character in ascii_text if character.isalnum())


def _person_name(given_name, family_name) -> str | None:
    parts = [
        str(value)
        for value in (_value(given_name), _value(family_name))
        if _value(value) and str(value).casefold() != "not applicable"
    ]
    return " ".join(parts) or None


def _image_features(path: Path) -> tuple[int, int, list[float]]:
    with Image.open(path) as original:
        width, height = original.size
        thumbnail = original.convert("RGB").resize((64, 64))
        histogram = thumbnail.histogram()

    pixels = 64 * 64
    bins = []
    for channel in range(3):
        channel_histogram = histogram[channel * 256 : (channel + 1) * 256]
        for bin_index in range(8):
            start = bin_index * 32
            bins.append(round(sum(channel_histogram[start : start + 32]) / pixels, 6))
    return width, height, bins


def build_knowledge_graph(
    summary_df: pd.DataFrame,
    player_df: pd.DataFrame,
    image_root: str | Path | None = None,
    *,
    team_df: pd.DataFrame | None = None,
    matches_df: pd.DataFrame | None = None,
    goals_df: pd.DataFrame | None = None,
    appearances_df: pd.DataFrame | None = None,
    all_players_df: pd.DataFrame | None = None,
) -> Graph:
    graph = Graph()
    graph.bind("fifa", NS)
    graph.bind("fifa-ontology", ONTOLOGY)

    summary_source = _source(graph, "WorldCupSummary")
    team_source = _source(graph, "FIFA2022TeamStandings") if team_df is not None else None
    player_source = _source(graph, "FIFA2022PlayerStatistics")
    roster_source = _source(graph, "FIFA2022PlayerRoster") if all_players_df is not None else None
    match_source = _source(graph, "FIFAWorldCupMatches") if matches_df is not None else None
    goal_source = _source(graph, "FIFAWorldCupGoals") if goals_df is not None else None
    appearance_source = (
        _source(graph, "FIFAWorldCupPlayerAppearances")
        if appearances_df is not None
        else None
    )

    tournament_2022 = _uri("Tournament", "2022")
    team_uris: dict[str, URIRef] = {}
    player_uris: dict[str, list[URIRef]] = {}

    def team_uri(name) -> URIRef | None:
        value = _value(name)
        if value is None:
            return None
        key = str(value).casefold()
        if key not in team_uris:
            entity = _add_entity(graph, _uri("Team", value), "Team")
            team_uris[key] = entity
        return team_uris[key]

    def player_uri(name, source_id=None) -> URIRef | None:
        value = _value(name)
        if value is None:
            return _uri("PlayerSource", source_id) if _value(source_id) is not None else None
        matches = player_uris.get(_person_key(value), [])
        if len(matches) == 1:
            return matches[0]
        return _uri("Player", value)

    for _, row in summary_df.iterrows():
        year = _value(row.get("YEAR"))
        if year is None:
            continue
        tournament = _add_entity(graph, _uri("Tournament", year), "Tournament")
        for field, predicate in (
            ("HOST", "hasHost"),
            ("CHAMPION", "hasChampion"),
            ("RUNNER UP", "hasRunnerUp"),
            ("THIRD PLACE", "hasThirdPlace"),
            ("TEAMS", "hasTeamCount"),
            ("MATCHES PLAYED", "hasMatchCount"),
            ("GOALS SCORED", "hasGoalCount"),
            ("AVG GOALS PER GAME", "hasAverageGoalsPerGame"),
        ):
            value = _value(row.get(field))
            if value is not None:
                if field in {"TEAMS", "MATCHES PLAYED", "GOALS SCORED", "AVG GOALS PER GAME"}:
                    value = _number(value)
                _add_fact(graph, tournament, predicate, value)
        for field, predicate in (
            ("CHAMPION", "hasChampionTeam"),
            ("RUNNER UP", "hasRunnerUpTeam"),
        ):
            entity = team_uri(row.get(field))
            if entity is not None:
                graph.add((tournament, NS[predicate], entity))
                _add_source(graph, entity, summary_source)
        host = team_uri(row.get("HOST"))
        if host is not None:
            graph.add((tournament, NS["hostedIn"], host))
        _add_source(graph, tournament, summary_source)

    if team_df is not None:
        assert team_source is not None
        for _, row in team_df.iterrows():
            entity = team_uri(row.get("Team"))
            if entity is None:
                continue
            stats = _add_entity(
                graph,
                _uri("TeamTournamentStatistics", f"2022/{row.get('Team')}"),
                "TeamTournamentStatistics",
            )
            graph.add((entity, NS["hasTournamentStatistics"], stats))
            graph.add((stats, NS["inTournament"], tournament_2022))
            for field, predicate in TEAM_PROPERTIES.items():
                value = _number(row.get(field))
                _add_fact(graph, stats, predicate, value)
            _add_source(graph, entity, team_source)
            _add_source(graph, stats, team_source)
            _add_fact(graph, entity, "hasCountryName", row.get("Team"))

    for _, row in player_df.iterrows():
        name = _value(row.get("Player Name"))
        if name is None:
            continue
        player = _add_entity(graph, _uri("Player", name), "Player")
        key = _person_key(name)
        if player not in player_uris.setdefault(key, []):
            player_uris[key].append(player)
        _add_fact(graph, player, "hasName", name)
        _add_source(graph, player, player_source)

        for field, predicate in PLAYER_PROPERTIES.items():
            value = _value(row.get(field))
            if value is None:
                continue
            if field in {
                "FIFA Ranking",
                "National Team Jersey Number",
                "Appearances",
                "Goals Scored",
                "Assists Provided",
                "Dribbles per 90",
                "Interceptions per 90",
                "Tackles per 90",
                "Total Duels Won per 90",
                "Save Percentage",
                "Clean Sheets",
            }:
                value = _number(value)
            _add_fact(graph, player, predicate, value)

        club = _value(row.get("Club"))
        if club is not None:
            club_entity = _add_entity(graph, _uri("Club", club), "Club")
            graph.add((player, NS["playsForClub"], club_entity))
            _add_source(graph, club_entity, player_source)
        country = team_uri(row.get("Nationality"))
        if country is not None:
            graph.add((player, NS["representsTeam"], country))

    if all_players_df is not None:
        assert roster_source is not None
        for _, row in all_players_df.iterrows():
            name = _value(row.get("Name_Player"))
            if name is None:
                continue
            entity = player_uri(name)
            if entity is None:
                continue
            _add_entity(graph, entity, "Player")
            _add_fact(graph, entity, "hasName", name)
            _add_source(graph, entity, roster_source)
            _add_fact(graph, entity, "hasSourceIndex", _number(row.get("source_index")))
            key = _person_key(name)
            if entity not in player_uris.setdefault(key, []):
                player_uris[key].append(entity)

    if matches_df is not None:
        assert match_source is not None
        for _, row in matches_df.iterrows():
            match_id = _value(row.get("match_id"))
            if match_id is None:
                continue
            match = _add_entity(graph, _uri("Match", match_id), "Match")
            _add_source(graph, match, match_source)
            _add_fact(graph, match, "hasMatchName", row.get("match_name"))
            _add_fact(graph, match, "hasStage", row.get("stage_name"))
            _add_fact(graph, match, "hasGroup", row.get("group_name"))
            _add_fact(graph, match, "hasMatchDate", row.get("match_date"))
            _add_fact(graph, match, "hasMatchTime", row.get("match_time"))
            _add_fact(graph, match, "hasScore", row.get("score"))
            _add_fact(graph, match, "hasHomeTeamGoals", _number(row.get("home_team_score")))
            _add_fact(graph, match, "hasAwayTeamGoals", _number(row.get("away_team_score")))
            _add_fact(graph, match, "hasResult", row.get("result"))
            _add_fact(graph, match, "hasExtraTime", _number(row.get("extra_time")))
            _add_fact(
                graph,
                match,
                "hasPenaltyShootout",
                _number(row.get("penalty_shootout")),
            )
            _add_fact(graph, match, "hasPenaltyScore", row.get("score_penalties"))
            _add_fact(graph, match, "hasSourceMatchId", match_id)
            graph.add((match, NS["matchOf"], tournament_2022))

            for name_field, relation in (
                ("home_team_name", "homeTeam"),
                ("away_team_name", "awayTeam"),
            ):
                team = team_uri(row.get(name_field))
                if team is not None:
                    graph.add((match, NS[relation], team))

            stadium_id = _value(row.get("stadium_id"))
            stadium_name = _value(row.get("stadium_name"))
            if stadium_id is not None or stadium_name is not None:
                venue = _add_entity(
                    graph,
                    _uri("Venue", stadium_id or stadium_name),
                    "Venue",
                )
                graph.add((match, NS["playedAt"], venue))
                _add_fact(graph, venue, "hasVenueName", stadium_name)
                _add_fact(graph, venue, "hasCity", row.get("city_name"))
                _add_fact(graph, venue, "hasCountry", row.get("country_name"))
                _add_source(graph, venue, match_source)

    if goals_df is not None:
        assert goal_source is not None
        for _, row in goals_df.iterrows():
            goal_id = _value(row.get("goal_id"))
            match_id = _value(row.get("match_id"))
            if goal_id is None or match_id is None:
                continue
            goal = _add_entity(graph, _uri("Goal", goal_id), "Goal")
            match = _uri("Match", match_id)
            graph.add((match, NS["hasGoal"], goal))
            _add_fact(graph, goal, "hasMinute", _number(row.get("minute_regulation")))
            _add_fact(graph, goal, "hasStoppageMinute", _number(row.get("minute_stoppage")))
            _add_fact(graph, goal, "hasMatchPeriod", row.get("match_period"))
            _add_fact(graph, goal, "isOwnGoal", _number(row.get("own_goal")))
            _add_fact(graph, goal, "isPenalty", _number(row.get("penalty")))
            _add_source(graph, goal, goal_source)

            scorer_name = _person_name(row.get("given_name"), row.get("family_name"))
            scorer = player_uri(scorer_name, row.get("player_id"))
            if scorer is not None:
                _add_entity(graph, scorer, "Player")
                _add_fact(graph, scorer, "hasName", scorer_name)
                _add_fact(graph, scorer, "hasSourcePlayerId", row.get("player_id"))
                graph.add((goal, NS["scoredBy"], scorer))
            team = team_uri(row.get("team_name"))
            if team is not None:
                graph.add((goal, NS["forTeam"], team))

    if appearances_df is not None:
        assert appearance_source is not None
        for _, row in appearances_df.iterrows():
            match_id = _value(row.get("match_id"))
            player_id = _value(row.get("player_id"))
            if match_id is None or player_id is None:
                continue
            name = _person_name(row.get("given_name"), row.get("family_name"))
            player = player_uri(name, player_id)
            if player is None:
                continue
            _add_entity(graph, player, "Player")
            _add_fact(graph, player, "hasName", name)
            _add_fact(graph, player, "hasSourcePlayerId", player_id)
            appearance = _add_entity(
                graph,
                _uri("Appearance", f"{match_id}/{player_id}"),
                "Appearance",
            )
            graph.add((appearance, NS["appearanceOf"], player))
            graph.add((appearance, NS["appearanceIn"], _uri("Match", match_id)))
            _add_fact(graph, appearance, "hasShirtNumber", _number(row.get("shirt_number")))
            _add_fact(graph, appearance, "hasPosition", row.get("position_name"))
            _add_fact(graph, appearance, "isStarter", _number(row.get("starter")))
            _add_fact(graph, appearance, "isSubstitute", _number(row.get("substitute")))
            team = team_uri(row.get("team_name"))
            if team is not None:
                graph.add((appearance, NS["playedFor"], team))
            _add_source(graph, appearance, appearance_source)

    if image_root:
        image_root_path = Path(image_root)
        image_source = _source(graph, "FIFA2022PlayerImages")
        for player_dir in sorted(image_root_path.rglob("Images_*")):
            if not player_dir.is_dir():
                continue
            image_files = sorted(
                path
                for path in player_dir.iterdir()
                if path.is_file() and path.suffix.casefold() in {".jpg", ".jpeg"}
            )
            if not image_files:
                continue

            folder_name = re.sub(r"\s*\([^)]*\)\s*$", "", player_dir.name.removeprefix("Images_"))
            player = player_uri(folder_name)
            if player is None:
                continue
            _add_entity(graph, player, "Player")
            _add_fact(graph, player, "hasName", folder_name)
            image = _add_entity(graph, _uri("Image", folder_name), "Image")
            graph.add((player, NS["hasImage"], image))
            representative = image_files[0]
            width, height, features = _image_features(representative)
            relative_path = representative.relative_to(image_root_path).as_posix()
            _add_fact(graph, image, "hasFileName", relative_path)
            _add_fact(graph, image, "hasImageCount", len(image_files))
            _add_fact(graph, image, "hasImageWidth", width)
            _add_fact(graph, image, "hasImageHeight", height)
            _add_fact(graph, image, "hasColorHistogramRgb8", json.dumps(features))
            _add_fact(graph, image, "hasFeatureExtractor", "RGB histogram, 8 bins/channel")
            _add_source(graph, image, image_source)

    return graph
