from __future__ import annotations

import argparse
import os
import re
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote, urlsplit

from neo4j import GraphDatabase, Query
from rdflib import Graph, Literal, URIRef


ROOT = Path(__file__).resolve().parent.parent
BATCH_SIZE = 1000
PREDICATE_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")


def _resource_category(uri: str) -> str:
    parts = [unquote(part) for part in urlsplit(uri).path.split("/") if part]
    return parts[-2] if len(parts) >= 2 else "Resource"


def _predicate_name(uri: URIRef) -> str:
    value = str(uri).rsplit("#", 1)[-1].rsplit("/", 1)[-1]
    if not PREDICATE_NAME.fullmatch(value):
        raise ValueError(f"Unsafe RDF predicate local name for Neo4j: {value!r}")
    return value


def _literal_native_value(value: Literal):
    native = value.toPython()
    if isinstance(native, (bool, int, float, str)):
        return native
    return None


class Neo4jKGLoader:
    def __init__(self, uri: str, user: str, password: str, database: str | None = None):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.database = database

    def close(self):
        self.driver.close()

    def clear_graph(self):
        with self.driver.session(database=self.database) as session:
            session.run("MATCH (n) DETACH DELETE n").consume()

    def ensure_indexes(self):
        with self.driver.session(database=self.database) as session:
            session.run(
                "CREATE INDEX resource_uri_index IF NOT EXISTS "
                "FOR (n:Resource) ON (n.uri)"
            ).consume()
            session.run(
                "CREATE INDEX literal_value_index IF NOT EXISTS "
                "FOR (n:Literal) ON (n.value)"
            ).consume()

    def import_from_rdf(self, rdf_path: str | Path) -> int:
        graph = Graph()
        graph.parse(str(rdf_path), format="turtle")
        self.ensure_indexes()
        grouped: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)

        for subject, predicate, obj in graph:
            if not isinstance(predicate, URIRef):
                raise TypeError(f"RDF predicate must be a URI: {predicate!r}")
            relationship = _predicate_name(predicate)
            row: dict[str, object] = {
                "subject": str(subject),
                "subjectCategory": _resource_category(str(subject)),
            }
            if isinstance(obj, Literal):
                row.update(
                    {
                        "value": str(obj),
                        "datatype": str(obj.datatype or ""),
                        "language": obj.language or "",
                        "nativeValue": _literal_native_value(obj),
                    }
                )
                object_kind = "literal"
            elif isinstance(obj, URIRef):
                row.update(
                    {
                        "object": str(obj),
                        "objectCategory": _resource_category(str(obj)),
                    }
                )
                object_kind = "resource"
            else:
                continue
            grouped[(relationship, object_kind)].append(row)

        with self.driver.session(database=self.database) as session:
            for (relationship, object_kind), rows in grouped.items():
                relationship_type = f"`{relationship}`"
                if object_kind == "literal":
                    query = (
                        "UNWIND $rows AS row "
                        "MERGE (a:Resource {uri: row.subject}) "
                        "SET a.category = coalesce(a.category, row.subjectCategory) "
                        "MERGE (b:Literal {value: row.value}) "
                        f"MERGE (a)-[r:{relationship_type}]->(b) "
                        "SET r.rdfDatatype = row.datatype, "
                        "r.rdfLanguage = row.language "
                        "FOREACH (_ IN CASE WHEN row.nativeValue IS NULL "
                        "THEN [] ELSE [1] END | SET r.nativeValue = row.nativeValue)"
                    )
                else:
                    query = (
                        "UNWIND $rows AS row "
                        "MERGE (a:Resource {uri: row.subject}) "
                        "SET a.category = coalesce(a.category, row.subjectCategory) "
                        "MERGE (b:Resource {uri: row.object}) "
                        "SET b.category = coalesce(b.category, row.objectCategory) "
                        f"MERGE (a)-[:{relationship_type}]->(b)"
                    )
                for start in range(0, len(rows), BATCH_SIZE):
                    session.run(Query(query), rows=rows[start : start + BATCH_SIZE]).consume()

        return len(graph)


def main():
    parser = argparse.ArgumentParser(description="Import the FIFA RDF knowledge graph into Neo4j.")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Delete all nodes and relationships from the selected database before importing.",
    )
    parser.add_argument(
        "--rdf",
        type=Path,
        default=ROOT / "fifa_kg.ttl",
        help="Turtle file to import (default: fifa_kg.ttl).",
    )
    args = parser.parse_args()

    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "fifa2022")
    database = os.getenv("NEO4J_DATABASE") or None
    loader = Neo4jKGLoader(uri, user, password, database)
    try:
        if args.replace:
            print("Replacing the selected Neo4j database contents as requested.")
            loader.clear_graph()
        count = loader.import_from_rdf(args.rdf)
        print(f"Neo4j import complete: {count:,} RDF triples processed.")
    finally:
        loader.close()


if __name__ == "__main__":
    main()
