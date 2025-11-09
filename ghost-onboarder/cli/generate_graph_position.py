# scripts/layout.py
import json, networkx as nx, sys, math

IN  = sys.argv[1] if len(sys.argv) > 1 else "../ghost-onboarder-site/static/graph.json"
OUT = sys.argv[2] if len(sys.argv) > 2 else "../ghost-onboarder-site/static/graph_with_pos.json"

with open(IN) as f:
    data = json.load(f)

G = nx.Graph()
G.add_nodes_from([n["id"] for n in data["nodes"]])
G.add_edges_from([(e["source"], e["target"]) for e in data["edges"]])

# Try both
# pos = nx.spring_layout(G, k=None, iterations=200, seed=42)
pos = nx.kamada_kawai_layout(G)  # nice, deterministic for many graphs

# Normalize to a centered viewport (~1200x800 logical units)
xs = [p[0] for p in pos.values()]
ys = [p[1] for p in pos.values()]
minx, maxx = min(xs), max(xs)
miny, maxy = min(ys), max(ys)

def map_range(v, a, b, A, B):
    return A if a == b else A + (v - a) * (B - A) / (b - a)

WIDTH, HEIGHT = 1200, 800
nodes_out = []
for n in data["nodes"]:
    x, y = pos[n["id"]]
    nodes_out.append({
        "id": n["id"],
        "label": n.get("label", n["id"]),
        "x": map_range(x, minx, maxx, -WIDTH/2,  WIDTH/2),
        "y": map_range(y, miny, maxy, -HEIGHT/2, HEIGHT/2)
    })

out = {"nodes": nodes_out, "edges": data["edges"]}
with open(OUT, "w") as f:
    json.dump(out, f, indent=2)
print(f"Wrote {OUT}")
