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

      return {
        id: n.id,
        position: { x: n.x, y: n.y },
        data: { label: n.label },
        style: {
          padding: 6,
          borderRadius: 12,
          background: "#fff",
          border: "1px solid #999",
          fontSize: 11,
          opacity: isActive ? 1 : 0.15,
          transition: "opacity 120ms ease",
        },
        draggable: false,
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
        onNodeClick={(_, node) => {
          const slug = node.id.replace(/[\/.]/g, "-");
          window.open(`/docs/${slug}`, "_self");
        }}
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