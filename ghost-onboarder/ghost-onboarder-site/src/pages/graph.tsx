// src/pages/graph.tsx
import React, { useEffect, useMemo, useRef, useState } from "react";
import BrowserOnly from "@docusaurus/BrowserOnly";
import Layout from "@theme/Layout";

function GraphClient() {
  const { ReactFlow, Background, Controls, MiniMap } = require("reactflow");
  require("reactflow/dist/style.css");

  const [g, setG] = useState<{ nodes: any[]; edges: any[] }>({ nodes: [], edges: [] });
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  // --- DEV-ONLY: suppress Chrome's noisy ResizeObserver overlay error ---
  useEffect(() => {
    const handler = (e: ErrorEvent) => {
      if (e?.message && e.message.includes("ResizeObserver loop")) {
        e.stopImmediatePropagation();
      }
    };
    window.addEventListener("error", handler);
    return () => window.removeEventListener("error", handler);
  }, []);
  // ---------------------------------------------------------------------

  useEffect(() => {
    fetch("/graph_with_pos.json").then((r) => r.json()).then(setG);
  }, []);

  // Build a quick neighbor index for hover highlighting
  const neighbors = useMemo(() => {
    const m = new Map<string, Set<string>>();
    for (const n of g.nodes || []) m.set(n.id, new Set());
    for (const e of g.edges || []) {
      m.get(e.source)?.add(e.target);
      m.get(e.target)?.add(e.source);
    }
    return m;
  }, [g]);

  // --- File-level coloring helpers --------------------------------------
  const getLevel = (id: string) => {
    if (!id) return 0;
    const norm = id.replace(/\\/g, "/");
    const parts = norm.split("/").filter(Boolean);
    return Math.max(0, parts.length - 1);
  };

  const LEVEL_COLORS = [
    "#4C78A8", "#F58518", "#54A24B", "#E45756",
    "#72B7B2", "#B279A2", "#FF9DA6", "#9C755F",
  ];
  const colorForLevel = (lvl: number) => LEVEL_COLORS[lvl % LEVEL_COLORS.length];

  const withAlpha = (hex: string, alpha = 0.12) => {
    const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    if (!m) return hex;
    const r = parseInt(m[1], 16), g = parseInt(m[2], 16), b = parseInt(m[3], 16);
    return `rgba(${r}, ${g}, ${b}, ${alpha})`;
  };
  // ----------------------------------------------------------------------

  // RAF-throttled hover setter to reduce layout churn
  const hoverRaf = useRef<number | null>(null);
  const setHoverThrottled = (id: string | null) => {
    if (hoverRaf.current) cancelAnimationFrame(hoverRaf.current);
    hoverRaf.current = requestAnimationFrame(() => setHoveredId(id));
  };

  const nodes = useMemo(() => {
    return (g.nodes || []).map((n) => {
      const isActive =
        !hoveredId ||
        hoveredId === n.id ||
        neighbors.get(hoveredId || "")?.has(n.id);

      const level = getLevel(n.id);
      const stroke = colorForLevel(level);
      const bg = withAlpha(stroke, 0.14);

      return {
        id: n.id,
        position: { x: n.x, y: n.y },
        data: { label: n.label },
        style: {
          padding: 6,
          borderRadius: 12,
          background: bg,
          border: `1.5px solid ${stroke}`,
          fontSize: 11,
          opacity: isActive ? 1 : 0.15,
          transition: "opacity 120ms ease",
        },
        draggable: false,
        title: `Level ${level} • ${n.id}`,
      };
    });
  }, [g.nodes, hoveredId, neighbors]);

  const edges = useMemo(() => {
    return (g.edges || []).map((e, i) => {
      const touchesHover =
        !hoveredId ||
        e.source === hoveredId ||
        e.target === hoveredId ||
        (neighbors.get(hoveredId || "")?.has(e.source) &&
         neighbors.get(hoveredId || "")?.has(e.target));

      return {
        id: `${e.source}-${e.target}-${i}`,
        source: e.source,
        target: e.target,
        className: touchesHover ? "edge-pulse" : "edge-dim",
        style: {
          strokeWidth: 1.2,
          stroke: "#98A6B3",
          opacity: touchesHover ? 0.85 : 0.1,
          transition: "opacity 120ms ease",
        },
      };
    });
  }, [g.edges, hoveredId, neighbors]);

  return (
    <div
      style={{
        height: "calc(100vh - 0px)",
        width: "100%",
        borderRadius: 0,
        overflow: "hidden",
        background: "#fafafa",
        borderTop: "1px solid #e9ecef",
        position: "relative",
      }}
    >
      {/* Edge pulse keyframes + class targeting */}
      <style>{`
        @keyframes edgePulse {
          0%   { opacity: 0.55; }
          50%  { opacity: 0.95; }
          100% { opacity: 0.55; }
        }
        /* React Flow wraps edges in <g>; animate its <path> when active */
        g.edge-pulse path { animation: edgePulse 2400ms ease-in-out infinite; }
        g.edge-dim   path { animation: none; }
      `}</style>

      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        fitViewOptions={{ padding: 0.12 }}
        panOnScroll
        zoomOnScroll
        proOptions={{ hideAttribution: true }}
        onNodeMouseEnter={(_, node) => setHoverThrottled(node.id)}
        onNodeMouseLeave={() => setHoverThrottled(null)}
        onNodeClick={() => {}}
        minZoom={0.2}
        maxZoom={2}
      >
        <Background />
        <MiniMap pannable zoomable />
        <Controls position="bottom-right" />
      </ReactFlow>
    </div>
  );
}

export default function GraphPage() {
  return (
    <Layout title="Graph View" description="Precomputed layout (spaced)">
      <main style={{ margin: 0, padding: 0, maxWidth: "none" }}>
        <BrowserOnly>{() => <GraphClient />}</BrowserOnly>
      </main>
    </Layout>
  );
}
