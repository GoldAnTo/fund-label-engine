import { useState, useCallback } from "react";
import {
  ReactFlow,
  Controls,
  MiniMap,
  Background,
  addEdge,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type Connection,
  type NodeProps,
  Handle,
  Position,
  BackgroundVariant,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Card, CardHeader, CardBody, Badge, Loading, ErrorBox, ProgressBar, Table, Th, Td } from "../components/ui";
import { DonutChart } from "../charts";

// API types
interface MultiCognitionItem {
  direction: string;
  conviction: string;
  weight_pct: number;
}
interface MultiCognitionResponse {
  cognition_count: number;
  cognitions: Array<{
    direction: string;
    weight_pct: number;
    conviction: string;
    result: Record<string, unknown>;
  }>;
  combined_portfolio: {
    suggested_weight?: number;
    defense_weight?: number;
    cash_pct?: number;
    total_invested?: number;
    rationale?: string;
    top_funds?: Array<{ fund_code: string; fund_name: string; match_pct: number }>;
    [key: string]: unknown;
  };
}

const CONVICTION_LABEL: Record<string, string> = { high: "高", medium: "中", low: "低" };

// Custom cognition node data shape
interface CognitionNodeData extends Record<string, unknown> {
  direction: string;
  conviction: string;
  weight_pct: number;
  onDelete: (nodeId: string) => void;
  onChange: (nodeId: string, key: string, value: string | number) => void;
}

type CognitionNodeType = Node<CognitionNodeData, "cognition">;

let nodeIdCounter = 1;

// Custom cognition node
function CognitionNode({ id, data }: NodeProps<CognitionNodeType>) {
  const updateData = (key: string, value: string | number) => {
    data.onChange(id, key, value);
  };

  return (
    <div className="bg-surface border border-border rounded-lg p-4 min-w-[240px] shadow-lg">
      <Handle type="target" position={Position.Top} style={{ background: "var(--accent)" }} />
      <div className="flex items-center justify-between mb-3">
        <span className="text-xs uppercase tracking-wide text-text-3 font-semibold">认知方向</span>
        <button
          type="button"
          onClick={() => data.onDelete(id)}
          className="text-xs text-neg hover:text-neg-text"
        >
          删除
        </button>
      </div>
      <input
        type="text"
        defaultValue={data.direction || ""}
        onChange={(e) => updateData("direction", e.target.value)}
        placeholder="如：AI、创新药..."
        className="w-full px-2 py-1.5 text-sm bg-surface-2 border border-border rounded mb-2 focus:outline-none focus:border-accent"
      />
      <div className="flex gap-1 mb-2">
        {(["low", "medium", "high"] as const).map((c) => (
          <button
            key={c}
            type="button"
            onClick={() => updateData("conviction", c)}
            className={`px-2 py-0.5 rounded text-xs border ${
              (data.conviction || "medium") === c
                ? "border-accent bg-accent-soft text-accent"
                : "border-border bg-surface text-text-2"
            }`}
          >
            {CONVICTION_LABEL[c]}
          </button>
        ))}
      </div>
      <div className="flex items-center gap-2">
        <span className="text-xs text-text-3">权重</span>
        <input
          type="range"
          min={0}
          max={50}
          defaultValue={data.weight_pct || 20}
          onChange={(e) => updateData("weight_pct", Number(e.target.value))}
          className="flex-1"
        />
        <span className="text-xs font-mono font-semibold text-accent w-8 text-right">
          {data.weight_pct || 20}%
        </span>
      </div>
      <Handle type="source" position={Position.Bottom} style={{ background: "var(--accent)" }} />
    </div>
  );
}

const nodeTypes = { cognition: CognitionNode };

export default function MultiCognitionPage() {
  const [nodes, setNodes, onNodesChange] = useNodesState<CognitionNodeType>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<MultiCognitionResponse | null>(null);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  const handleDeleteNode = useCallback(
    (nodeId: string) => {
      setNodes((nds) => nds.filter((n) => n.id !== nodeId));
    },
    [setNodes]
  );

  const handleNodeChange = useCallback(
    (nodeId: string, key: string, value: string | number) => {
      setNodes((nds) =>
        nds.map((n) =>
          n.id === nodeId ? { ...n, data: { ...n.data, [key]: value } } : n
        )
      );
    },
    [setNodes]
  );

  const addCognitionNode = () => {
    const id = `cognition-${nodeIdCounter++}`;
    const newNode: CognitionNodeType = {
      id,
      type: "cognition",
      position: {
        x: 100 + (nodes.length % 3) * 280,
        y: 80 + Math.floor(nodes.length / 3) * 200,
      },
      data: {
        direction: "",
        conviction: "medium",
        weight_pct: 20,
        onDelete: handleDeleteNode,
        onChange: handleNodeChange,
      },
    };
    setNodes((nds) => [...nds, newNode]);
  };

  const runMultiCognition = async () => {
    const items: MultiCognitionItem[] = nodes
      .map((n) => ({
        direction: n.data.direction || "",
        conviction: n.data.conviction || "medium",
        weight_pct: n.data.weight_pct || 20,
      }))
      .filter((item) => item.direction.trim());

    if (items.length < 2) {
      setError("至少需要 2 个认知方向才能构建多认知组合");
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const BASE = import.meta.env.VITE_API_BASE ?? "";
      const res = await fetch(`${BASE}/v1/cognition/multi`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          items,
          risk_tolerance: "moderate",
          time_horizon: "long",
          top_n: 5,
        }),
      });
      if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
      const data = await res.json();
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  const totalWeight = nodes.reduce(
    (sum, n) => sum + (n.data.weight_pct || 0),
    0
  );

  return (
    <div className="main">
      <div className="mb-6">
        <h2 className="text-2xl font-bold tracking-tight mb-2">多认知组合构建器</h2>
        <p className="text-text-3 text-sm leading-relaxed">
          组合是多个认知的分层表达。添加认知方向节点，分配权重，系统将合并为统一组合方案。
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left: Node Palette */}
        <div className="lg:col-span-2 space-y-3">
          <Card>
            <CardHeader title="认知节点" />
            <CardBody>
              <button
                type="button"
                onClick={addCognitionNode}
                className="w-full px-3 py-2 text-sm bg-accent text-white border border-accent rounded-lg hover:opacity-90 mb-3"
              >
                + 添加认知
              </button>
              <div className="text-xs text-text-3 space-y-1">
                <div>当前节点：{nodes.length}</div>
                <div>总权重：{totalWeight}%</div>
                {totalWeight !== 100 && totalWeight > 0 && (
                  <div className="text-warn">建议总权重 = 100%</div>
                )}
              </div>
            </CardBody>
          </Card>
        </div>

        {/* Middle: React Flow Canvas */}
        <div className="lg:col-span-7">
          <Card>
            <CardBody className="p-0">
              <div style={{ height: "500px" }}>
                <ReactFlow
                  nodes={nodes}
                  edges={edges}
                  onNodesChange={onNodesChange}
                  onEdgesChange={onEdgesChange}
                  onConnect={onConnect}
                  nodeTypes={nodeTypes}
                  fitView
                  defaultEdgeOptions={{ style: { stroke: "var(--accent)", strokeWidth: 2 } }}
                >
                  <Controls />
                  <MiniMap
                    nodeColor={() => "var(--accent)"}
                    maskColor="rgba(0,0,0,0.1)"
                  />
                  <Background variant={BackgroundVariant.Dots} gap={16} size={1} color="var(--border)" />
                </ReactFlow>
              </div>
            </CardBody>
          </Card>

          {error && <ErrorBox message={error} />}
          {loading && <Loading text="正在分析多个认知方向并合并组合…" />}
          <div className="mt-4 flex justify-end">
            <button
              type="button"
              disabled={nodes.length < 2 || loading}
              onClick={runMultiCognition}
              className="px-6 py-3 text-sm font-semibold bg-accent text-white border border-accent rounded-lg hover:opacity-90 disabled:opacity-50"
            >
              {loading ? "分析中…" : "运行多认知分析"}
            </button>
          </div>
        </div>

        {/* Right: Result Panel */}
        <div className="lg:col-span-3 space-y-4">
          {result ? (
            <MultiCognitionResult result={result} />
          ) : (
            <div className="p-6 bg-surface border border-border border-dashed rounded-lg text-center text-text-3 text-sm">
              添加 2+ 认知节点并运行分析后，组合结果将显示在此处
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function MultiCognitionResult({ result }: { result: MultiCognitionResponse }) {
  const cp = result.combined_portfolio;
  const topFunds = (cp.top_funds ?? []) as Array<{ fund_code: string; fund_name: string; match_pct: number }>;
  const donutData = [
    { name: "认知仓位", value: cp.suggested_weight || 0, color: "#3b82f6" },
    { name: "防守仓位", value: cp.defense_weight || 0, color: "#10b981" },
    { name: "现金", value: cp.cash_pct || 0, color: "#e5e7eb" },
  ].filter((d) => d.value > 0);

  return (
    <>
      <Card>
        <CardHeader title="组合概览" subtitle={`${result.cognition_count} 个认知方向合并`} />
        <CardBody>
          {donutData.length > 0 && (
            <div className="mb-4">
              <DonutChart
                data={donutData}
                size={160}
                innerRadius={42}
                outerRadius={65}
                centerLabel="总投资"
                centerValue={`${(cp.total_invested || 0).toFixed(0)}%`}
              />
            </div>
          )}
          <div className="space-y-2">
            <ProgressBar value={cp.suggested_weight || 0} variant="accent" label="认知仓位" />
            <ProgressBar value={cp.defense_weight || 0} variant="pos" label="防守仓位" />
            <ProgressBar value={cp.cash_pct || 0} variant="neutral" label="现金" />
          </div>
          {cp.rationale && (
            <p className="text-xs text-text-3 mt-3 leading-relaxed">{cp.rationale}</p>
          )}
        </CardBody>
      </Card>

      {topFunds.length > 0 && (
        <Card>
          <CardHeader title="基金明细" />
          <CardBody className="p-0">
            <Table>
              <thead>
                <tr>
                  <Th>代码</Th>
                  <Th>名称</Th>
                  <Th className="text-right">匹配度</Th>
                </tr>
              </thead>
              <tbody>
                {topFunds.map((f, i) => (
                  <tr key={i}>
                    <Td className="font-mono text-xs">{f.fund_code}</Td>
                    <Td>{f.fund_name}</Td>
                    <Td className="text-right font-semibold text-accent">
                      {f.match_pct?.toFixed(1) ?? "-"}%
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </CardBody>
        </Card>
      )}

      <Card>
        <CardHeader title="认知来源" />
        <CardBody>
          <div className="space-y-2">
            {result.cognitions.map((c, i) => (
              <div key={i} className="flex items-center justify-between text-xs">
                <span className="font-semibold">{c.direction}</span>
                <div className="flex items-center gap-2">
                  <Badge variant="accent">{CONVICTION_LABEL[c.conviction] ?? "中"}</Badge>
                  <span className="font-mono text-accent">{c.weight_pct}%</span>
                </div>
              </div>
            ))}
          </div>
        </CardBody>
      </Card>
    </>
  );
}
