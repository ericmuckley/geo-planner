"""Use the frozen compact parser with explicit legacy/scoped graph identities."""

from compact_load import Reader
from compact_storage import BaseGraph, Csr, Roads, States, digest
from maneuver_graph import ManeuverGraph
from barrier_policy import MODEL_ID
from scoped_member_lookup import POLICY_ID


def load_graph(path, block_size=1 << 20):
    data, roads, base_rows, rows, states, initial_count = {}, Roads(), Csr(), Csr(), None, 0
    seen = set()
    with path.open() as stream:
        reader = Reader(stream, block_size)
        reader.take("{")
        while True:
            key = reader.value()
            if key in seen: raise ValueError("Duplicate graph field")
            seen.add(key); reader.take(":")
            if key == "roads":
                for row in reader.rows(): roads.append(row)
            elif key in {"baseTransitions", "transitions"}:
                target = base_rows if key == "baseTransitions" else rows
                for row in reader.rows(): target.append(row)
            elif key == "initialStates":
                for index in reader.rows():
                    if type(index) is not int or index != initial_count: raise ValueError("Initial state ordering differs")
                    initial_count += 1
            elif key == "states":
                if "roads" not in seen: raise ValueError("Canonical graph requires roads before states")
                states = States(len(roads), {})
                count = 0
                for row in reader.rows():
                    if count < len(roads):
                        if row["road"] != count: raise ValueError("Initial road/state ordering differs")
                        if row["history"]: states.initial_history[count] = tuple(row["history"])
                    else: states.extra.append((row["road"], tuple(row["history"])))
                    count += 1
                if count != len(states): raise ValueError("Incomplete states")
            elif key in {"model", "baseIdentity", "graphIdentity", "patterns"}: data[key] = reader.value()
            else: raise ValueError(f"Unknown graph field {key}")
            if reader.peek() == "}": break
            reader.take(",")
        reader.take("}")
        if reader.peek(): raise ValueError("Trailing graph data")
    expected = {"roads", "baseTransitions", "transitions", "states", "initialStates", "model", "baseIdentity", "graphIdentity", "patterns"}
    if seen != expected or states is None or initial_count != len(roads) or len(base_rows) != len(roads) or len(rows) != len(states):
        raise ValueError("Incomplete compact graph")
    base_id = digest({"roads": roads, "transitions": base_rows})
    identity = {"model": data["model"].get("id", "exploratory-static-car-v2"), "baseIdentity": base_id, "patterns": data["patterns"], "states": states, "transitions": rows}
    if "restrictionGeometryPolicy" in data["model"]:
        if data["model"]["restrictionGeometryPolicy"] != POLICY_ID or data["model"].get("id") != MODEL_ID:
            raise ValueError("Unsupported restriction-geometry model")
        identity["restrictionGeometryPolicy"] = POLICY_ID
    graph_id = digest(identity)
    if base_id != data["baseIdentity"] or graph_id != data["graphIdentity"]: raise ValueError("Reloaded identity differs")
    return ManeuverGraph(BaseGraph(roads, base_rows, [], base_id), states, range(len(roads)), rows, data["patterns"], [], graph_id), data["model"]
