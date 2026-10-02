# Exam Walkthrough: FIFA World Cup Knowledge Graph

## The project in one minute

The pipeline cleans the professor-provided FIFA files, downloads the missing
match-level CSVs from the required `jfjelstul/worldcup` source, models facts as RDF
triples, serializes Turtle, and imports it into Neo4j. A Streamlit application runs
Cypher retrieval over the graph. The optional chatbot is not the source of truth.

Evidence path:

`source files -> cleaning/audit -> RDF -> fifa_kg.ttl -> Neo4j -> Cypher -> measured evaluation`

## Source coverage

- 22 historical tournament summary records.
- 32 FIFA 2022 team standings.
- 814 FIFA 2022 player-statistics records.
- 830 player names in the all-player roster.
- 64 World Cup 2022 matches, 172 goals and 1,995 match appearances from
  `jfjelstul/worldcup`.
- 831 image folders and 41,510 JPG files.

Counts are inspected during pipeline execution and written to `output/data_quality.json`.
The three upstream match datasets are filtered by tournament ID `WC-2022`; the
standings table is not mistaken for match-level data.

## Main source files

### `src/fifa_kg/data_loader.py`

Trims columns and string values, normalizes blank/dash placeholders to missing values,
keeps source row counts, and filters match, goal and appearance data by stable
tournament ID.

### `src/fifa_kg/graph_builder.py`

Creates RDF entities and relationships for tournaments, teams, standings, players,
matches, goals, appearances, venues, clubs and image metadata. It stores source
provenance and typed literal values. For each player-image folder it extracts one
deterministically selected JPEG's original dimensions and a normalized 24-value RGB
histogram.

### `src/run_pipeline.py`

Loads all required tables, builds `fifa_kg.ttl`, and writes `output/data_quality.json`
with row, duplicate and missing-value counts.

### `src/neo4j_import.py`

Imports RDF resources, literal nodes and predicate relationships in batches. The
default is additive. `--replace` explicitly clears the selected database first.

### `scripts/evaluate.py`

Executes Neo4j read-only benchmarks with a warm-up and repeated timings. It compares
answers to values computed from the source data and writes `output/evaluation.json`.

### `scripts/build_report.py`

Generates `report.pdf`, including an illustrated ontology, dataset coverage, methods,
limits and benchmark answer/timing table. It requires a successful evaluation output.

### `app.py`

Provides graph summaries, saved query examples, read-only direct Cypher retrieval,
interactive graph visualization and optional AI chat.

## Ontology examples

```text
Match/M-2022-01 --matchOf--> Tournament/2022
Match/M-2022-01 --homeTeam--> Team/Argentina
Match/M-2022-01 --playedAt--> Venue/S-...
Match/M-2022-01 --hasGoal--> Goal/G-...
Goal/G-... --scoredBy--> Player/Lionel_Messi
Appearance/... --appearanceOf--> Player/Lionel_Messi
Player/Lionel_Messi --playsForClub--> Club/...
Player/Lionel_Messi --hasImage--> Image/Lionel_Messi
```

The full illustrated schema is in `report.md` and `report.pdf`.

## Example query to demonstrate in an exam

```cypher
MATCH (m:Resource)-[:matchOf]->(t:Resource),
      (m)-[:hasGoal]->(goal:Resource),
      (goal)-[:scoredBy]->(player:Resource)
WHERE t.uri ENDS WITH '/Tournament/2022'
RETURN player.uri AS player, count(DISTINCT goal) AS goals
ORDER BY goals DESC
LIMIT 10;
```

This is a cross-dataset, event-level query: match facts identify the tournament,
goal-event resources identify scorers, and aggregation yields a ranking. The exact
queries and expected answers are in `cyphers.md` and `output/evaluation.json`.

## Important cautions

- `./run.sh` replaces all graph data in the selected Neo4j database. Use the project
  database and confirm `.env` before running it.
- A clean clone needs the professor-provided local datasets and image collection. The
  match-source fetch script downloads its pinned CSV inputs.
- The RGB histogram is a simple visual descriptor, not a semantic image model.
- Cross-source player matching is based on normalized names when stable identifiers
  are unavailable; ambiguous matches should be checked.
- Present measured Neo4j timings as local observations, not universal performance
  claims. Do not use chatbot wording as retrieval evidence.
