import os
from typing import Any, Dict, List

import pandas as pd
import streamlit as st
import requests
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()


@st.cache_resource
def get_neo4j_driver():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "fifa2022")
    return GraphDatabase.driver(uri, auth=(user, password))


def run_query(query: str) -> List[Dict[str, Any]]:
    driver = get_neo4j_driver()
    with driver.session() as session:
        result = session.run(query)
        return [dict(record) for record in result]


def ask_openrouter(question: str, context: str) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return "OpenRouter API key is not configured. Add it in the .env file to enable AI-assisted answers."

    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    model = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a sports knowledge assistant. Answer using the provided graph context only. "
                    "If the answer is not in the context, say so clearly."
                ),
            },
            {
                "role": "user",
                "content": f"Question: {question}\n\nContext from Neo4j:\n{context}",
            },
        ],
        "temperature": 0.2,
    }

    try:
        response = requests.post(f"{base_url}/chat/completions", headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except Exception as exc:
        return f"OpenRouter call failed: {exc}"


def graph_summary() -> Dict[str, int]:
    summary_query = """
    MATCH (n)
    RETURN count(n) AS nodes
    """
    relationship_query = """
    MATCH ()-[r]->()
    RETURN count(r) AS relationships
    """

    node_data = run_query(summary_query)
    rel_data = run_query(relationship_query)
    nodes = int(node_data[0].get("nodes", 0)) if node_data else 0
    relationships = int(rel_data[0].get("relationships", 0)) if rel_data else 0
    return {"nodes": nodes, "relationships": relationships}


def node_label_distribution() -> pd.DataFrame:
    query = "MATCH (n) RETURN labels(n) AS labels, count(n) AS count ORDER BY count DESC"
    rows = run_query(query)
    return pd.DataFrame(rows)


def relationship_distribution() -> pd.DataFrame:
    query = "MATCH ()-[r]->() RETURN type(r) AS relationship_type, count(r) AS count ORDER BY count DESC"
    rows = run_query(query)
    return pd.DataFrame(rows)


st.set_page_config(page_title="FIFA Knowledge Graph Explorer", page_icon="⚽", layout="wide")
st.title("⚽ FIFA World Cup Knowledge Graph Explorer")

with st.sidebar:
    st.header("Neo4j connection")
    st.caption(f"URI: {os.getenv('NEO4J_URI', 'bolt://localhost:7687')}")
    st.caption(f"User: {os.getenv('NEO4J_USER', 'neo4j')}")

    st.header("Sample queries")
    sample_queries = {
        "Node overview": "MATCH (n) RETURN n LIMIT 20",
        "All relationships": "MATCH ()-[r]->() RETURN type(r) AS rel_type, count(r) AS cnt ORDER BY cnt DESC LIMIT 20",
        "Resource summary": "MATCH (n) RETURN labels(n) AS labels, count(n) AS count ORDER BY count DESC",
        "Tournament facts": "MATCH (n) RETURN n LIMIT 20",
    }
    chosen = st.selectbox("Use a sample query", list(sample_queries.keys()))
    if st.button("Run selected query"):
        st.session_state["query"] = sample_queries[chosen]

    st.markdown("---")
    st.subheader("AI assistant")
    st.caption("Optional: uses OpenRouter if API key is provided.")


if "query" not in st.session_state:
    st.session_state["query"] = "MATCH (n) RETURN n LIMIT 20"

query = st.text_area("Cypher query", value=st.session_state["query"], height=150)

col1, col2 = st.columns([1, 1])
with col1:
    if st.button("Execute query"):
        try:
            st.session_state["results"] = run_query(query)
            st.session_state["error"] = None
        except Exception as exc:
            st.session_state["results"] = []
            st.session_state["error"] = str(exc)
with col2:
    if st.button("Clear"):
        st.session_state.pop("results", None)
        st.session_state.pop("error", None)

summary = graph_summary()

st.subheader("Graph overview")
metric_cols = st.columns(4)
metric_cols[0].metric("Nodes", summary["nodes"])
metric_cols[1].metric("Relationships", summary["relationships"])
metric_cols[2].metric("Database", "Neo4j")
metric_cols[3].metric("AI", "OpenRouter" if os.getenv("OPENROUTER_API_KEY") else "Off")

st.markdown("---")

label_df = node_label_distribution()
rel_df = relationship_distribution()

left_chart, right_chart = st.columns(2)
if not label_df.empty:
    left_chart.subheader("Node labels")
    left_chart.bar_chart(label_df.set_index("labels")["count"])
if not rel_df.empty:
    right_chart.subheader("Relationship types")
    right_chart.bar_chart(rel_df.set_index("relationship_type")["count"])

if "error" in st.session_state and st.session_state["error"]:
    st.error(st.session_state["error"])

if "results" in st.session_state:
    results = st.session_state["results"]
    if results:
        st.subheader("Query results")
        st.dataframe(results, use_container_width=True)
    else:
        st.info("No rows returned for this query.")

st.markdown("---")

st.subheader("Ask the graph in natural language")
question = st.text_input("Question about the FIFA knowledge graph")
if st.button("Ask AI") and question:
    try:
        context_data = run_query("MATCH (n) RETURN n LIMIT 50")
        response = ask_openrouter(question, str(context_data))
        st.success(response)
    except Exception as exc:
        st.error(f"AI query failed: {exc}")
