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
  // Depth based on forward slashes in the node id (e.g., "src/utils/foo.ts" => level 2)
  const getLevel = (id: string) => {
    if (!id) return 0;
    // Normalize potential Windows-style backslashes if any ever appear
    const norm = id.replace(/\\/g, "/");
    const parts = norm.split("/").filter(Boolean);
    // If it's a leaf file at repo root (e.g., "README.md"), depth = 0
    return Math.max(0, parts.length - 1);
  };

  // A compact, high-contrast palette that loops if levels exceed length
  const LEVEL_COLORS = [
    "#4C78A8", // level 0
    "#F58518", // level 1
    "#54A24B", // level 2
    "#E45756", // level 3
    "#72B7B2", // level 4
    "#B279A2", // level 5
    "#FF9DA6", // level 6
    "#9C755F", // level 7
  ];

  const colorForLevel = (lvl: number) => LEVEL_COLORS[lvl % LEVEL_COLORS.length];

  // Helper to make a soft background from the stroke color
  const withAlpha = (hex: string, alpha = 0.12) => {
    // Accept #RRGGBB
    const m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
    if (!m) return hex;
    const r = parseInt(m[1], 16);
    const g = parseInt(m[2], 16);
    const b = parseInt(m[3], 16);
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
          background: bg,                // color by file level
          border: `1.5px solid ${stroke}`, // color by file level
          fontSize: 11,
          opacity: isActive ? 1 : 0.15,
          transition: "opacity 120ms ease",
        },
        draggable: false,
        // Provide a tooltip with level for quick debugging/UX
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
        style: {
          strokeWidth: 1.2,
          stroke: "#98A6B3",
          opacity: touchesHover ? 0.8 : 0.1,
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
      }}
    >
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
        // Make clicking do nothing
        onNodeClick={() => {}}
        minZoom={0.2}
        maxZoom={2}
      >
        <Background />
        {/* MiniMap inherits node styles by default; this keeps a nice overview */}
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
