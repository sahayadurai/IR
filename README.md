# FIFA World Cup 2022 Knowledge Graph

An exam project for multimedia information retrieval using RDF, Neo4j and Cypher.
The project integrates historical FIFA tournament summaries, 2022 team standings,
player statistics, match/goal/appearance facts and representative player-image features.

## Quick start

1. Install and start Neo4j.
2. Configure `.env` using `.env.example`; set the password to the one configured in
   your local Neo4j instance.
3. Ensure the professor-provided `dataset/` files and FIFA image collection are present.
4. Run:

   ```sh
   ./run.sh
   ```

This installs Python requirements, downloads missing match-level files from a pinned
`jfjelstul/worldcup` commit, rebuilds and imports the KG, evaluates the benchmarks,
generates `report.pdf`, and runs Streamlit at http://localhost:8501.

> `./run.sh` replaces all nodes and relationships in the selected Neo4j database.
> Review `.env` and use a database dedicated to this project.

## Manual commands

```sh
python -m scripts.fetch_worldcup_data
python -m src.run_pipeline
python src/neo4j_import.py                 # additive import
python -m scripts.evaluate --repeats 5
python -m scripts.build_report
python -m unittest discover -s tests -v
```

## Project guide

- [Assignment mapping and method](./report.md)
- [Exam walkthrough](./self-study.md)
- [Setup and deliverables](./instruction.md)
- [Cypher query catalog and benchmarks](./cyphers.md)

The report generator requires fresh benchmark output and produces a report of at most
10 pages. Local source data, Turtle output and evaluation intermediates are intentionally
not included in source control; see the professor-provided dataset and the source-fetch
script for reproducible inputs.
