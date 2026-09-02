from __future__ import annotations

import os
from pathlib import Path

from neo4j import GraphDatabase
from rdflib import Graph, URIRef, Literal


ROOT = Path(__file__).resolve().parent.parent


class Neo4jKGLoader:
    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def clear_graph(self):
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")

    def import_from_rdf(self, rdf_path: str | Path):
        g = Graph()
        g.parse(str(rdf_path), format='turtle')

        with self.driver.session() as session:
            for s, p, o in g:
                s_id = str(s)
                p_name = str(p).split('/')[-1]

                if isinstance(o, Literal):
                    value = str(o)
                    session.run(
                        "MERGE (a:Resource {uri: $subject}) "
                        "MERGE (b:Literal {value: $value}) "
                        "MERGE (a)-[:`" + p_name + "`]->(b)",
                        subject=s_id,
                        value=value,
                    )
                elif isinstance(o, URIRef):
                    obj_id = str(o)
                    session.run(
                        "MERGE (a:Resource {uri: $subject}) "
                        "MERGE (b:Resource {uri: $object}) "
                        "MERGE (a)-[:`" + p_name + "`]->(b)",
                        subject=s_id,
                        object=obj_id,
                    )


def main():
    uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
    user = os.getenv('NEO4J_USER', 'neo4j')
    password = os.getenv('NEO4J_PASSWORD', 'fifa2022')

    loader = Neo4jKGLoader(uri, user, password)
    try:
        loader.clear_graph()
        loader.import_from_rdf(ROOT / 'fifa_kg.ttl')
        print('Neo4j import complete.')
    finally:
        loader.close()


if __name__ == '__main__':
    main()
