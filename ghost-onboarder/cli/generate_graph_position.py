# scripts/layout.py
import json, networkx as nx, sys, math
import os, sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if len(sys.argv) > 1:
    IN = sys.argv[1]
else:
    IN = os.path.join(BASE_DIR, "../ghost-onboarder-site/static/graph.json")

if len(sys.argv) >1:
    OUT = sys.argv[1]
else:
    OUT = os.path.join(BASE_DIR, "../ghost-onboarder-site/static/graph_with_pos.json")


with open(IN) as f:
    data = json.load(f)

G = nx.Graph()
G.add_nodes_from([n["id"] for n in data["nodes"]])
G.add_edges_from([(e["source"], e["target"]) for e in data["edges"]])

n = max(1, G.number_of_nodes())

# 1) Spread out: larger k => more spacing; iterations for stability
#    (If you prefer, use nx.kamada_kawai_layout(G) instead.)
k = 1.8 / (n ** 0.5)  # bump this to spread more
pos = nx.spring_layout(G, k=k, iterations=300, seed=42, center=(0.0, 0.0), dim=2)

# 2) Uniform scale up to create more whitespace
spread = 1.8  # increase if needed (2.0, 2.2…)
for node in pos:
    x, y = pos[node]
    pos[node] = (x * spread, y * spread)

# 3) Light de-overlap pass (nudges nodes apart if closer than min_dist)
min_dist = 90.0  # "no-clash" distance in logical units; raise if labels still collide
passes = 3
nodes_list = list(G.nodes())
for _ in range(passes):
    for i in range(n):
        xi, yi = pos[nodes_list[i]]
        for j in range(i + 1, n):
            xj, yj = pos[nodes_list[j]]
            dx, dy = xj - xi, yj - yi
            dist = math.hypot(dx, dy) or 1e-6
            if dist < min_dist:
                # push both nodes away from each other
                push = 0.5 * (min_dist - dist) / dist
                ox, oy = dx * push, dy * push
                pos[nodes_list[i]] = (xi - ox, yi - oy)
                pos[nodes_list[j]] = (xj + ox, yj + oy)

# 4) Map to a wide landscape viewport (fills screen nicely)
WIDTH, HEIGHT = 1800, 950  # landscape
xs = [p[0] for p in pos.values()]
ys = [p[1] for p in pos.values()]
minx, maxx = min(xs), max(xs)
miny, maxy = min(ys), max(ys)

def map_range(v, a, b, A, B):
    return (A + B)/2 if a == b else A + (v - a) * (B - A) / (b - a)

nodes_out = []
for nobj in data["nodes"]:
    nid = nobj["id"]
    x, y = pos[nid]
    nodes_out.append({
        "id": nid,
        "label": nobj.get("label", nid),
        "x": map_range(x, minx, maxx, -WIDTH/2,  WIDTH/2),
        "y": map_range(y, miny, maxy, -HEIGHT/2, HEIGHT/2),
    })

out = {"nodes": nodes_out, "edges": data["edges"]}
with open(OUT, "w") as f:
    json.dump(out, f, indent=2)

print(f"Wrote {OUT} with {len(nodes_out)} nodes. "
      f"Try tweaking k={k}, spread={spread}, min_dist={min_dist} if needed.")
