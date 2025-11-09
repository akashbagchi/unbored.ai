import json, networkx as nx, sys, math, os, re, fnmatch
from math import log10, ceil
from networkx.algorithms.community import greedy_modularity_communities

# ==== your existing filtering config can stay here if you merged earlier ====
# (If you didn't add filters, you can ignore this section and feed a raw graph.json.)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def read_json(path):
    with open(path) as f: return json.load(f)

def write_json(path, obj):
    with open(path, "w") as f: json.dump(obj, f, indent=2)

def map_range(v, a, b, A, B):
    return (A + B)/2 if a == b else A + (v - a) * (B - A) / (b - a)

# ---------------- Layout helpers ---------------- #

def adaptive_params(n):
    """
    Pick spring 'k', extra spread, min_dist, iterations based on graph size.
    Grows spacing & separation with n while keeping runtime reasonable.
    """
    n = max(1, n)
    lg = max(0.0, log10(n))               # 10→1, 100→2, 1000→3...
    k      = 1.8 / (n ** 0.5) * (1.0 + 0.15*lg)      # slightly stronger repel for large n
    spread = 1.6 + 0.45 * lg                          # expand canvas for readability
    min_d  = 80.0 + 22.0 * lg                         # raise no-clash distance
    iters  = int(min(800, 220 + 4.0*n))               # more iterations for stability, capped
    return k, spread, min_d, iters

def adaptive_viewport(n):
    """
    Scale viewport with size so labels don't pile up.
    Keeps ~16:9, grows gently with sqrt(n).
    """
    base_w, base_h = 1800.0, 950.0
    s = min(2.2, max(1.0, (n/50.0) ** 0.5))           # 50 nodes ~= 1.0, 200 nodes ~= 2.0
    return int(base_w*s), int(base_h*s)

def de_overlap(pos, min_dist, passes=3):
    nodes_list = list(pos.keys())
    n = len(nodes_list)
    for _ in range(passes):
        for i in range(n):
            xi, yi = pos[nodes_list[i]]
            for j in range(i + 1, n):
                xj, yj = pos[nodes_list[j]]
                dx, dy = xj - xi, yj - yi
                dist = math.hypot(dx, dy) or 1e-6
                if dist < min_dist:
                    push = 0.5 * (min_dist - dist) / dist
                    ox, oy = dx * push, dy * push
                    pos[nodes_list[i]] = (xi - ox, yi - oy)
                    pos[nodes_list[j]] = (xj + ox, yj + oy)
    return pos

def normalize_box(subpos):
    xs = [p[0] for p in subpos.values()] or [0]
    ys = [p[1] for p in subpos.values()] or [0]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    w = max(1e-6, maxx - minx)
    h = max(1e-6, maxy - miny)
    out = {}
    for k,(x,y) in subpos.items():
        out[k] = ((x - minx)/w - 0.5, (y - miny)/h - 0.5)  # centered in [-0.5,0.5]
    return out

def pack_communities(G, iters, k_global):
    """
    Community-aware packing:
      1) Find communities (greedy modularity).
      2) Layout each community locally.
      3) Place community centroids on a circle.
    Works without extra deps.
    """
    if G.number_of_nodes() == 0:
        return {}

    comms = list(greedy_modularity_communities(G))
    if len(comms) <= 1:
        # fall back to global layout
        return nx.spring_layout(G, k=k_global, iterations=iters, seed=42, center=(0.0,0.0), dim=2)

    # Layout each community
    sub_positions = {}
    sizes = []
    for c in comms:
        H = G.subgraph(c).copy()
        k_local = 1.6 / (max(1, H.number_of_nodes()) ** 0.5)
        subpos = nx.spring_layout(H, k=k_local, iterations=max(200, iters//2), seed=42, center=(0.0,0.0), dim=2)
        subpos = normalize_box(subpos)
        sub_positions[len(sizes)] = (H, subpos)
        sizes.append(H.number_of_nodes())

    # Place community centers on a circle proportional to their sizes
    K = len(comms)
    angle_step = 2*math.pi / K
    R = 8.0 + 0.8 * (sum(sizes) ** 0.5)  # radius grows with total size

    pos = {}
    for idx, (H, subpos) in sub_positions.items():
        theta = idx * angle_step
        cx, cy = R*math.cos(theta), R*math.sin(theta)
        # scale each sub-layout box according to comm size so larger comms get more space
        scale = 6.0 + 0.35 * (H.number_of_nodes() ** 0.5)
        for n, (x, y) in subpos.items():
            pos[n] = (cx + x*scale, cy + y*scale)

    return pos

# ---------------- Main ---------------- #

def main():
    IN  = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE_DIR, "../ghost-onboarder-site/static/graph.json")
    OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(BASE_DIR, "../ghost-onboarder-site/static/graph_with_pos.json")

    data = read_json(IN)

    # Build graph from current JSON as-is (assuming nodes:{id}, edges:{source,target})
    G = nx.Graph()
    node_ids = [n["id"] for n in data.get("nodes", [])]
    G.add_nodes_from(node_ids)
    for e in data.get("edges", []):
        s, t = e.get("source"), e.get("target")
        if s in G and t in G:
            G.add_edge(s, t)

    n = max(1, G.number_of_nodes())

    # --- Adaptive params ---
    k, spread, min_dist, iterations = adaptive_params(n)

    # --- Choose layout strategy ---
    if n >= 60:
        # community pack for larger graphs
        pos = pack_communities(G, iterations, k)
    else:
        pos = nx.spring_layout(G, k=k, iterations=iterations, seed=42, center=(0.0, 0.0), dim=2)

    # Scale out a bit
    for node in pos:
        x, y = pos[node]
        pos[node] = (x * spread, y * spread)

    # Light de-overlap
    pos = de_overlap(pos, min_dist=min_dist, passes=3)

    # Adaptive viewport
    WIDTH, HEIGHT = adaptive_viewport(n)
    xs = [p[0] for p in pos.values()] or [0]
    ys = [p[1] for p in pos.values()] or [0]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)

    nodes_out = []
    for nobj in data.get("nodes", []):
        nid = nobj["id"]
        x, y = pos.get(nid, (0.0, 0.0))
        nodes_out.append({
            "id": nid,
            "label": nobj.get("label", nid),
            "x": map_range(x, minx, maxx, -WIDTH/2,  WIDTH/2),
            "y": map_range(y, miny, maxy, -HEIGHT/2, HEIGHT/2),
        })

    out = {"nodes": nodes_out, "edges": data.get("edges", [])}
    write_json(OUT, out)

    print(f"Wrote {OUT} with {len(nodes_out)} nodes / {len(out['edges'])} edges.")
    print(f"Params: n={n}, k={k:.4f}, spread={spread:.2f}, min_dist={min_dist:.1f}, iters={iterations}, viewport={WIDTH}x{HEIGHT}")

if __name__ == "__main__":
    main()