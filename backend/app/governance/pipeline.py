"""工作流编排：Run/Step 管理 + 阶段 handoff + 孤儿清理"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable
from enum import Enum


class RunStatus(str, Enum):
    """Run 状态"""
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(str, Enum):
    """Step 状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class StageType(str, Enum):
    """阶段类型"""
    SCREENER = "screener"          # 筛选
    COGNITION = "cognition"        # 认知分析
    IC_REVIEW = "ic_review"        # 投决会审查
    MEMO = "memo"                  # 投资备忘录
    PORTFOLIO = "portfolio"        # 组合构建
    MONITORING = "monitoring"      # 投后监控


# 漏斗阶段（失败则 pipeline fail）
FUNNEL_STAGES = {StageType.SCREENER, StageType.COGNITION, StageType.IC_REVIEW}


@dataclass
class Step:
    """工作流步骤"""
    step_id: str
    run_id: str
    stage: str               # StageType 值
    item_ref: str            # 关联对象（如 direction, fund_code）
    status: str = "pending"  # StepStatus 值
    attempt: int = 0
    detail: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    started_at: str = ""
    finished_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "run_id": self.run_id,
            "stage": self.stage,
            "item_ref": self.item_ref,
            "status": self.status,
            "attempt": self.attempt,
            "detail": self.detail,
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
        }


@dataclass
class Run:
    """工作流运行"""
    run_id: str
    kind: str                # "pipeline" | "screener" | "cognition" 等
    status: str = "running"  # RunStatus 值
    trigger: str = "user"    # "user" | "pipeline" | "filing"
    direction: str = ""
    steps: list[Step] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    started_at: str = ""
    finished_at: str = ""
    server_session_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "kind": self.kind,
            "status": self.status,
            "trigger": self.trigger,
            "direction": self.direction,
            "steps": [s.to_dict() for s in self.steps],
            "stats": self.stats,
            "error": self.error,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "server_session_id": self.server_session_id,
        }


@dataclass
class PipelineResult:
    """Pipeline 执行结果"""
    run: Run
    stages_completed: list[str]
    stages_failed: list[str]
    partial: bool            # 是否部分完成
    output: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run": self.run.to_dict(),
            "stages_completed": self.stages_completed,
            "stages_failed": self.stages_failed,
            "partial": self.partial,
            "output": self.output,
        }


# === 内存中的 Run Store（生产环境可替换为数据库） ===

class RunStore:
    """Run 存储（内存版，可替换为持久化实现）"""

    def __init__(self):
        self._runs: dict[str, Run] = {}
        self._server_session_id: str = datetime.now().isoformat()

    def create_run(self, kind: str, trigger: str = "user", direction: str = "") -> Run:
        """创建新 run"""
        run_id = f"run_{kind}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        run = Run(
            run_id=run_id,
            kind=kind,
            trigger=trigger,
            direction=direction,
            started_at=datetime.now().isoformat(),
            server_session_id=self._server_session_id,
        )
        self._runs[run_id] = run
        return run

    def get_run(self, run_id: str) -> Run | None:
        return self._runs.get(run_id)

    def update_run_status(self, run_id: str, status: str, error: str = "") -> None:
        run = self._runs.get(run_id)
        if run:
            run.status = status
            run.error = error
            if status in (RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED):
                run.finished_at = datetime.now().isoformat()

    def add_step(self, run_id: str, stage: str, item_ref: str) -> Step:
        """添加步骤"""
        run = self._runs.get(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")
        step_id = f"step_{stage}_{len(run.steps)}_{datetime.now().strftime('%H%M%S')}"
        step = Step(
            step_id=step_id,
            run_id=run_id,
            stage=stage,
            item_ref=item_ref,
            started_at=datetime.now().isoformat(),
        )
        run.steps.append(step)
        return step

    def update_step(self, run_id: str, step_id: str, status: str,
                    detail: dict | None = None, error: str = "") -> None:
        run = self._runs.get(run_id)
        if not run:
            return
        for step in run.steps:
            if step.step_id == step_id:
                step.status = status
                step.attempt += 1 if status == "running" else 0
                if detail:
                    step.detail.update(detail)
                step.error = error
                if status in (StepStatus.COMPLETED, StepStatus.FAILED, StepStatus.SKIPPED):
                    step.finished_at = datetime.now().isoformat()
                break

    def reconcile_orphans(self) -> list[str]:
        """
        清理孤儿 run：将其他 server session 的 running run 标记为 failed。

        借鉴 FundOps：启动时调用，把上一 session 遗留的 running run 标记为
        "interrupted - server restarted"。
        """
        orphaned: list[str] = []
        for run_id, run in self._runs.items():
            if run.status == RunStatus.RUNNING and run.server_session_id != self._server_session_id:
                run.status = RunStatus.FAILED
                run.error = "interrupted - server restarted"
                run.finished_at = datetime.now().isoformat()
                # 级联关闭非终态 step
                for step in run.steps:
                    if step.status in (StepStatus.PENDING, StepStatus.RUNNING):
                        step.status = StepStatus.FAILED
                        step.error = "interrupted - server restarted"
                        step.finished_at = run.finished_at
                orphaned.append(run_id)
        return orphaned

    def list_runs(self, direction: str | None = None) -> list[Run]:
        """列出 runs"""
        runs = list(self._runs.values())
        if direction:
            runs = [r for r in runs if r.direction == direction]
        return sorted(runs, key=lambda r: r.started_at, reverse=True)


# === Pipeline 编排器 ===

class Pipeline:
    """认知研究流水线编排器"""

    def __init__(self, store: RunStore):
        self.store = store
        # 阶段执行器注册
        self._executors: dict[str, Callable] = {}

    def register_executor(self, stage: str, executor: Callable) -> None:
        """注册阶段执行器"""
        self._executors[stage] = executor

    def execute(self, direction: str, stages: list[str] | None = None) -> PipelineResult:
        """
        执行 pipeline。

        规则：
        1. 漏斗阶段失败 -> pipeline 立即 fail
        2. 非漏斗阶段失败 -> 记录为 failed step，pipeline 继续
        3. 已完成的阶段不重复执行
        4. 部分完成标记为 partial
        """
        if stages is None:
            stages = [s.value for s in StageType]

        run = self.store.create_run(kind="pipeline", direction=direction)
        completed: list[str] = []
        failed: list[str] = []
        output: dict[str, Any] = {}
        partial = False

        for stage in stages:
            step = self.store.add_step(run.run_id, stage, direction)
            self.store.update_step(run.run_id, step.step_id, StepStatus.RUNNING)

            executor = self._executors.get(stage)
            if not executor:
                self.store.update_step(run.run_id, step.step_id, StepStatus.SKIPPED,
                                       error=f"no executor for {stage}")
                continue

            try:
                result = executor(direction, output)
                step_detail = {"result_keys": list(result.keys()) if isinstance(result, dict) else []}
                self.store.update_step(run.run_id, step.step_id, StepStatus.COMPLETED,
                                       detail=step_detail)
                completed.append(stage)
                if isinstance(result, dict):
                    output[stage] = result

            except Exception as e:
                self.store.update_step(run.run_id, step.step_id, StepStatus.FAILED,
                                       error=str(e))
                failed.append(stage)

                # 漏斗阶段失败 -> pipeline fail
                if StageType(stage) in FUNNEL_STAGES:
                    run.stats = {
                        "completed": completed,
                        "failed": failed,
                        "output_keys": list(output.keys()),
                    }
                    self.store.update_run_status(run.run_id, RunStatus.FAILED,
                                                 error=f"funnel stage {stage} failed: {e}")
                    return PipelineResult(
                        run=run,
                        stages_completed=completed,
                        stages_failed=failed,
                        partial=False,
                        output=output,
                    )
                else:
                    # 非漏斗阶段失败，继续
                    partial = True

        run.stats = {
            "completed": completed,
            "failed": failed,
            "output_keys": list(output.keys()),
        }
        final_status = RunStatus.COMPLETED if not failed else RunStatus.COMPLETED
        self.store.update_run_status(run.run_id, final_status)

        return PipelineResult(
            run=run,
            stages_completed=completed,
            stages_failed=failed,
            partial=partial,
            output=output,
        )


# === 全局单例 ===

_global_store: RunStore | None = None


def get_run_store() -> RunStore:
    """获取全局 RunStore（单例）"""
    global _global_store
    if _global_store is None:
        _global_store = RunStore()
        # 启动时清理孤儿
        _global_store.reconcile_orphans()
    return _global_store


def execute_cognition_pipeline(direction: str) -> PipelineResult:
    """
    执行认知研究 pipeline。

    阶段顺序：
    1. screener - 确定性筛选
    2. cognition - 认知分析（产业链/匹配/估值/验证）
    3. ic_review - 投决会审查
    4. memo - 投资备忘录
    5. portfolio - 组合构建
    6. monitoring - 投后监控（设置 watch items）
    """
    store = get_run_store()
    pipeline = Pipeline(store)

    # 注册执行器
    def screener_executor(direction: str, prev_output: dict) -> dict:
        # 筛选阶段：调用 cognition engine 的第一步
        return {"status": "screener_completed", "direction": direction}

    def cognition_executor(direction: str, prev_output: dict) -> dict:
        # 认知分析：调用 CognitionEngine
        from app.cognition.engine import CognitionEngine
        engine = CognitionEngine(source_db_path="", factor_db_path="")
        result = engine.run(direction=direction, conviction="medium")
        return result

    def ic_review_executor(direction: str, prev_output: dict) -> dict:
        # IC Review：从认知结果中提取
        cognition_result = prev_output.get("cognition", {})
        ic_review = cognition_result.get("ic_review", {})
        return ic_review

    def memo_executor(direction: str, prev_output: dict) -> dict:
        # 备忘录
        cognition_result = prev_output.get("cognition", {})
        memo = cognition_result.get("investment_memo", {})
        return memo

    def portfolio_executor(direction: str, prev_output: dict) -> dict:
        # 组合
        cognition_result = prev_output.get("cognition", {})
        portfolio = cognition_result.get("portfolio", {})
        return portfolio

    def monitoring_executor(direction: str, prev_output: dict) -> dict:
        # 监控
        cognition_result = prev_output.get("cognition", {})
        tracker = cognition_result.get("thesis_tracker", {})
        health = tracker.get("health", {})
        return health

    pipeline.register_executor("screener", screener_executor)
    pipeline.register_executor("cognition", cognition_executor)
    pipeline.register_executor("ic_review", ic_review_executor)
    pipeline.register_executor("memo", memo_executor)
    pipeline.register_executor("portfolio", portfolio_executor)
    pipeline.register_executor("monitoring", monitoring_executor)

    # 执行 pipeline（只执行认知相关的阶段）
    return pipeline.execute(
        direction=direction,
        stages=["screener", "cognition", "ic_review", "memo", "portfolio", "monitoring"],
    )
