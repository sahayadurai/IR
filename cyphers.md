# FIFA Knowledge Graph: Cypher Query Catalog

Run these read-only queries from the Streamlit **Cypher Query** page or `cypher-shell`.
The Neo4j importer represents RDF URI subjects and objects as `Resource` nodes and RDF
literals as `Literal` nodes with a `value` property. Relationship types are the RDF
predicate names. Source provenance is represented by `wasDerivedFrom`.

## 1. Graph health

```cypher
MATCH (n) RETURN count(n) AS nodes;
```

```cypher
MATCH ()-[r]->() RETURN count(r) AS relationships;
```

```cypher
MATCH (n:Resource)
RETURN n.category AS resource_category, count(n) AS count
ORDER BY count DESC;
```

## 2. Historical tournament source

```cypher
MATCH (t:Resource)-[:hasChampion]->(champion:Literal)
WHERE t.uri CONTAINS '/Tournament/'
RETURN replace(t.uri, 'http://example.org/fifa/Tournament/', '') AS year,
       champion.value AS champion
ORDER BY year;
```

```cypher
MATCH (t:Resource)-[:hasChampion]->(champion:Literal),
      (t)-[:hasRunnerUp]->(runner_up:Literal),
      (t)-[:hasHost]->(host:Literal)
WHERE t.uri ENDS WITH '/Tournament/2022'
RETURN champion.value AS champion, runner_up.value AS runner_up,
       host.value AS host;
```

## 3. FIFA 2022 standings source

```cypher
MATCH (team:Resource)-[:hasTournamentStatistics]->(stats:Resource)
      -[:inTournament]->(t:Resource),
      (stats)-[:hasPoints]->(points:Literal),
      (stats)-[:hasStandingPosition]->(position:Literal)
WHERE t.uri ENDS WITH '/Tournament/2022'
RETURN team.uri AS team, toInteger(position.value) AS position,
       toInteger(points.value) AS points
ORDER BY position;
```

## 4. Match and venue retrieval

```cypher
MATCH (m:Resource)-[:matchOf]->(t:Resource),
      (m)-[:hasMatchName]->(name:Literal),
      (m)-[:hasScore]->(score:Literal)
WHERE t.uri ENDS WITH '/Tournament/2022'
RETURN m.uri AS match_id, name.value AS match, score.value AS score
ORDER BY match_id
LIMIT 20;
```

```cypher
MATCH (m:Resource)-[:matchOf]->(t:Resource),
      (m)-[:playedAt]->(venue:Resource),
      (venue)-[:hasVenueName]->(name:Literal),
      (venue)-[:hasCity]->(city:Literal)
WHERE t.uri ENDS WITH '/Tournament/2022'
RETURN m.uri AS match_id, name.value AS venue, city.value AS city
ORDER BY match_id;
```

## 5. Goal and player appearance retrieval

```cypher
MATCH (match:Resource)-[:matchOf]->(t:Resource),
      (match)-[:hasGoal]->(goal:Resource),
      (goal)-[:scoredBy]->(player:Resource),
      (goal)-[:hasMinute]->(minute:Literal)
WHERE t.uri ENDS WITH '/Tournament/2022'
RETURN player.uri AS player, count(DISTINCT goal) AS goals,
       collect(toInteger(minute.value)) AS minutes
ORDER BY goals DESC, player
LIMIT 20;
```

```cypher
MATCH (appearance:Resource)-[:appearanceIn]->(match:Resource)-[:matchOf]->(t:Resource),
      (appearance)-[:appearanceOf]->(player:Resource),
      (appearance)-[:playedFor]->(team:Resource)
WHERE t.uri ENDS WITH '/Tournament/2022'
  AND team.uri ENDS WITH '/Team/Argentina'
RETURN DISTINCT player.uri AS player, team.uri AS team
ORDER BY player;
```

## 6. 2022 player-statistics source

```cypher
MATCH (player:Resource)-[:hasName]->(name:Literal),
      (player)-[:hasNationality]->(nationality:Literal),
      (player)-[:hasPosition]->(position:Literal),
      (player)-[:playsForClub]->(club:Resource)
WHERE name.value = 'Lionel Messi'
RETURN name.value AS player, nationality.value AS nationality,
       position.value AS position, club.uri AS club;
```

```cypher
MATCH (team:Resource)<-[:representsTeam]-(player:Resource),
      (player)-[:hasName]->(name:Literal)
WHERE team.uri ENDS WITH '/Team/Argentina'
RETURN name.value AS player
ORDER BY player;
```

## 7. Multimedia retrieval

```cypher
MATCH (player:Resource)-[:hasImage]->(image:Resource),
      (image)-[:hasFileName]->(file:Literal),
      (image)-[:hasImageCount]->(count:Literal),
      (image)-[:hasColorHistogramRgb8]->(features:Literal)
RETURN player.uri AS player, file.value AS representative_file,
       toInteger(count.value) AS source_image_count,
       features.value AS rgb_histogram
ORDER BY player
LIMIT 20;
```

```cypher
MATCH (image:Resource)-[:hasColorHistogramRgb8]->(features:Literal),
      (image)-[:hasImageCount]->(count:Literal)
RETURN count(DISTINCT image) AS featured_player_images,
       sum(toInteger(count.value)) AS source_jpg_files;
```

## 8. Provenance

```cypher
MATCH (entity:Resource)-[:wasDerivedFrom]->(dataset:Resource)
RETURN dataset.uri AS source, entity.category AS entity_type,
       count(DISTINCT entity) AS entities
ORDER BY source, entity_type;
```

## 9. Evaluation protocol

`python scripts/evaluate.py --repeats 5` runs one warm-up and five timed, read-only
executions per benchmark. It compares returned values with ground truth derived from
the corresponding local source files, writes `output/evaluation.json`, and exits with a
failure if any expected result differs. `report.pdf` includes the query results and median
response times. Timing results are machine- and cache-dependent and should be presented
as local measurements, not as a comparison with another database.

The benchmark set covers historical outcomes, 2022 standings, player statistics,
matches, goal events, player appearances and image descriptors. The language model is not
used as a correctness judge.
