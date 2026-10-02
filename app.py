import os
import json
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import requests
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

OPENROUTER_FALLBACK_MODELS = [
    "openai/gpt-4o-mini",
    "openai/gpt-4o",
    "google/gemini-2.0-flash-exp:free",
    "google/gemma-3-4b-it:free",
    "meta-llama/llama-3.1-8b-instruct:free",
]

FREE_MODELS = OPENROUTER_FALLBACK_MODELS


@st.cache_resource
def get_neo4j_driver():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "fifa2022")
    return GraphDatabase.driver(uri, auth=(user, password))


def normalize_neo4j_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        return [normalize_neo4j_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): normalize_neo4j_value(v) for k, v in value.items()}
    if hasattr(value, "labels") and hasattr(value, "items"):
        return {
            "labels": list(value.labels),
            "properties": {k: normalize_neo4j_value(v) for k, v in value.items()},
            "id": str(value.element_id),
        }
    if hasattr(value, "type") and hasattr(value, "start_node") and hasattr(value, "end_node"):
        return {
            "type": value.type,
            "start": normalize_neo4j_value(value.start_node),
            "end": normalize_neo4j_value(value.end_node),
            "properties": {k: normalize_neo4j_value(v) for k, v in value.items()},
        }
    return str(value)


def run_query(query: str) -> List[Dict[str, Any]]:
    driver = get_neo4j_driver()
    database = os.getenv("NEO4J_DATABASE") or None

    def read_records(transaction):
        result = transaction.run(query)
        return [
            {key: normalize_neo4j_value(value) for key, value in record.items()}
            for record in result
        ]

    with driver.session(database=database) as session:
        return session.execute_read(read_records)


def graph_context() -> str:
    """Return deterministic KG facts for the optional natural-language layer."""
    tournament_facts = run_query(
        "MATCH (n:Resource)-[r]->(m) "
        "WHERE n.uri CONTAINS '/Tournament/' "
        "RETURN n.uri AS tournament, type(r) AS relation, "
        "coalesce(m.value, m.uri) AS value ORDER BY n.uri, relation"
    )
    player_facts = run_query(
        "MATCH (n:Resource)-[r]->(m) "
        "WHERE n.uri CONTAINS '/Player/' "
        "RETURN n.uri AS player, type(r) AS relation, "
        "coalesce(m.value, m.uri) AS value ORDER BY player LIMIT 300"
    )
    return str({"tournament_facts": tournament_facts, "player_facts": player_facts})


def ask_openrouter(
    question: str,
    context: str,
    model_name: Optional[str] = None,
    chat_history: Optional[List[Dict[str, str]]] = None,
) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return "OpenRouter API key is not configured. Add it in the .env file to enable AI-assisted answers."

    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    preferred_model = model_name or os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")

    candidate_models = []
    for candidate in [preferred_model, *OPENROUTER_FALLBACK_MODELS]:
        if candidate and candidate not in candidate_models:
            candidate_models.append(candidate)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    conversation = []
    for entry in chat_history or []:
        conversation.append({
            "role": entry.get("role", "user"),
            "content": entry.get("content", ""),
        })

    messages = [
        {
            "role": "system",
            "content": (
                "You are a sports knowledge assistant grounded in a FIFA World Cup knowledge graph. "
                "Use the provided graph context and the previous conversation to answer follow-up questions. "
                "If the answer cannot be inferred from the graph, say so explicitly."
            ),
        },
        *conversation,
        {
            "role": "user",
            "content": f"Question: {question}\n\nGraph context:\n{context}",
        },
    ]

    last_error = None
    for model in candidate_models:
        payload = {
            "model": model,
            "messages": messages,
            "temperature": 0.2,
        }
        response = None
        try:
            response = requests.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )
            if response.status_code == 404:
                last_error = f"Model '{model}' is not available on OpenRouter. Retrying with a supported model."
                continue
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except requests.RequestException as exc:
            last_error = str(exc)
            if response is not None and response.status_code == 404:
                continue
            return f"OpenRouter call failed: {exc}"
        except Exception as exc:
            last_error = str(exc)
            return f"OpenRouter call failed: {exc}"

    if last_error:
        return f"OpenRouter call failed: {last_error}"
    return "OpenRouter call failed: no supported model was available for this API key."


def graph_summary() -> Dict[str, int]:
    summary_query = "MATCH (n) RETURN count(n) AS nodes"
    relationship_query = "MATCH ()-[r]->() RETURN count(r) AS relationships"
    node_data = run_query(summary_query)
    rel_data = run_query(relationship_query)
    nodes = int(node_data[0].get("nodes", 0)) if node_data else 0
    relationships = int(rel_data[0].get("relationships", 0)) if rel_data else 0
    return {"nodes": nodes, "relationships": relationships}


def node_label_distribution() -> pd.DataFrame:
    rows = run_query("MATCH (n) RETURN labels(n) AS labels, count(n) AS count ORDER BY count DESC")
    return pd.DataFrame(rows)


def relationship_distribution() -> pd.DataFrame:
    rows = run_query("MATCH ()-[r]->() RETURN type(r) AS relationship_type, count(r) AS count ORDER BY count DESC")
    return pd.DataFrame(rows)


def graph_payload_from_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
        nodes = {}
        edges = []

        def visit(value: Any) -> None:
                if isinstance(value, list):
                        for item in value:
                                visit(item)
                elif isinstance(value, dict):
                        if "start" in value and "end" in value and "type" in value:
                                start = value["start"]
                                end = value["end"]
                                visit(start)
                                visit(end)
                                if isinstance(start, dict) and isinstance(end, dict):
                                        edges.append({
                                                "source": str(start.get("id", start.get("properties", {}).get("uri", ""))),
                                                "target": str(end.get("id", end.get("properties", {}).get("uri", ""))),
                                                "label": str(value["type"]),
                                        })
                        elif "id" in value and ("labels" in value or "properties" in value):
                                node_id = str(value["id"])
                                properties = value.get("properties", {})
                                nodes[node_id] = {
                                        "id": node_id,
                                        "label": ", ".join(value.get("labels", [])) or "Resource",
                                        "title": str(properties.get("uri", node_id)).split("/")[-1],
                                }
                        else:
                                for item in value.values():
                                        visit(item)

        visit(results)
        return {"nodes": list(nodes.values()), "edges": edges}


def render_graph_visualization(payload: Dict[str, Any], height: int = 680) -> None:
        graph_json = json.dumps(payload).replace("</", "<\\/")
        components.html(
                f"""
                <script src="https://cdnjs.cloudflare.com/ajax/libs/gsap/3.12.5/gsap.min.js"></script>
                <style>
                    html, body {{ margin: 0; background: #08131c; color: #dce9ee; font-family: sans-serif; overflow: hidden; }}
                    #graph {{ width: 100%; height: {height}px; display: block; cursor: grab; }}
                    #graph:active {{ cursor: grabbing; }}
                    .edge {{ stroke: #5d7882; stroke-width: 1.2; opacity: .65; }}
                    .edge-label {{ fill: #91b2b8; font-size: 10px; pointer-events: none; }}
                    .node {{ stroke: #dce9ee; stroke-width: 1.5; cursor: grab; }}
                    .node-label {{ fill: #f4f7f8; font-size: 11px; pointer-events: none; text-anchor: middle; }}
                    .legend {{ fill: #9db4ba; font-size: 12px; }}
                </style>
                <svg id="graph" viewBox="0 0 1100 {height}" role="img" aria-label="Interactive knowledge graph"></svg>
                <script>
                (() => {{
                    const data = {graph_json};
                    const svg = document.getElementById('graph');
                    const ns = 'http://www.w3.org/2000/svg';
                    const width = 1100, centerY = {height} / 2;
                    const colors = {{ Resource: '#ef8354', Literal: '#4cb5ae' }};
                      const nodes = data.nodes || [];
                    const ids = new Set(nodes.map(n => n.id));
                      const edges = (data.edges || []).filter(e => ids.has(e.source) && ids.has(e.target));
                    const positions = {{}};
                    nodes.forEach((node, index) => {{
                        const ring = Math.floor(index / 36);
                        const slot = index % 36;
                        const radius = 130 + ring * 90;
                        positions[node.id] = {{ x: width / 2 + Math.cos(slot / 36 * Math.PI * 2) * radius, y: centerY + Math.sin(slot / 36 * Math.PI * 2) * radius * .65 }};
                    }});
                    const edgeLayer = document.createElementNS(ns, 'g');
                    const labelLayer = document.createElementNS(ns, 'g');
                    const nodeLayer = document.createElementNS(ns, 'g');
                    svg.append(edgeLayer, labelLayer, nodeLayer);
                    const edgeEls = [], labelEls = [], nodeEls = [];
                    const draw = () => {{
                        edges.forEach((edge, index) => {{
                            const a = positions[edge.source], b = positions[edge.target];
                            edgeEls[index].setAttribute('x1', a.x); edgeEls[index].setAttribute('y1', a.y);
                            edgeEls[index].setAttribute('x2', b.x); edgeEls[index].setAttribute('y2', b.y);
                            labelEls[index].setAttribute('x', (a.x + b.x) / 2); labelEls[index].setAttribute('y', (a.y + b.y) / 2);
                        }});
                        nodes.forEach((node, index) => {{
                            const p = positions[node.id];
                            nodeEls[index].circle.setAttribute('cx', p.x); nodeEls[index].circle.setAttribute('cy', p.y);
                            nodeEls[index].text.setAttribute('x', p.x); nodeEls[index].text.setAttribute('y', p.y + 25);
                        }});
                    }};
                    edges.forEach(edge => {{
                        const line = document.createElementNS(ns, 'line'); line.setAttribute('class', 'edge'); edgeLayer.appendChild(line); edgeEls.push(line);
                        const label = document.createElementNS(ns, 'text'); label.setAttribute('class', 'edge-label'); label.textContent = edge.label; labelLayer.appendChild(label); labelEls.push(label);
                    }});
                    nodes.forEach(node => {{
                        const group = document.createElementNS(ns, 'g');
                        const circle = document.createElementNS(ns, 'circle'); circle.setAttribute('class', 'node'); circle.setAttribute('r', node.label === 'Literal' ? 7 : 10); circle.setAttribute('fill', colors[node.label] || '#ef8354');
                        const text = document.createElementNS(ns, 'text'); text.setAttribute('class', 'node-label'); text.textContent = node.title.slice(0, 25);
                        group.append(circle, text); nodeLayer.appendChild(group); nodeEls.push({{ group, circle, text }});
                        let dragging = false;
                        group.addEventListener('pointerdown', event => {{ dragging = true; group.setPointerCapture(event.pointerId); }});
                        group.addEventListener('pointermove', event => {{ if (!dragging) return; const point = svg.createSVGPoint(); point.x = event.clientX; point.y = event.clientY; const local = point.matrixTransform(svg.getScreenCTM().inverse()); positions[node.id] = {{ x: local.x, y: local.y }}; draw(); }});
                        group.addEventListener('pointerup', () => dragging = false);
                    }});
                    draw();
                      gsap.from(edgeEls, {{ opacity: 0, duration: .45, stagger: .001, ease: 'power2.out' }});
                      gsap.from(nodeEls.map(n => n.group), {{ scale: 0, transformOrigin: 'center', duration: .7, stagger: .003, ease: 'back.out(1.7)' }});
                    const legend = document.createElementNS(ns, 'text'); legend.setAttribute('class', 'legend'); legend.setAttribute('x', 22); legend.setAttribute('y', 30); legend.textContent = `${{nodes.length}} nodes  |  ${{edges.length}} relationships  |  drag nodes`; svg.appendChild(legend);
                }})();
                </script>
                """,
                height=height,
                scrolling=False,
        )


st.set_page_config(page_title="FIFA Knowledge Graph Explorer", page_icon="⚽", layout="wide")
st.title("⚽ FIFA World Cup Knowledge Graph Explorer")

with st.sidebar:
    st.header("Navigation")
    page = st.radio("Go to", ["Dashboard", "Cypher Query", "Visualize", "AI Chat"])

    st.header("Neo4j connection")
    st.caption(f"URI: {os.getenv('NEO4J_URI', 'bolt://localhost:7687')}")
    st.caption(f"User: {os.getenv('NEO4J_USER', 'neo4j')}")

    st.header("Free model")
    selected_model = st.selectbox(
        "Recommended: Mistral 7B Instruct is usually the most economical free tier",
        FREE_MODELS,
        index=0,
    )
    st.caption("OpenRouter model selection for AI responses.")

    st.header("Sample queries")
    sample_queries = {
        "2022 champion": (
            "MATCH (t:Resource)-[:hasChampion]->(v:Literal) "
            "WHERE t.uri ENDS WITH '/Tournament/2022' RETURN v.value AS champion"
        ),
        "2022 match count": (
            "MATCH (m:Resource)-[:matchOf]->(t:Resource) "
            "WHERE t.uri ENDS WITH '/Tournament/2022' RETURN count(m) AS matches"
        ),
        "2022 Argentina standings": (
            "MATCH (team:Resource)-[:hasTournamentStatistics]->(stats:Resource) "
            "-[:inTournament]->(t:Resource), (stats)-[:hasPoints]->(p:Literal) "
            "WHERE t.uri ENDS WITH '/Tournament/2022' "
            "AND team.uri ENDS WITH '/Team/Argentina' "
            "RETURN team.uri AS team, p.value AS points"
        ),
        "Lionel Messi goals": (
            "MATCH (g:Resource)-[:scoredBy]->(p:Resource), "
            "(m:Resource)-[:hasGoal]->(g), "
            "(m)-[:matchOf]->(t:Resource) "
            "WHERE t.uri ENDS WITH '/Tournament/2022' "
            "AND p.uri ENDS WITH '/Player/Lionel_Messi' "
            "RETURN count(g) AS goals"
        ),
        "Player image features": (
            "MATCH (p:Resource)-[:hasImage]->(image:Resource), "
            "(image)-[:hasColorHistogramRgb8]->(features:Literal) "
            "RETURN p.uri AS player, image.uri AS image, features.value AS rgb_histogram "
            "ORDER BY player LIMIT 20"
        ),
        "Graph size by label": (
            "MATCH (n) RETURN labels(n) AS labels, count(n) AS count "
            "ORDER BY count DESC LIMIT 20"
        ),
    }
    chosen = st.selectbox("Use a sample query", list(sample_queries.keys()))
    if st.button("Run selected query"):
        st.session_state["query"] = sample_queries[chosen]

    st.markdown("---")
    st.subheader("AI assistant")
    st.caption("Optional: uses OpenRouter if your API key is configured.")

if "query" not in st.session_state:
    st.session_state["query"] = sample_queries["2022 champion"]

if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []

if page == "Dashboard":
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

elif page == "Cypher Query":
    query = st.text_area("Cypher query", value=st.session_state["query"], height=180)
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Execute query"):
            if query is None:
                st.session_state["results"] = []
                st.session_state["error"] = "Enter a Cypher query before execution."
            else:
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

    if "error" in st.session_state and st.session_state["error"]:
        st.error(st.session_state["error"])

    if "results" in st.session_state:
        results = st.session_state["results"]
        if results:
            st.subheader("Query results")
            st.dataframe(results, use_container_width=True)
            query_graph = graph_payload_from_results(results)
            if query_graph["nodes"]:
                st.subheader("Query graph")
                render_graph_visualization(query_graph, height=620)
        else:
            st.info("No rows returned for this query.")

elif page == "Visualize":
    st.subheader("Interactive knowledge graph")
    st.caption("Nodes are entities or values. Lines are Neo4j relationships; drag a node to explore its connections.")
    visualization_query = (
        "MATCH (a:Resource)-[r]->(b) "
        "RETURN a, r, b"
    )
    try:
        full_graph = graph_payload_from_results(run_query(visualization_query))
        if full_graph["nodes"]:
            render_graph_visualization(full_graph, height=720)
        else:
            st.info("No graph nodes are available yet. Run the pipeline first.")
    except Exception as exc:
        st.error(f"Graph visualization failed: {exc}")

elif page == "AI Chat":
    st.subheader("Ask about the FIFA graph")
    for message in st.session_state.chat_messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if prompt := st.chat_input("Ask a question about players, teams, tournaments, or clubs..."):
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        try:
            answer = ask_openrouter(
                prompt,
                graph_context(),
                model_name=selected_model,
                chat_history=st.session_state.chat_messages,
            )
            st.session_state.chat_messages.append({"role": "assistant", "content": answer})
            with st.chat_message("assistant"):
                st.markdown(answer)
        except Exception as exc:
            error_message = f"AI query failed: {exc}"
            st.session_state.chat_messages.append({"role": "assistant", "content": error_message})
            with st.chat_message("assistant"):
                st.markdown(error_message)

st.sidebar.markdown("---")
if os.getenv("OPENROUTER_API_KEY"):
    st.sidebar.success("OpenRouter is configured and ready.")
else:
    st.sidebar.warning("Add your OpenRouter API key in the .env file to enable AI answers.")
