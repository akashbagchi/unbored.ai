import React, { useEffect, useMemo, useRef, useState } from "react";
import BrowserOnly from "@docusaurus/BrowserOnly";
import Layout from "@theme/Layout";
import { useColorMode } from "@docusaurus/theme-common";

interface NodeData {
  id: string;
  label: string;
  x: number;
  y: number;
  lang?: string;
  dir?: string;
  is_test?: boolean;
  in_degree: number;
  out_degree: number;
}

interface GraphData {
  nodes: NodeData[];
  edges: { source: string; target: string }[];
}

const DIR_COLORS = [
  "#4C78A8", "#F58518", "#54A24B", "#E45756",
  "#72B7B2", "#B279A2", "#FF9DA6", "#9C755F",
  "#BAB0AC", "#86BCB6",
];

// Given an angle (degrees, 0 = right, 90 = down), returns the source and target handle IDs.
function angleToHandles(deg: number): { sh: string; th: string } {
  const d = ((deg % 360) + 360) % 360;
  if (d < 45 || d >= 315)  return { sh: "s-right",  th: "t-left"   }; // rightward
  if (d < 135)              return { sh: "s-bottom", th: "t-top"    }; // downward
  if (d < 225)              return { sh: "s-left",   th: "t-right"  }; // leftward
                            return { sh: "s-top",    th: "t-bottom" }; // upward
}

// Custom node that exposes handles on all 4 sides so edges can emerge from any direction.
const MultiHandleNode = ({ data }: any) => {
  const { Handle, Position } = require("reactflow");
  const hs: React.CSSProperties = { opacity: 0, width: 1, height: 1, minWidth: 0, minHeight: 0, background: "none", border: "none" };
  return (
    <>
      <Handle type="source" position={Position.Top}    id="s-top"    style={hs} />
      <Handle type="source" position={Position.Right}  id="s-right"  style={hs} />
      <Handle type="source" position={Position.Bottom} id="s-bottom" style={hs} />
      <Handle type="source" position={Position.Left}   id="s-left"   style={hs} />
      <Handle type="target" position={Position.Top}    id="t-top"    style={hs} />
      <Handle type="target" position={Position.Right}  id="t-right"  style={hs} />
      <Handle type="target" position={Position.Bottom} id="t-bottom" style={hs} />
      <Handle type="target" position={Position.Left}   id="t-left"   style={hs} />
      <div style={{ textAlign: "center", lineHeight: 1.3 }}>{data.label}</div>
    </>
  );
};

const NODE_TYPES = { mh: MultiHandleNode };

function GraphClient() {
  const { ReactFlow, Background, Controls, MiniMap, MarkerType } = require("reactflow");
  const { forceSimulation, forceLink, forceManyBody, forceX, forceY, forceCollide } = require("d3-force");
  require("reactflow/dist/style.css");

  const { colorMode } = useColorMode();
  const isDark = colorMode === "dark";

  const [g, setG] = useState<GraphData>({ nodes: [], edges: [] });
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hideIsolates, setHideIsolates] = useState(true);
  const [hideTests, setHideTests] = useState(false);
  const [fitViewOnce, setFitViewOnce] = useState(true);

  // Live force simulation positions
  const [simPos, setSimPos] = useState<Map<string, { x: number; y: number }>>(new Map());
  const simRef = useRef<any>(null);
  const posRef = useRef<Map<string, { x: number; y: number }>>(new Map());
  const pinnedRef = useRef<Set<string>>(new Set());
  const frameRef = useRef(0);

  useEffect(() => {
    fetch("/graph_with_pos.json").then((r) => r.json()).then(setG);
  }, []);

  // Color mixing helpers
  const mixWithWhite = (hex: string, t = 0.85) => {
    const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    if (!m) return "#ffffff";
    const r = parseInt(m[1], 16), gv = parseInt(m[2], 16), b = parseInt(m[3], 16);
    const toHex = (v: number) => Math.round(v).toString(16).padStart(2, "0");
    return `#${toHex(r * (1 - t) + 255 * t)}${toHex(gv * (1 - t) + 255 * t)}${toHex(b * (1 - t) + 255 * t)}`;
  };

  const mixWithWarmDark = (hex: string, t = 0.80) => {
    const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    if (!m) return "#1a1816";
    const r = parseInt(m[1], 16), gv = parseInt(m[2], 16), b = parseInt(m[3], 16);
    const toHex = (v: number) => Math.round(v).toString(16).padStart(2, "0");
    return `#${toHex(r * (1 - t) + 26 * t)}${toHex(gv * (1 - t) + 24 * t)}${toHex(b * (1 - t) + 22 * t)}`;
  };

  // Directory color map (sorted for deterministic assignment)
  const dirColorMap = useMemo(() => {
    const dirs = Array.from(new Set((g.nodes || []).map(n => n.dir ?? "(root)"))).sort();
    const m = new Map<string, string>();
    dirs.forEach((d, i) => m.set(d, DIR_COLORS[i % DIR_COLORS.length]));
    return m;
  }, [g.nodes]);

  // Neighbor adjacency for hover fade
  const neighbors = useMemo(() => {
    const m = new Map<string, Set<string>>();
    for (const n of g.nodes || []) m.set(n.id, new Set());
    for (const e of g.edges || []) {
      m.get(e.source)?.add(e.target);
      m.get(e.target)?.add(e.source);
    }
    return m;
  }, [g]);

  // Importer/importee index for detail panel
  const edgeIndex = useMemo(() => {
    const importers = new Map<string, string[]>();
    const importees = new Map<string, string[]>();
    for (const n of g.nodes || []) {
      importers.set(n.id, []);
      importees.set(n.id, []);
    }
    for (const e of g.edges || []) {
      importees.get(e.source)?.push(e.target);
      importers.get(e.target)?.push(e.source);
    }
    return { importers, importees };
  }, [g]);

  // Max degree for node size scaling
  const maxDegree = useMemo(() => {
    const degs = (g.nodes || []).map(n => (n.in_degree ?? 0) + (n.out_degree ?? 0));
    return Math.max(1, ...degs);
  }, [g.nodes]);

  // Apply visibility filters
  const { visibleNodes, visibleEdges } = useMemo(() => {
    const connectedIds = new Set<string>();
    for (const e of g.edges || []) {
      connectedIds.add(e.source);
      connectedIds.add(e.target);
    }
    const vNodes = (g.nodes || []).filter(n => {
      if (hideIsolates && !connectedIds.has(n.id)) return false;
      if (hideTests && (n.is_test ?? false)) return false;
      return true;
    });
    const vIds = new Set(vNodes.map(n => n.id));
    const vEdges = (g.edges || []).filter(e => vIds.has(e.source) && vIds.has(e.target));
    return { visibleNodes: vNodes, visibleEdges: vEdges };
  }, [g, hideIsolates, hideTests]);

  // Live d3-force simulation — restarts when visible graph changes
  useEffect(() => {
    if (simRef.current) simRef.current.stop();
    if (!visibleNodes.length) return;

    pinnedRef.current = new Set();
    frameRef.current = 0;

    // Seed from Python-computed positions so nodes start near their expected positions
    const simNodes: any[] = visibleNodes.map(n => ({
      id: n.id,
      x: n.x,
      y: n.y,
    }));
    const nodeSet = new Set(simNodes.map((n: any) => n.id));

    const simLinks = visibleEdges
      .filter(e => nodeSet.has(e.source) && nodeSet.has(e.target))
      .map(e => ({ source: e.source, target: e.target }));

    const sim = forceSimulation(simNodes)
      .force("link", forceLink(simLinks).id((d: any) => d.id).distance(220).strength(0.45))
      .force("charge", forceManyBody().strength(-600).distanceMax(800))
      .force("x", forceX(0).strength(0.04))
      .force("y", forceY(0).strength(0.04))
      .force("collide", forceCollide().radius(70).strength(0.8))
      .alphaDecay(0.015)   // slower decay = longer, smoother animation
      .velocityDecay(0.35);

    sim.on("tick", () => {
      frameRef.current++;
      const updated = new Map<string, { x: number; y: number }>();
      for (const [k, v] of posRef.current) updated.set(k, v);
      for (const n of sim.nodes() as any[]) {
        if (!pinnedRef.current.has(n.id)) {
          updated.set(n.id, { x: n.x, y: n.y });
        }
      }
      posRef.current = updated;
      // Update React state every 2 ticks to balance smoothness vs cost
      if (frameRef.current % 2 === 0) {
        setSimPos(new Map(updated));
      }
    });

    sim.on("end", () => setSimPos(new Map(posRef.current)));

    simRef.current = sim;
    return () => { sim.stop(); };
  }, [g, hideIsolates, hideTests]);

  // RAF-throttled hover setter
  const hoverRaf = useRef<number | null>(null);
  const setHoverThrottled = (id: string | null) => {
    if (hoverRaf.current) cancelAnimationFrame(hoverRaf.current);
    hoverRaf.current = requestAnimationFrame(() => setHoveredId(id));
  };

  // ReactFlow nodes — positions from simulation, falling back to Python coords
  const nodes = useMemo(() => {
    return visibleNodes.map(n => {
      const pos = simPos.get(n.id) ?? { x: n.x, y: n.y };
      const isActive = !hoveredId || hoveredId === n.id || neighbors.get(hoveredId)?.has(n.id);
      const dir = n.dir ?? "(root)";
      const stroke = dirColorMap.get(dir) ?? "#888888";
      const bg = isDark ? mixWithWarmDark(stroke, 0.80) : mixWithWhite(stroke, 0.86);
      const totalDeg = (n.in_degree ?? 0) + (n.out_degree ?? 0);
      const nodeWidth = 100 + Math.min((totalDeg / maxDegree) * 80, 80);
      const isSelected = selectedId === n.id;

      return {
        id: n.id,
        type: "mh",
        position: pos,
        data: { label: n.label },
        style: {
          padding: 6,
          borderRadius: 12,
          background: bg,
          border: isSelected ? `2px solid ${stroke}` : `1.5px solid ${stroke}`,
          fontSize: 11,
          color: isDark ? "#f0ede8" : "#1a1a1a",
          opacity: isActive ? 1 : 0.2,
          transition: "opacity 120ms ease",
          width: nodeWidth,
          cursor: "pointer",
          boxShadow: isSelected ? `0 0 0 3px ${stroke}55` : "none",
        },
        draggable: true,
      };
    });
  }, [visibleNodes, simPos, hoveredId, neighbors, isDark, dirColorMap, maxDegree, selectedId]);

  // ReactFlow edges — straight, from nearest side of source to nearest side of target
  const edges = useMemo(() => {
    return visibleEdges.map((e, i) => {
      const touchesHover =
        !hoveredId ||
        e.source === hoveredId ||
        e.target === hoveredId ||
        (neighbors.get(hoveredId)?.has(e.source) && neighbors.get(hoveredId)?.has(e.target));

      // Pick handles based on angle between the two nodes so the edge leaves
      // from the correct side rather than always top/bottom.
      const sp = simPos.get(e.source);
      const tp = simPos.get(e.target);
      let sourceHandle = "s-bottom";
      let targetHandle = "t-top";
      if (sp && tp) {
        const deg = Math.atan2(tp.y - sp.y, tp.x - sp.x) * (180 / Math.PI);
        ({ sh: sourceHandle, th: targetHandle } = angleToHandles(deg));
      }

      const edgeColor = isDark ? "#5c5248" : "#98A6B3";
      return {
        id: `${e.source}-${e.target}-${i}`,
        source: e.source,
        target: e.target,
        sourceHandle,
        targetHandle,
        type: "straight",
        markerEnd: {
          type: MarkerType.ArrowClosed,
          width: 14,
          height: 14,
          color: edgeColor,
        },
        className: touchesHover ? "edge-pulse" : "edge-dim",
        style: {
          strokeWidth: 1,
          stroke: edgeColor,
          opacity: touchesHover ? 0.75 : 0.08,
          transition: "opacity 120ms ease",
        },
      };
    });
  }, [visibleEdges, hoveredId, neighbors, isDark, simPos]);

  // Drag handlers — pin nodes in simulation when dragged
  const onNodeDrag = (_evt: React.MouseEvent, node: { id: string; position: { x: number; y: number } }) => {
    const simNodes = simRef.current?.nodes() as any[] | undefined;
    const simNode = simNodes?.find((n: any) => n.id === node.id);
    if (simNode) {
      simNode.fx = node.position.x;
      simNode.fy = node.position.y;
      simNode.x = node.position.x;
      simNode.y = node.position.y;
    }
    pinnedRef.current.add(node.id);
    simRef.current?.alpha(0.15).restart();
  };

  const onNodeDragStop = () => {
    // Keep nodes pinned after drag — they stay where placed
    // The simulation will reflow remaining free nodes around them
  };

  // Selected node data for detail panel
  const selectedNode = useMemo(
    () => (selectedId ? g.nodes.find(n => n.id === selectedId) ?? null : null),
    [selectedId, g.nodes]
  );

  const onNodeClick = (_evt: React.MouseEvent, node: { id: string }) => {
    setSelectedId(prev => (prev === node.id ? null : node.id));
  };

  const onPaneClick = () => setSelectedId(null);

  // Style helpers
  const pillStyle = (color: string): React.CSSProperties => ({
    display: "inline-flex", alignItems: "center", gap: 4,
    background: isDark ? mixWithWarmDark(color, 0.75) : mixWithWhite(color, 0.80),
    border: `1px solid ${color}`,
    borderRadius: 8, padding: "2px 7px",
    fontSize: 10, color: isDark ? "#f0ede8" : "#1a1a1a",
    whiteSpace: "nowrap",
  });

  const btnStyle = (active: boolean): React.CSSProperties => ({
    padding: "4px 10px", borderRadius: 8, fontSize: 11, cursor: "pointer",
    border: active
      ? `1px solid ${isDark ? "#6a8fcc" : "#4C78A8"}`
      : `1px solid ${isDark ? "#3a3633" : "#dee2e6"}`,
    background: active
      ? isDark ? "#2a3a55" : "#dce8f5"
      : isDark ? "#1a1816" : "#f8f9fa",
    color: isDark ? "#f0ede8" : "#1a1a1a",
    transition: "all 120ms ease",
  });

  const panelBase: React.CSSProperties = {
    position: "absolute", zIndex: 10,
    background: isDark ? "rgba(20,18,16,0.95)" : "rgba(255,255,255,0.95)",
    border: isDark ? "1px solid #3a3633" : "1px solid #dee2e6",
    borderRadius: 10, backdropFilter: "blur(8px)",
  };

  return (
    <div style={{
      height: "calc(100vh - 0px)", width: "100%",
      borderRadius: 0, overflow: "hidden",
      background: isDark ? "#0f0e0d" : "#fafafa",
      borderTop: isDark ? "1px solid #2e2b27" : "1px solid #e9ecef",
      position: "relative",
    }}>
      <style>{`
        @keyframes edgePulse {
          0%   { opacity: 0.45; }
          50%  { opacity: 0.85; }
          100% { opacity: 0.45; }
        }
        g.edge-pulse path { animation: edgePulse 2400ms ease-in-out infinite; }
        g.edge-dim   path { animation: none; }
        .react-flow__handle { opacity: 0 !important; pointer-events: none !important; }
      `}</style>

      {/* Filter bar — top left */}
      <div style={{ ...panelBase, top: 12, left: 12, padding: "10px 14px", maxWidth: 260 }}>
        <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
          <button style={btnStyle(!hideIsolates)} onClick={() => setHideIsolates(v => !v)}>
            {hideIsolates ? "Show" : "Hide"} isolated
          </button>
          <button style={btnStyle(hideTests)} onClick={() => setHideTests(v => !v)}>
            {hideTests ? "Show" : "Hide"} tests
          </button>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
          {Array.from(dirColorMap.entries()).map(([dir, color]) => (
            <span key={dir} style={pillStyle(color)}>
              <span style={{ width: 7, height: 7, borderRadius: "50%", background: color, display: "inline-block", flexShrink: 0 }} />
              {dir}
            </span>
          ))}
        </div>
      </div>

      {/* Detail panel — right side */}
      {selectedNode && (
        <div style={{ ...panelBase, top: 12, right: 12, width: 280, maxHeight: "calc(100vh - 80px)", padding: 14, overflowY: "auto" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
            <span style={{ fontWeight: 700, fontSize: 13, color: isDark ? "#f0ede8" : "#1a1a1a", wordBreak: "break-all", paddingRight: 8 }}>
              {selectedNode.label}
            </span>
            <button
              onClick={() => setSelectedId(null)}
              style={{ background: "none", border: "none", cursor: "pointer", fontSize: 18, lineHeight: 1, color: isDark ? "#a09890" : "#666", flexShrink: 0, padding: 0 }}
            >×</button>
          </div>

          <div style={{ color: isDark ? "#7a7068" : "#888", fontSize: 10, wordBreak: "break-all", marginBottom: 10 }}>
            {selectedNode.id}
          </div>

          <div style={{ display: "flex", gap: 5, flexWrap: "wrap", marginBottom: 14 }}>
            {selectedNode.lang && (
              <span style={{ ...pillStyle("#72B7B2"), fontSize: 10 }}>{selectedNode.lang}</span>
            )}
            {selectedNode.dir && (
              <span style={{ ...pillStyle(dirColorMap.get(selectedNode.dir) ?? "#888"), fontSize: 10 }}>
                {selectedNode.dir}
              </span>
            )}
            {selectedNode.is_test && (
              <span style={{ ...pillStyle("#F58518"), fontSize: 10 }}>test</span>
            )}
          </div>

          <div style={{ marginBottom: 12 }}>
            <div style={{ fontWeight: 600, fontSize: 11, color: isDark ? "#c0b8b0" : "#444", marginBottom: 5 }}>
              Imported by ({edgeIndex.importers.get(selectedNode.id)?.length ?? 0})
            </div>
            {(edgeIndex.importers.get(selectedNode.id) ?? []).length === 0
              ? <div style={{ fontSize: 11, color: isDark ? "#5a5248" : "#aaa", fontStyle: "italic" }}>nothing imports this</div>
              : (edgeIndex.importers.get(selectedNode.id) ?? []).map(id => (
                  <div key={id}
                    style={{ padding: "3px 0", cursor: "pointer", fontSize: 11, color: isDark ? "#88aaee" : "#0066cc" }}
                    onClick={() => setSelectedId(id)}
                  >
                    {id.split("/").pop()}
                  </div>
                ))
            }
          </div>

          <div>
            <div style={{ fontWeight: 600, fontSize: 11, color: isDark ? "#c0b8b0" : "#444", marginBottom: 5 }}>
              Imports ({edgeIndex.importees.get(selectedNode.id)?.length ?? 0})
            </div>
            {(edgeIndex.importees.get(selectedNode.id) ?? []).length === 0
              ? <div style={{ fontSize: 11, color: isDark ? "#5a5248" : "#aaa", fontStyle: "italic" }}>imports nothing</div>
              : (edgeIndex.importees.get(selectedNode.id) ?? []).map(id => (
                  <div key={id}
                    style={{ padding: "3px 0", cursor: "pointer", fontSize: 11, color: isDark ? "#88aaee" : "#0066cc" }}
                    onClick={() => setSelectedId(id)}
                  >
                    {id.split("/").pop()}
                  </div>
                ))
            }
          </div>
        </div>
      )}

      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={NODE_TYPES}
        fitView={fitViewOnce}
        fitViewOptions={{ padding: 0.15 }}
        onInit={() => setFitViewOnce(false)}
        panOnScroll
        zoomOnScroll
        proOptions={{ hideAttribution: true }}
        onNodeMouseEnter={(_evt: React.MouseEvent, node: { id: string }) => setHoverThrottled(node.id)}
        onNodeMouseLeave={() => setHoverThrottled(null)}
        onNodeClick={onNodeClick}
        onNodeDrag={onNodeDrag}
        onNodeDragStop={onNodeDragStop}
        onPaneClick={onPaneClick}
        minZoom={0.1}
        maxZoom={2}
      >
        <Background color={isDark ? "#2e2b27" : undefined} />
        <MiniMap
          pannable
          zoomable
          nodeColor={(n: { id: string }) => {
            const nd = g.nodes.find(x => x.id === n.id);
            return dirColorMap.get(nd?.dir ?? "(root)") ?? "#888888";
          }}
          style={{ background: isDark ? "#1a1816" : undefined }}
        />
        <Controls position="bottom-right" />
      </ReactFlow>
    </div>
  );
}

export default function GraphPage() {
  return (
    <Layout title="Graph View" description="Dependency graph with directory grouping">
      <main style={{ margin: 0, padding: 0, maxWidth: "none" }}>
        <BrowserOnly>{() => <GraphClient />}</BrowserOnly>
      </main>
    </Layout>
  );
}
