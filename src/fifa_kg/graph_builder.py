from __future__ import annotations

from rdflib import Graph, Literal, Namespace, URIRef


def build_knowledge_graph(summary_df, player_df):
    ns = Namespace('http://example.org/fifa/')
    g = Graph()

    for _, row in summary_df.head(20).iterrows():
        year = str(row['YEAR']).strip()
        champion = str(row['CHAMPION']).strip()
        runner_up = str(row['RUNNER UP']).strip()
        host = str(row['HOST']).strip()

        tournament = URIRef(f'{ns}Tournament/{year}')
        g.add((tournament, ns['hasHost'], Literal(host)))
        g.add((tournament, ns['hasChampion'], Literal(champion)))
        g.add((tournament, ns['hasRunnerUp'], Literal(runner_up)))

        champion_team = URIRef(f'{ns}Team/{champion.replace(" ", "_")}')
        runner_team = URIRef(f'{ns}Team/{runner_up.replace(" ", "_")}')
        host_team = URIRef(f'{ns}Team/{host.replace(" ", "_")}')
        g.add((tournament, ns['hasChampionTeam'], champion_team))
        g.add((tournament, ns['hasRunnerUpTeam'], runner_team))
        g.add((tournament, ns['hostedIn'], host_team))

    for _, row in player_df.head(100).iterrows():
        nationality = str(row.get('Nationality', row.get('Nationality ', ''))).strip()
        player_name = str(row.get('Player Name', row.get('Player Name ', ''))).strip()
        club = str(row.get('Club', row.get('Club ', ''))).strip()
        position = str(row.get('Position', '')).strip()

        if not player_name:
            continue

        player = URIRef(f'{ns}Player/{player_name.replace(" ", "_").replace("/", "-")}')
        g.add((player, ns['hasNationality'], Literal(nationality)))
        g.add((player, ns['hasPosition'], Literal(position)))

        if club:
            club_uri = URIRef(f'{ns}Club/{club.replace(" ", "_")}')
            g.add((player, ns['playsForClub'], club_uri))

        if nationality:
            team_uri = URIRef(f'{ns}Team/{nationality.replace(" ", "_")}')
            g.add((player, ns['representsTeam'], team_uri))
            g.add((team_uri, ns['countryName'], Literal(nationality)))

    return g
