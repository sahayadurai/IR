from __future__ import annotations

import argparse
import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import Flowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
INK = colors.HexColor("#17324d")
TEAL = colors.HexColor("#1b8f91")
PALE = colors.HexColor("#eaf3f5")


class OntologyDiagram(Flowable):
    def __init__(self):
        super().__init__()
        self.height = 120 * mm

    def wrap(self, available_width, _available_height):
        self.width = available_width
        return self.width, self.height

    def draw(self):
        canvas = self.canv
        box_width = 25 * mm
        box_height = 13 * mm
        centers = [19 * mm + index * 42 * mm for index in range(4)]
        top_y = self.height - 18 * mm
        middle_y = 58 * mm
        bottom_y = 19 * mm
        top = [
            ("Tournament", centers[0], top_y),
            ("Match", centers[1], top_y),
            ("Goal", centers[2], top_y),
            ("Venue", centers[3], top_y),
        ]
        middle = [
            ("Team", centers[0], middle_y),
            ("Player", centers[1], middle_y),
            ("Club", centers[2], middle_y),
            ("Image", centers[3], middle_y),
        ]
        bottom = [
            ("Team stats", centers[0], bottom_y),
            ("Appearance", centers[1], bottom_y),
            ("Dataset", centers[3], bottom_y),
        ]

        def draw_node(label, center_x, center_y):
            x = center_x - box_width / 2
            y = center_y - box_height / 2
            canvas.setFillColor(PALE)
            canvas.setStrokeColor(TEAL)
            canvas.roundRect(x, y, box_width, box_height, 3 * mm, fill=1, stroke=1)
            canvas.setFillColor(INK)
            canvas.setFont("Helvetica-Bold", 7.5)
            canvas.drawCentredString(center_x, center_y - 2.5, label)

        def draw_arrow(start, end, label, label_offset: float = 0.0):
            x1, y1 = start
            x2, y2 = end
            dx = x2 - x1
            dy = y2 - y1
            length = max((dx * dx + dy * dy) ** 0.5, 0.001)
            ux = dx / length
            uy = dy / length
            canvas.setStrokeColor(INK)
            canvas.setFillColor(INK)
            canvas.setLineWidth(0.7)
            canvas.line(x1, y1, x2, y2)
            canvas.line(
                x2,
                y2,
                x2 - ux * 2 * mm + uy * 1 * mm,
                y2 - uy * 2 * mm - ux * 1 * mm,
            )
            canvas.line(
                x2,
                y2,
                x2 - ux * 2 * mm - uy * 1 * mm,
                y2 - uy * 2 * mm + ux * 1 * mm,
            )
            canvas.setFont("Helvetica", 6.2)
            canvas.drawCentredString((x1 + x2) / 2, (y1 + y2) / 2 + label_offset, label)

        for label, x, y in top + middle + bottom:
            draw_node(label, x, y)

        draw_arrow(
            (centers[1] - box_width / 2, top_y),
            (centers[0] + box_width / 2, top_y),
            "matchOf",
            3 * mm,
        )
        draw_arrow(
            (centers[1] + box_width / 2, top_y),
            (centers[2] - box_width / 2, top_y),
            "hasGoal",
            3 * mm,
        )
        route_y = top_y + 5 * mm
        venue_edge = centers[3] - box_width / 2
        canvas.line(centers[1] + box_width / 2, top_y, centers[1] + box_width / 2, route_y)
        canvas.line(centers[1] + box_width / 2, route_y, venue_edge, route_y)
        draw_arrow((venue_edge, route_y), (venue_edge, top_y), "playedAt", 6 * mm)
        draw_arrow(
            (centers[1] - 3 * mm, top_y - box_height / 2),
            (centers[0] + 3 * mm, middle_y + box_height / 2),
            "homeTeam / awayTeam",
            2 * mm,
        )
        draw_arrow(
            (centers[2] - 2 * mm, top_y - box_height / 2),
            (centers[1] + box_width / 2, middle_y + box_height / 2),
            "scoredBy",
            -2 * mm,
        )
        draw_arrow(
            (centers[1] - box_width / 2, middle_y),
            (centers[0] + box_width / 2, middle_y),
            "representsTeam",
            3 * mm,
        )
        draw_arrow(
            (centers[1] + box_width / 2, middle_y),
            (centers[2] - box_width / 2, middle_y),
            "playsForClub",
            3 * mm,
        )
        draw_arrow(
            (centers[1] + box_width / 2, middle_y - 4 * mm),
            (centers[3] - box_width / 2, middle_y - 4 * mm),
            "hasImage",
            -4 * mm,
        )
        draw_arrow(
            (centers[1], bottom_y + box_height / 2),
            (centers[1], middle_y - box_height / 2),
            "appearanceOf",
            4 * mm,
        )
        draw_arrow(
            (centers[0], middle_y - box_height / 2),
            (centers[0], bottom_y + box_height / 2),
            "hasTournamentStatistics",
            -5 * mm,
        )
        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(INK)
        canvas.drawRightString(
            self.width - 1 * mm,
            5 * mm,
            "Entities and events link to Dataset via wasDerivedFrom",
        )


def _styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=23,
            leading=28,
            textColor=INK,
            alignment=TA_CENTER,
            spaceAfter=8 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Section",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            textColor=INK,
            spaceBefore=2 * mm,
            spaceAfter=3 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Subsection",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13,
            textColor=TEAL,
            spaceBefore=2 * mm,
            spaceAfter=1.5 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BodySmall",
            parent=styles["BodyText"],
            fontSize=8.7,
            leading=12,
            spaceAfter=2.5 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            name="CaptionSmall",
            parent=styles["BodyText"],
            fontSize=7.5,
            leading=10,
            textColor=colors.HexColor("#526579"),
            alignment=TA_CENTER,
            spaceAfter=2 * mm,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TableSmall",
            parent=styles["BodyText"],
            fontSize=7,
            leading=9,
        )
    )
    return styles


def _paragraph(text, styles, style="BodySmall"):
    return Paragraph(text, styles[style])


def _table(data, widths, repeat_rows=1):
    table = Table(data, colWidths=widths, repeatRows=repeat_rows, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), INK),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("LEADING", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#becbd2")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, PALE]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def _page_number(canvas, document):
    canvas.saveState()
    canvas.setStrokeColor(colors.HexColor("#d1dce1"))
    canvas.line(18 * mm, 14 * mm, A4[0] - 18 * mm, 14 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#526579"))
    canvas.drawString(18 * mm, 9 * mm, "FIFA World Cup 2022 Multimedia Knowledge Graph")
    canvas.drawRightString(A4[0] - 18 * mm, 9 * mm, f"Page {document.page}")
    canvas.restoreState()


def build_report(evaluation_path: Path, output_path: Path) -> int:
    if not evaluation_path.is_file():
        raise FileNotFoundError(
            f"Evaluation results are missing: {evaluation_path}. "
            "Run `python scripts/evaluate.py` after importing the graph."
        )
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8"))
    source = evaluation["source_counts"]
    results = evaluation["results"]
    audit_path = ROOT / "output" / "data_quality.json"
    if not audit_path.is_file():
        raise FileNotFoundError(
            f"Data-quality audit is missing: {audit_path}. Run the graph pipeline first."
        )
    audit = json.loads(audit_path.read_text(encoding="utf-8"))
    player_missing = audit["preprocessing"]["datasets"][
        "fifa_2022_player_statistics"
    ]["missing_by_column"]
    ttl_path = ROOT / "fifa_kg.ttl"
    from rdflib import Graph

    graph = Graph()
    if ttl_path.is_file():
        graph.parse(ttl_path, format="turtle")
    triples = len(graph) if ttl_path.is_file() else "not available"
    styles = _styles()
    story = []

    story.extend(
        [
            Spacer(1, 17 * mm),
            _paragraph("Multimedia Information Retrieval<br/>for Sports Analytics", styles, "ReportTitle"),
            _paragraph(
                "<b>FIFA World Cup 2022 Knowledge Graph</b><br/>"
                "Information Retrieval Exam Project<br/>"
                "Course: Information Retrieval | Academic Year: 2025/2026",
                styles,
            ),
            Spacer(1, 4 * mm),
            _paragraph("Abstract and objectives", styles, "Section"),
            _paragraph(
                "This project builds a source-grounded knowledge graph for retrieval over FIFA "
                "World Cup data. It cleans and audits the supplied tabular sources, models "
                "tournament, team, player, match, goal, appearance, venue and image facts as RDF "
                "triples, imports the graph into Neo4j, and evaluates read-only Cypher queries "
                "against source-derived answers. A Streamlit dashboard exposes graph exploration "
                "and saved retrieval examples. The optional language-model feature is not treated "
                "as retrieval evidence.",
                styles,
            ),
            _paragraph(
                "The objective is to connect facts that are separated across datasets—for example, "
                "retrieving a match, its venue and score, goal events and scorers, or a player’s "
                "nationality, club and image features—through explicit graph relationships.",
                styles,
            ),
            _paragraph("Dataset coverage", styles, "Section"),
        ]
    )
    dataset_rows = [
        ["Source / category", "Records used", "Integration"],
        ["Historical World Cup summary", str(source["tournaments"]), "Tournament outcomes and totals"],
        ["FIFA 2022 team standings", str(source["teams_2022"]), "Team tournament statistics"],
        ["FIFA 2022 player statistics", str(source["player_statistics_2022"]), "Player profile and performance"],
        ["FIFA 2022 all-player roster", str(source["roster_names_2022"]), "Player name coverage"],
        ["jfjelstul match data", str(source["matches_2022"]), "2022 match facts and venues"],
        ["jfjelstul goal events", str(source["goals_2022"]), "Goal minute, scorer and team"],
        ["jfjelstul player appearances", str(source["player_appearances_2022"]), "Match roster and roles"],
        ["FIFA player image dataset", f"{source['image_folders']} folders / {source['image_files']} files", "Representative image and descriptors"],
    ]
    story.append(
        _table(
            [[_paragraph(str(cell), styles, "TableSmall") for cell in row] for row in dataset_rows],
            [48 * mm, 35 * mm, 89 * mm],
        )
    )
    story.extend(
        [
            Spacer(1, 2 * mm),
            _paragraph(
                f"The current RDF build contains <b>{triples}</b> triples. "
                "The match, goal and appearance tables are filtered to the men's FIFA World Cup "
                "2022 tournament identifier (WC-2022); the supplied historical summary covers "
                "22 tournaments.",
                styles,
                "CaptionSmall",
            ),
            PageBreak(),
            _paragraph("1. Data and preprocessing", styles, "Section"),
            _paragraph(
                "The local input collection includes the historical results table, a separate "
                "2022 team standings table, 2022 player statistics, an all-player name list and "
                "41,510 JPG assets organised into player folders. The professor-required "
                "jfjelstul/worldcup source additionally supplies the match, goal and player "
                "appearance CSVs. A fetch script pins a specific upstream commit so the added "
                "files can be reproduced instead of relying on an untracked manual download.",
                styles,
            ),
            _paragraph("Cleaning and quality controls", styles, "Subsection"),
            _paragraph(
                "CSV column names and string cells are whitespace-trimmed. Empty strings, dash "
                "placeholders and common null markers are normalized to missing values; numeric "
                "and percentage values are parsed into typed RDF literals. Original row counts "
                "are retained, and records with missing optional facts are not discarded. "
                "World Cup match, goal and appearance sources are filtered by tournament_id "
                "rather than by a loose year/name substring. Stable source identifiers are kept "
                "for match, goal and player records; image paths are stored relative to the image "
                "root.",
                styles,
            ),
            _paragraph(
                "A JSON data-quality audit accompanies each graph build, recording row counts, "
                "columns, duplicate rows and missing values by column. Source files are not "
                "modified. Missing optional values are omitted from RDF instead of being "
                "converted to misleading text such as “-”.",
                styles,
            ),
            _paragraph("Missing-value observations", styles, "Subsection"),
            _table(
                [
                    [
                        _paragraph("Player statistic", styles, "TableSmall"),
                        _paragraph("Missing rows", styles, "TableSmall"),
                        _paragraph("Treatment", styles, "TableSmall"),
                    ],
                    [
                        _paragraph("Goals Scored", styles, "TableSmall"),
                        str(player_missing.get("Goals Scored", 0)),
                        _paragraph("Source placeholder retained as missing; not assumed to mean zero.", styles, "TableSmall"),
                    ],
                    [
                        _paragraph("Save Percentage", styles, "TableSmall"),
                        str(player_missing.get("Save Percentage", 0)),
                        _paragraph("Role-specific field; missing values are not imputed for non-goalkeepers.", styles, "TableSmall"),
                    ],
                    [
                        _paragraph("Clean Sheets", styles, "TableSmall"),
                        str(player_missing.get("Clean Sheets", 0)),
                        _paragraph("Role-specific field; missing values are not imputed for non-goalkeepers.", styles, "TableSmall"),
                    ],
                    [
                        _paragraph("Appearances", styles, "TableSmall"),
                        str(player_missing.get("Appearances", 0)),
                        _paragraph("Optional source field; no inferred value is added.", styles, "TableSmall"),
                    ],
                ],
                [36 * mm, 23 * mm, 113 * mm],
            ),
            _paragraph("Reproducibility", styles, "Subsection"),
            _paragraph(
                "Run <font name='Courier'>./run.sh</font> on macOS with Neo4j installed and "
                "configured in <font name='Courier'>.env</font>. The script installs declared "
                "Python dependencies, downloads any missing pinned match-source CSVs, rebuilds "
                "the Turtle graph, imports it, runs the benchmark suite, regenerates this report "
                "and starts Streamlit on port 8501. Importing with <font name='Courier'>--replace</font> "
                "replaces the selected Neo4j database; the importer without that option is "
                "additive.",
                styles,
            ),
            PageBreak(),
            _paragraph("2. Ontological schema", styles, "Section"),
            _paragraph(
                "The global schema uses stable URI resources for entities and RDF literals for "
                "attribute values. RDF type assertions distinguish the core classes. Named "
                "relationships preserve the connections needed for multi-hop retrieval; "
                "<font name='Courier'>wasDerivedFrom</font> links entities and events to dataset "
                "resources for provenance.",
                styles,
            ),
            OntologyDiagram(),
            _paragraph(
                "Figure 1. Domain ontology (arrows are directed RDF predicates). Match-level "
                "facts are connected to teams, venues, tournaments and goal events. Players "
                "connect to team, club, appearance and image resources.",
                styles,
                "CaptionSmall",
            ),
            _paragraph("Representative predicates", styles, "Subsection"),
            _paragraph(
                "<b>Tournament:</b> hasChampion, hasRunnerUp, hostedIn, hasMatchCount<br/>"
                "<b>Match:</b> matchOf, homeTeam, awayTeam, playedAt, hasHomeTeamGoals, hasAwayTeamGoals<br/>"
                "<b>Goal:</b> scoredBy, forTeam, hasMinute, isPenalty, isOwnGoal<br/>"
                "<b>Player:</b> hasNationality, hasPosition, playsForClub, representsTeam, hasImage<br/>"
                "<b>Appearance:</b> appearanceOf, appearanceIn, playedFor, isStarter, isSubstitute<br/>"
                "<b>Image:</b> hasFileName, hasImageCount, hasColorHistogramRgb8<br/>"
                "<b>Provenance:</b> wasDerivedFrom",
                styles,
            ),
            PageBreak(),
            _paragraph("3. Knowledge graph construction and retrieval", styles, "Section"),
            _paragraph(
                "The graph builder produces RDF subject-predicate-object statements with rdflib "
                "and serializes them as Turtle. Neo4j stores URI resources and literal-value "
                "nodes; predicate local names become relationship types. Literal values retain "
                "their RDF datatype and language on their outgoing relationships, while resource "
                "nodes record their category. Imports are batched by predicate. The default "
                "import is additive; a full replacement requires the explicit --replace flag.",
                styles,
            ),
            _paragraph("Example semantic queries", styles, "Subsection"),
            _paragraph(
                "<b>Champion of 2022:</b><br/>"
                "<font name='Courier'>MATCH (t:Resource)-[:hasChampion]-&gt;(v:Literal) "
                "WHERE t.uri ENDS WITH '/Tournament/2022' RETURN v.value</font>",
                styles,
            ),
            _paragraph(
                "<b>2022 matches with venue and score:</b><br/>"
                "<font name='Courier'>MATCH (m:Resource)-[:matchOf]-&gt;(t:Resource), "
                "(m)-[:playedAt]-&gt;(v:Resource), (m)-[:hasScore]-&gt;(s:Literal) "
                "WHERE t.uri ENDS WITH '/Tournament/2022' "
                "RETURN m.uri, v.uri, s.value</font>",
                styles,
            ),
            _paragraph(
                "<b>Goal events by player:</b><br/>"
                "<font name='Courier'>MATCH (m:Resource)-[:hasGoal]-&gt;(g:Resource), "
                "(m)-[:matchOf]-&gt;(t:Resource), (g)-[:scoredBy]-&gt;(p:Resource) "
                "WHERE t.uri ENDS WITH '/Tournament/2022' RETURN p.uri, count(g)</font>",
                styles,
            ),
            _paragraph(
                "The Streamlit dashboard includes saved examples, direct Cypher retrieval, "
                "graph visualization and optional AI chat. Dashboard queries run in Neo4j read "
                "transactions. AI responses are an optional explanation layer and are not used "
                "for correctness or evaluation.",
                styles,
            ),
            _paragraph("4. Multimedia feature extraction", styles, "Section"),
            _paragraph(
                "The image tree contains thousands of files, so the reproducible graph uses one "
                "deterministically selected representative JPEG per player folder. Pillow "
                "records original width and height, relative file path and image count. It also "
                "resizes the representative to 64×64 RGB and computes a normalized 24-value "
                "color histogram (8 bins per RGB channel). The compact descriptor is stored as "
                "an RDF feature literal linked to the image resource. This is a transparent "
                "low-level visual descriptor, not a learned embedding or claim of face "
                "recognition.",
                styles,
            ),
            _paragraph(
                "Neo4j queries can retrieve image resources, their source counts and histogram "
                "descriptors. The method is suitable for metadata/color-based exploration; "
                "future work could add perceptual hashes or learned embeddings and explicit "
                "similarity ranking.",
                styles,
            ),
            PageBreak(),
            _paragraph("5. Performance evaluation", styles, "Section"),
            _paragraph(
                evaluation.get("evaluation_method", ""),
                styles,
            ),
        ]
    )
    result_rows: list[list[object]] = [
        ["Benchmark / source", "Expected", "Returned", "Correct", "Median ms"]
    ]
    for result in results:
        expected = json.dumps(result["expected"], ensure_ascii=False)
        returned = json.dumps(result["returned"], ensure_ascii=False)
        result_rows.append(
            [
                _paragraph(f"{result['name']}<br/><font color='#526579'>{result['dataset']}</font>", styles, "TableSmall"),
                _paragraph(expected, styles, "TableSmall"),
                _paragraph(returned, styles, "TableSmall"),
                "Yes" if result["correct"] else "No",
                f"{result['median_response_ms']:.3f}",
            ]
        )
    story.append(
        _table(
            result_rows,
            [38 * mm, 38 * mm, 47 * mm, 18 * mm, 20 * mm],
        )
    )
    story.extend(
        [
            Spacer(1, 3 * mm),
            _paragraph(
                f"Correctness against the provided source data: "
                f"<b>{sum(bool(result['correct']) for result in results)}/{len(results)} "
                f"benchmarks pass</b>. The benchmark suite covers the historical summary, "
                "2022 standings, player statistics, match results, goal events, player "
                "appearances and image descriptors. Reported timings are local observations "
                "from this Neo4j instance and vary with hardware, cache state and database load; "
                "they are not a cross-system speed claim.",
                styles,
            ),
            _paragraph("Critical analysis", styles, "Subsection"),
            _paragraph(
                "The graph joins multiple independent sources through explicit match, team, "
                "player and provenance edges, reducing the work needed for cross-dataset "
                "questions to a single Cypher traversal. The benchmark compares query output "
                "with values derived from the input files rather than asking an LLM to judge "
                "it. Limitations include a small benchmark set, single-machine timings, and "
                "name-based reconciliation when external player identifiers differ across "
                "sources. Match-level analysis is limited to fields available in the selected "
                "source tables.",
                styles,
            ),
            PageBreak(),
            _paragraph("6. Conclusions and future work", styles, "Section"),
            _paragraph(
                "The implementation provides an end-to-end, reproducible multimedia information "
                "retrieval system: source preprocessing and auditing, RDF ontology and triple "
                "generation, Neo4j storage, Cypher retrieval, query benchmarks and a Streamlit "
                "interface. It includes 2022 match, goal and appearance data, which supports "
                "event-level questions rather than only tournament summaries. Player images "
                "contribute both descriptive metadata and a simple, inspectable visual feature.",
                styles,
            ),
            _paragraph("Limitations and future work", styles, "Subsection"),
            _paragraph(
                "The RGB histogram is intentionally simple and captures global color rather "
                "than semantics. Cross-source person identity matching depends on normalized "
                "names where no common stable key is supplied. The graph does not currently "
                "model video clips, tracking coordinates or rich tactical events. Evaluation "
                "could be expanded with more held-out questions, completeness checks for every "
                "input record, query plans and repeated measurements under controlled cache "
                "conditions. Further extensions include richer appearance/event facts, "
                "perceptual or learned image descriptors, validated entity-resolution links, "
                "indexes and schema constraints.",
                styles,
            ),
            _paragraph("References and data provenance", styles, "Subsection"),
            _paragraph(
                "1. jfjelstul/worldcup, CSV data at commit "
                f"{'35a8667f518b07469182ae16d35574dd0e7a00fb'}: "
                "https://github.com/jfjelstul/worldcup<br/>"
                "2. FIFA World Cup datasets: local professor-provided FIFA 2022 team, player "
                "statistics and all-player image files, preserved under dataset/.<br/>"
                "3. Cristiano Russo, <i>Homework: Multimedia Information Retrieval for Sports "
                "Analytics</i>, University of Naples Federico II, A.Y. 2025/2026.",
                styles,
            ),
        ]
    )

    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=17 * mm,
        bottomMargin=19 * mm,
        title="FIFA World Cup 2022 Multimedia Knowledge Graph",
        author="Information Retrieval Exam Project",
    )
    document.build(story, onFirstPage=_page_number, onLaterPages=_page_number)
    if document.page > 10:
        raise ValueError(
            f"The generated report is {document.page} pages; the assignment limit is 10."
        )
    return document.page


def main():
    parser = argparse.ArgumentParser(description="Build the exam project report PDF.")
    parser.add_argument(
        "--evaluation",
        type=Path,
        default=ROOT / "output" / "evaluation.json",
    )
    parser.add_argument("--output", type=Path, default=ROOT / "report.pdf")
    args = parser.parse_args()
    pages = build_report(args.evaluation, args.output)
    print(f"Created {args.output} ({pages} pages; within the 10-page limit).")


if __name__ == "__main__":
    main()
