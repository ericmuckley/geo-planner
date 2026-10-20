"""Range-advised reads with the declared scoped-policy identity check."""

from scoped_load import load_graph as compact_load
from range_graph import GraphPath
from range_hash import artifact
from xml_stream import report as graph_stream_report


def load_graph(path, block_size=1 << 20, **options):
    return compact_load(GraphPath(path, **options), block_size)


def load_checked(directory, manifest):
    graph, model = load_graph(directory / "graph.json")
    if graph.identity != manifest["graphIdentity"] or model != manifest["profile"]["model"]:
        raise ValueError("Reloaded graph/model differs")
    if artifact(directory / "graph.json") != manifest["artifacts"]["graph.json"]:
        raise ValueError("Graph changed during reload")
    reads = [row for row in graph_stream_report()["requests"] if row["path"] == str(directory / "graph.json")]
    if len(reads) != 1 or any(not row["closed"] or not row["eofObserved"] or row["readBytes"] != row["fileBytes"] or row["successfulAdviceBytes"] != row["readBytes"] or row["adviceErrors"] for row in reads):
        raise ValueError("Range-advised graph read incomplete")
    return graph


