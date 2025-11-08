// src/pages/graph.tsx
import React, { useEffect, useMemo, useState } from "react";
import BrowserOnly from "@docusaurus/BrowserOnly";
import Layout from "@theme/Layout";

/**
 * A lightweight, Obsidian-style Graph View for Ghost Onboarder.
 * Reads static/graph.json and renders it with React Flow.
 */
function GraphInner() {
  const [data, setData] = useState<{ nodes: any[]; edges: any[] }>({ nodes: [], edges: [] });
  const [rf, setRf] = useState<any>(null);

  // Hooks declared once; will never be conditionally skipped
  const [nodesState, setNodes] = useState<any[]>([]);
  const [edgesState, setEdges] = useState<any[]>([]);

  // Load JSON + ReactFlow module
  useEffect(() => {
    fetch("/graph.json")
      .then((r) => r.json())
      .then(setData)
      .catch((err) => console.error("Failed to load graph.json", err));

    import("reactflow")
      .then(async (mod) => {
        await import("reactflow/dist/style.css");
        setRf(mod);
      })
      .catch((err) => console.error("Failed to load ReactFlow", err));
  }, []);

  // Compute layout once data is available
  const { nodes, edges } = useMemo(() => {
    const N = Math.max(1, data.nodes.length);
    const radius = 220;
    const cx = 400;
    const cy = 300;

    const nodes = (data.nodes || []).map((n, i) => {
      const angle = (2 * Math.PI * i) / N;
      return {
        id: n.id,
        position: {
          x: cx + radius * Math.cos(angle),
          y: cy + radius * Math.sin(angle),
        },
        data: { label: n.label },
        style: {
          padding: 8,
          borderRadius: 12,
          fontSize: 12,
          background: "#fff",
          border: "1px solid #ccc",
        },
      };
    });

    const edges = (data.edges || []).map((e, i) => ({
      id: `${e.source}-${e.target}-${i}`,
      source: e.source,
      target: e.target,
      animated: true,
    }));

    return { nodes, edges };
  }, [data]);

  // Sync computed graph with state
  useEffect(() => {
    setNodes(nodes);
    setEdges(edges);
  }, [nodes, edges]);

  // Before ReactFlow loads, show fallback
  if (!rf) return <div style={{ padding: 20 }}>Loading graph view…</div>;

  const { ReactFlow, Background, Controls, MiniMap } = rf;

  return (
    <div style={{ height: "80vh", borderRadius: 12, overflow: "hidden" }}>
      <ReactFlow
        nodes={nodesState}
        edges={edgesState}
        fitView
        onNodeClick={(_, node) => {
          // optional: open related doc page if it exists
          const slug = node.id.replace(/[\/.]/g, "-");
          window.open(`/docs/${slug}`, "_self");
        }}
      >
        <Background />
        <MiniMap pannable zoomable />
        <Controls />
      </ReactFlow>
    </div>
  );
}

export default function GraphPage() {
  return (
    <Layout
      title="Graph View"
      description="Visualize file and module relationships inside Ghost Onboarder"
    >
      <main style={{ maxWidth: 980, margin: "0 auto", padding: "2rem 1rem" }}>
        <h1 style={{ marginBottom: 12 }}>Graph View</h1>
        <p style={{ marginTop: 0, opacity: 0.8 }}>
          Circles represent files or modules. Lines show import or dependency relationships.
          Click a node to navigate to its documentation.
        </p>
        <BrowserOnly>{() => <GraphInner />}</BrowserOnly>
      </main>
    </Layout>
  );
}
