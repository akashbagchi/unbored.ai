// src/pages/graph.tsx
import React, { useEffect, useState } from "react";
import BrowserOnly from "@docusaurus/BrowserOnly";
import Layout from "@theme/Layout";

function GraphClient() {
  const { ReactFlow, Background, Controls, MiniMap } = require("reactflow");
  require("reactflow/dist/style.css");

  const [g, setG] = useState<{nodes:any[]; edges:any[]}>({nodes:[], edges:[]});

  useEffect(() => {
    fetch("/graph_with_pos.json").then(r=>r.json()).then(setG);
  }, []);

  // Map JSON → ReactFlow elements (no layout; we trust x,y)
  const nodes = g.nodes.map(n => ({
    id: n.id,
    position: { x: n.x, y: n.y },
    data: { label: n.label },
    style: {
      padding: 6, borderRadius: 12, background: "#fff",
      border: "1px solid #999", fontSize: 11,
    },
  }));

  const edges = g.edges.map((e, i) => ({
    id: `${e.source}-${e.target}-${i}`,
    source: e.source, target: e.target,
    style: { strokeWidth: 1.2, opacity: 0.75 },
  }));

  return (
    <div style={{ height: "85vh", borderRadius: 12, overflow: "hidden" }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        panOnScroll
        zoomOnScroll
        onNodeClick={(_, node) => {
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
    <Layout title="Graph View" description="Precomputed layout (ReactFlow preset)">
      <main style={{ maxWidth: 1100, margin: "0 auto", padding: "2rem 1rem" }}>
        <h1>Graph View</h1>
        <p style={{ opacity: 0.8 }}>Precomputed x/y — instant render, zero client layout.</p>
        <BrowserOnly>{() => <GraphClient />}</BrowserOnly>
      </main>
    </Layout>
  );
}