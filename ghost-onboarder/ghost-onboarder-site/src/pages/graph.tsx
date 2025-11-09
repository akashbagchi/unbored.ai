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

  const nodes = g.nodes.map(n => ({
    id: n.id,
    position: { x: n.x, y: n.y },
    data: { label: n.label },
    style: {
      padding: 6, borderRadius: 12, background: "#fff",
      border: "1px solid #999", fontSize: 11,
    },
    draggable: false,
  }));

  const edges = g.edges.map((e, i) => ({
    id: `${e.source}-${e.target}-${i}`,
    source: e.source, target: e.target,
    style: { strokeWidth: 1.2, opacity: 0.75 },
  }));

  return (
    <div
      style={{
        height: "calc(100vh - 0px)",   // full viewport height
        width: "100%",                 // full width
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
        fitViewOptions={{ padding: 0.12 }}  // small padding since the viewport is large
        panOnScroll
        zoomOnScroll
        proOptions={{ hideAttribution: true }}
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
      {/* Full-bleed: remove maxWidth to let the canvas fill the page */}
      <main style={{ margin: 0, padding: 0, maxWidth: "none" }}>
        <BrowserOnly>{() => <GraphClient />}</BrowserOnly>
      </main>
    </Layout>
  );
}
