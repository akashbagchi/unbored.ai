import React, { useEffect, useMemo, useState } from "react";
import BrowserOnly from "@docusaurus/BrowserOnly";
import Layout from "@theme/Layout";

// React Flow is browser-only; import styles at runtime
function GraphInner() {
  const [data, setData] = useState<{nodes: any[]; edges: any[]}>({ nodes: [], edges: [] });
  const [rf, setRf] = useState<any>(null); // reactflow dynamic import

  useEffect(() => {
    (async () => {
      // Load ReactFlow only in browser to avoid SSR issues
      const mod = await import("reactflow");
      await import("reactflow/dist/style.css");
      setRf(mod);
    })();
    fetch("/graph.json").then(r => r.json()).then(setData);
  }, []);

  // Simple radial layout for deterministic positions (tiny POC)
  const { nodes, edges } = useMemo(() => {
    const N = Math.max(1, data.nodes.length);
    const radius = 220;
    const centerX = 400;
    const centerY = 280;

    const nodes = (data.nodes || []).map((n, i) => {
      const theta = (2 * Math.PI * i) / N;
      return {
        id: n.id,
        position: { x: centerX + radius * Math.cos(theta), y: centerY + radius * Math.sin(theta) },
        data: { label: n.label || n.id },
        style: { padding: 8, borderRadius: 12 }
      };
    });

    const edges = (data.edges || []).map((e, idx) => ({
      id: `${e.source}-${e.target}-${idx}`,
      source: e.source,
      target: e.target,
      animated: true,
      style: { strokeWidth: 1.5 }
    }));

    return { nodes, edges };
  }, [data]);

  // Not ready yet?
  if (!rf) return <div style={{padding: 16}}>Loading graph…</div>;
  const { ReactFlow, Background, Controls, MiniMap, useNodesState, useEdgesState, FitView } = rf as any;

  // Make nodes/edges editable in-state (optional for interactions)
  const [nState, setNodes, onNodesChange] = useNodesState(nodes);
  const [eState, setEdges, onEdgesChange] = useEdgesState(edges);

  useEffect(() => { setNodes(nodes); }, [nodes, setNodes]);
  useEffect(() => { setEdges(edges); }, [edges, setEdges]);

  const onNodeClick = (_: any, node: any) => {
    // Navigate to a doc if it exists; adapt mapping to your docs routing
    // Example: /docs/api-server.py  (replace / and .)
    const slug = node.id.replace(/\//g, "-").replace(/\./g, "-");
    window.open(`/docs/${slug}`, "_self"); // or route to your desired page
  };

  const proOptions = { hideAttribution: true };

  return (
    <div style={{ height: "80vh", borderRadius: 12, overflow: "hidden" }}>
      <ReactFlow
        nodes={nState}
        edges={eState}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={onNodeClick}
        fitView
        proOptions={proOptions}
      >
        <Background />
        <Controls />
        <MiniMap pannable zoomable />
        <FitView />
      </ReactFlow>
    </div>
  );
}

export default function GraphPage() {
  return (
    <Layout title="Graph View" description="Visual relationships between files and pages">
      <main style={{maxWidth: 980, margin: "0 auto", padding: "2rem 1rem"}}>
        <h1 style={{marginBottom: 12}}>Graph View</h1>
        <p style={{marginTop: 0, opacity: 0.8}}>
          Circles are nodes (files). Lines are relationships (imports/links). Click a node to open its doc.
        </p>
        <BrowserOnly>{() => <GraphInner />}</BrowserOnly>
      </main>
    </Layout>
  );
}
