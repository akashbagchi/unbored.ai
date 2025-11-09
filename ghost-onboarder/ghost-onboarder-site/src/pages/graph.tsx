// src/pages/graph.tsx
import React, { useEffect, useMemo, useState } from "react";
import BrowserOnly from "@docusaurus/BrowserOnly";
import Layout from "@theme/Layout";
import * as d3 from "d3-force";

/** --- Custom circle node (no inline text; shows label as tooltip) --- */
function CircleNode({ data }: { data: { label: string; hue: number; size: number } }) {
  return (
    <div
      title={data.label}
      style={{
        width: data.size,
        height: data.size,
        borderRadius: "50%",
        background: `hsl(${data.hue},70%,65%)`,
        border: "1px solid #444",
        boxShadow: "0 1px 2px rgba(0,0,0,0.15)",
      }}
    />
  );
}

/** --- Client-only graph (avoids SSR + hook-order issues) --- */
function GraphClient() {
  // Synchronous require: only runs inside BrowserOnly
  const { ReactFlow, Background, Controls, MiniMap } = require("reactflow");
  require("reactflow/dist/style.css");

  // Stable hooks
  const [graph, setGraph] = useState<{ nodes: any[]; edges: any[] }>({ nodes: [], edges: [] });
  const [hover, setHover] = useState<string | null>(null);

  useEffect(() => {
    fetch("/graph.json")
      .then((r) => r.json())
      .then(setGraph)
      .catch((e) => console.error("graph.json error:", e));
  }, []);

  /** ----- Force-directed layout with per-node radius + viewport mapping ----- */
  const layout = useMemo(() => {
    const nodesIn = graph.nodes ?? [];
    const edgesIn = graph.edges ?? [];
    if (!nodesIn.length) return { nodes: [], edges: [] };

    // Degree (for size/color)
    const degree = new Map<string, number>();
    edgesIn.forEach((e: any) => {
      degree.set(e.source, (degree.get(e.source) || 0) + 1);
      degree.set(e.target, (degree.get(e.target) || 0) + 1);
    });

    // Shallow copy + per-node collision radius
    const simNodes: any[] = nodesIn.map((n: any) => {
      const deg = degree.get(n.id) || 1;
      const size = Math.max(14, Math.min(30, 12 + deg * 2)); // clamp 14–30
      return { ...n, r: size / 2 + 6 }; // radius + padding for collide
    });

    // Seed starting positions so they don’t all begin at (0,0)
    simNodes.forEach((n, i) => {
      n.x = (Math.random() - 0.5) * 200;
      n.y = (Math.random() - 0.5) * 200;
    });

    const simLinks = edgesIn.map((e: any) => ({ source: e.source, target: e.target }));

    // Tuned forces for readable, non-overlapping layout
    const sim = d3
      .forceSimulation(simNodes)
      .force("link", d3.forceLink(simLinks).id((d: any) => d.id).distance(110).strength(0.9))
      .force("charge", d3.forceManyBody().strength(-320)) // more repulsion
      .force("collide", d3.forceCollide((d: any) => d.r).strength(1.0).iterations(2))
      .force("x", d3.forceX(0).strength(0.06))            // gentle centering
      .force("y", d3.forceY(0).strength(0.06))
      .stop();

    sim.tick(200);

    // Normalize to a fixed viewport so fitView behaves
    const xs = simNodes.map((n) => n.x ?? 0);
    const ys = simNodes.map((n) => n.y ?? 0);
    const minX = Math.min(...xs),
      maxX = Math.max(...xs),
      minY = Math.min(...ys),
      maxY = Math.max(...ys);

    const mapRange = (v: number, min: number, max: number, outMin: number, outMax: number) =>
      min === max ? (outMin + outMax) / 2 : outMin + ((v - min) * (outMax - outMin)) / (max - min);

    // Target box ~1200x800 centered around (0,0)
    const X_MIN = -600,
      X_MAX = 600,
      Y_MIN = -400,
      Y_MAX = 400;

    const nodes = simNodes.map((n: any) => {
      const deg = degree.get(n.id) || 1;
      const size = Math.max(14, Math.min(30, 12 + deg * 2));
      const hue = (deg * 40) % 360;

      return {
        id: n.id,
        type: "circleNode",
        position: {
          x: mapRange(n.x ?? 0, minX, maxX, X_MIN, X_MAX),
          y: mapRange(n.y ?? 0, minY, maxY, Y_MIN, Y_MAX),
        },
        data: { label: n.label, hue, size },
        draggable: true,
      };
    });

    const edges = edgesIn.map((e: any, i: number) => ({
      id: `${e.source}-${e.target}-${i}`,
      source: e.source,
      target: e.target,
      animated: true,
      style: { strokeWidth: 1, opacity: 0.7 },
    }));

    return { nodes, edges };
  }, [graph]);

  // Hover styling (computed outside JSX)
  const nodesDisplayed = useMemo(
    () =>
      layout.nodes.map((n: any) => ({
        ...n,
        style: {
          ...(n.style || {}),
          transform: hover === n.id ? "scale(1.2)" : "scale(1)",
          opacity: hover && hover !== n.id ? 0.45 : 1,
          transition: "transform 0.12s",
          cursor: "pointer",
        },
      })),
    [layout.nodes, hover]
  );

  const edgesDisplayed = useMemo(
    () =>
      layout.edges.map((e: any) => ({
        ...e,
        style: {
          ...e.style,
          stroke: hover && (e.source === hover || e.target === hover) ? "#111" : "#999",
          opacity: hover && !(e.source === hover || e.target === hover) ? 0.15 : 0.7,
        },
      })),
    [layout.edges, hover]
  );

  const nodeTypes = useMemo(() => ({ circleNode: CircleNode }), []);

  return (
    <div
      style={{ height: "85vh", background: "#fafafa", borderRadius: 12, overflow: "hidden" }}
      onMouseLeave={() => setHover(null)}
    >
      <ReactFlow
        nodes={nodesDisplayed}
        edges={edgesDisplayed}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        panOnScroll
        zoomOnScroll
        onNodeMouseEnter={(_, node) => setHover(node.id)}
        onNodeMouseLeave={() => setHover(null)}
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
    <Layout title="Graph View" description="Ghost Onboarder visual dependency map">
      <main style={{ maxWidth: 1100, margin: "0 auto", padding: "2rem 1rem" }}>
        <h1 style={{ marginBottom: 12 }}>Graph View</h1>
        <p style={{ marginTop: 0, opacity: 0.8 }}>
          Hover to highlight neighbors; click a node to open its doc. Labels appear as tooltips to
          keep the view clean.
        </p>
        <BrowserOnly>{() => <GraphClient />}</BrowserOnly>
      </main>
    </Layout>
  );
}
