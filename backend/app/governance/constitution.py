"""策略宪法:类型化准则 + guardrails 校验 + 确定性编译。

在现有 strategy_policy 体系之上新增一层"策略准则编译"能力:
    1. 把 YAML 策略政策中的散装阈值抽取为类型化 Criterion
    2. 对准则列表做 guardrails 校验(指标合法性、门槛能力、范围合理性)
    3. 把准则编译为可执行的分组配置(screen / rank / ic_hurdle / preference)
    4. 生成 ConstitutionVersion 供 API 和同步脚本使用

设计原则:
    - 纯函数,不依赖数据库或 FastAPI
    - 确定性:同样的策略政策输入永远产出同样的准则和编译结果
    - 宽进严出:能从策略中提取多少准则就提取多少,不合格的降级而非报错
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


# ============================================================
# 指标目录
# ============================================================
@dataclass
class MetricDef:
    """指标定义。"""
    metric_id: str           # 如 "pe", "pb", "roe", "match_pct", "val_pct"
    display_name: str        # 如 "市盈率"
    unit: str                # 如 "x", "%", ""
    typical_range: tuple[float, float]  # 如 (5, 100)
    lower_is_better: bool    # True = 越低越好(如 PE),False = 越高越好(如 ROE)
    hard_gate_capable: bool  # 是否可作为硬性门槛
    applies_to: str          # "fund" | "stock" | "both"


# 基金指标目录
# 覆盖项目中用到的所有基金指标:估值类、盈利成长类、收益风险类、匹配度类
METRIC_CATALOG: dict[str, MetricDef] = {
    # --- 估值类指标 ---
    "pe": MetricDef("pe", "加权PE", "x", (3, 100), True, True, "fund"),
    "pb": MetricDef("pb", "加权PB", "x", (0.5, 20), True, True, "fund"),
    "roe": MetricDef("roe", "加权ROE", "%", (0, 40), False, True, "fund"),
    "peg": MetricDef("peg", "PEG", "x", (0, 5), True, True, "fund"),
    "val_pct": MetricDef("val_pct", "估值分位", "%", (0, 100), True, True, "fund"),
    "dividend_yield": MetricDef("dividend_yield", "加权股息率", "%", (0, 10), False, True, "fund"),
    "market_cap": MetricDef("market_cap", "加权对数市值", "", (15, 25), False, False, "fund"),

    # --- 盈利成长类指标 ---
    "profit_growth": MetricDef("profit_growth", "加权利润增速", "%", (-20, 100), False, False, "fund"),
    "revenue_growth": MetricDef("revenue_growth", "加权营收增速", "%", (-20, 100), False, False, "fund"),

    # --- 收益风险类指标 ---
    "annualized_return": MetricDef("annualized_return", "年化收益", "%", (-30, 100), False, False, "fund"),
    "excess_return": MetricDef("excess_return", "超额收益", "%", (-20, 50), False, False, "fund"),
    "max_drawdown": MetricDef("max_drawdown", "最大回撤", "%", (-50, 0), True, False, "fund"),
    "sharpe": MetricDef("sharpe", "夏普比率", "", (-1, 5), False, False, "fund"),
    "volatility": MetricDef("volatility", "年化波动率", "%", (5, 50), True, False, "fund"),
    "information_ratio": MetricDef("information_ratio", "信息比率", "", (-1, 3), False, False, "fund"),
    "tracking_error": MetricDef("tracking_error", "跟踪误差", "%", (0, 30), True, False, "fund"),
    "alpha": MetricDef("alpha", "Alpha", "%", (-10, 30), False, False, "fund"),
    "beta": MetricDef("beta", "Beta", "", (0, 2), False, False, "fund"),

    # --- 持仓集中度类指标 ---
    "top10_weight": MetricDef("top10_weight", "前十大持仓权重", "%", (0, 100), True, False, "fund"),
    "industry_top1_weight": MetricDef("industry_top1_weight", "第一大行业权重", "%", (0, 100), True, False, "fund"),

    # --- 匹配度类指标 ---
    "match_pct": MetricDef("match_pct", "匹配度", "%", (0, 100), False, False, "fund"),
    "fit_score": MetricDef("fit_score", "拟合分数", "", (0, 100), False, False, "fund"),
    "evidence_score": MetricDef("evidence_score", "证据分数", "", (0, 100), False, False, "fund"),

    # --- 因子覆盖类指标 ---
    "factor_coverage": MetricDef("factor_coverage", "因子覆盖权重", "%", (0, 100), False, False, "fund"),

    # --- 风格权重类指标 ---
    "quality_growth_weight": MetricDef("quality_growth_weight", "质量成长权重", "%", (0, 100), False, False, "fund"),
    "deep_value_weight": MetricDef("deep_value_weight", "深度价值权重", "%", (0, 100), False, False, "fund"),
    "dividend_steady_weight": MetricDef("dividend_steady_weight", "红利稳健权重", "%", (0, 100), False, False, "fund"),

    # --- 基金经理类指标 ---
    "manager_tenure": MetricDef("manager_tenure", "基金经理任期", "年", (0, 20), False, False, "fund"),

    # --- 费率类指标 ---
    "fee_rate": MetricDef("fee_rate", "综合费率", "%", (0, 5), True, False, "fund"),

    # --- 基金规模类指标 ---
    "fund_size": MetricDef("fund_size", "基金规模", "亿", (0, 500), False, False, "fund"),
}


# ============================================================
# 类型化准则
# ============================================================
# 合法的准则类型
_VALID_KINDS = {"screen", "rank", "ic_hurdle", "preference"}

# 合法的运算符
_VALID_OPERATORS = {">", "<", ">=", "<="}


@dataclass
class Criterion:
    """策略准则。"""
    criterion_id: str            # 如 "screen.pe_max"
    kind: str                    # "screen" | "rank" | "ic_hurdle" | "preference"
    metric: str                  # 引用 METRIC_CATALOG
    operator: str                # ">" | "<" | ">=" | "<="
    value: float                 # 阈值
    weight: float = 1.0          # rank 准则的权重
    data_support_level: str = "fully"  # "fully" | "partial" | "proxy" | "unsupported"
    rule_rationale: str = ""     # 为什么需要这条规则
    rule_source: str = ""        # 来源

    def evaluate(self, observed: float | None) -> tuple[bool | None, str]:
        """
        评估准则。返回 (passed, reason)。

        - observed 为 None -> (None, "数据不足")
        - 通过 -> (True, "")
        - 不通过 -> (False, "指标值 {observed} {operator} {threshold} 未满足")
        """
        if observed is None:
            return (None, "数据不足")
        ops = {
            ">": lambda a, b: a > b,
            "<": lambda a, b: a < b,
            ">=": lambda a, b: a >= b,
            "<=": lambda a, b: a <= b,
        }
        fn = ops.get(self.operator)
        if not fn:
            return (None, f"不支持的运算符: {self.operator}")
        passed = fn(observed, self.value)
        if passed:
            return (True, "")
        return (False, f"{self.metric}={observed} 不满足 {self.operator} {self.value}")


# ============================================================
# Guardrails 校验
# ============================================================
@dataclass
class ValidationResult:
    """校验结果。"""
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    salvaged: list[dict] = field(default_factory=list)  # 降级的准则


def validate_criteria(criteria: list[Criterion]) -> ValidationResult:
    """
    校验准则列表。

    规则:
    1. criterion_id 必须命名空间化(含 ".")
    2. metric 必须在 METRIC_CATALOG 中
    3. screen/ic_hurdle 类型的 metric 必须 hard_gate_capable
    4. operator 必须合法
    5. value 必须在合理范围内(超出 typical_range 发 warning)
    6. screen 准则 >= 8 个 -> warning(过于狭窄)
    7. 不合格的 screen/ic_hurdle 降级为 preference
    """
    errors: list[str] = []
    warnings: list[str] = []
    salvaged: list[dict] = []

    # 用于标记需要降级的准则索引
    demoted_indices: set[int] = set()

    screen_count = 0

    for i, c in enumerate(criteria):
        # 规则 1: criterion_id 必须命名空间化(含 ".")
        if "." not in c.criterion_id:
            errors.append(f"准则 {c.criterion_id} 的 ID 必须命名空间化(含 '.')")

        # 规则 4: operator 必须合法
        if c.operator not in _VALID_OPERATORS:
            errors.append(
                f"准则 {c.criterion_id} 的运算符 {c.operator!r} 不合法,"
                f"合法值: {_VALID_OPERATORS}"
            )

        # 规则 2: metric 必须在 METRIC_CATALOG 中
        metric_def = METRIC_CATALOG.get(c.metric)
        if metric_def is None:
            errors.append(
                f"准则 {c.criterion_id} 的指标 {c.metric!r} 不在指标目录中"
            )
            continue

        # 检查 kind 是否合法
        if c.kind not in _VALID_KINDS:
            errors.append(
                f"准则 {c.criterion_id} 的类型 {c.kind!r} 不合法,"
                f"合法值: {_VALID_KINDS}"
            )
            continue

        # 统计 screen 数量
        if c.kind == "screen":
            screen_count += 1

        # 规则 3: screen/ic_hurdle 类型的 metric 必须 hard_gate_capable
        if c.kind in ("screen", "ic_hurdle") and not metric_def.hard_gate_capable:
            # 规则 7: 降级为 preference
            salvaged.append({
                "criterion_id": c.criterion_id,
                "original_kind": c.kind,
                "metric": c.metric,
                "reason": f"指标 {c.metric} 不支持硬性门槛(hard_gate_capable=False),降级为 preference",
            })
            demoted_indices.add(i)
            warnings.append(
                f"准则 {c.criterion_id} 的指标 {c.metric} 不支持硬性门槛,"
                f"已从 {c.kind} 降级为 preference"
            )

        # 规则 5: value 超出 typical_range 发 warning
        lo, hi = metric_def.typical_range
        if c.value < lo or c.value > hi:
            warnings.append(
                f"准则 {c.criterion_id} 的阈值 {c.value} 超出"
                f"指标 {c.metric} 的典型范围 ({lo}, {hi})"
            )

    # 规则 6: screen 准则 >= 8 个 -> warning(过于狭窄)
    if screen_count >= 8:
        warnings.append(
            f"screen 准则共 {screen_count} 个,>= 8 个可能导致筛选过于狭窄"
        )

    # 对降级的准则就地修改 kind
    for idx in demoted_indices:
        criteria[idx].kind = "preference"

    valid = len(errors) == 0
    return ValidationResult(
        valid=valid,
        errors=errors,
        warnings=warnings,
        salvaged=salvaged,
    )


# ============================================================
# 确定性编译
# ============================================================
def compile_criteria(criteria: list[Criterion]) -> dict[str, Any]:
    """
    将准则列表编译为可执行的配置。

    输出:
    {
        "screen_requirements": [Criterion...],  # screen 准则列表
        "ranking_blend": [{"metric": ..., "weight": ..., "invert": ...}],  # 排名混合
        "ic_hurdles": [Criterion...],  # IC 门槛
        "preferences": [Criterion...],  # 偏好(不执行)
    }
    """
    screen_requirements: list[Criterion] = []
    ranking_blend: list[dict[str, Any]] = []
    ic_hurdles: list[Criterion] = []
    preferences: list[Criterion] = []

    for c in criteria:
        if c.kind == "screen":
            screen_requirements.append(c)
        elif c.kind == "rank":
            metric_def = METRIC_CATALOG.get(c.metric)
            # lower_is_better 的指标在排名时需要反转
            invert = metric_def.lower_is_better if metric_def else False
            ranking_blend.append({
                "metric": c.metric,
                "weight": c.weight,
                "invert": invert,
            })
        elif c.kind == "ic_hurdle":
            ic_hurdles.append(c)
        elif c.kind == "preference":
            preferences.append(c)

    return {
        "screen_requirements": screen_requirements,
        "ranking_blend": ranking_blend,
        "ic_hurdles": ic_hurdles,
        "preferences": preferences,
    }


# ============================================================
# 从 YAML 策略生成准则
# ============================================================
def _get_float(d: dict[str, Any], *keys: str) -> float | None:
    """从字典中按多个候选键获取浮点值(兼容不同的字段命名)。"""
    for k in keys:
        v = d.get(k)
        if v is not None:
            try:
                return float(v)
            except (TypeError, ValueError):
                continue
    return None


def criteria_from_policy(policy: dict[str, Any]) -> list[Criterion]:
    """
    从现有的 strategy_policy YAML 字典生成准则列表。

    映射规则:
    - valuation_policy.max_pe / pe_max -> screen.pe_max (metric=pe, operator=<=, value=max_pe)
    - valuation_policy.max_pb / pb_max -> screen.pb_max
    - valuation_policy.max_peg / peg_max -> screen.peg_max
    - valuation_policy.max_valuation_percentile -> screen.val_pct_max
    - valuation_policy.min_dividend_yield -> screen.dividend_yield_min (如果有)
    - investment_policy.preferred_styles -> preference
    - candidate_priority.minimum_target_holding_weight -> screen.match_pct_min
    - candidate_priority.minimum_factor_coverage_weight -> screen.factor_coverage_min
    - monitoring_policy 中的阈值 -> ic_hurdle
    """
    criteria: list[Criterion] = []

    # --- 估值政策 -> screen 准则 ---
    vp = policy.get("valuation_policy") or {}

    max_pe = _get_float(vp, "max_pe", "pe_max")
    if max_pe is not None:
        criteria.append(Criterion(
            criterion_id="screen.pe_max",
            kind="screen",
            metric="pe",
            operator="<=",
            value=max_pe,
            rule_rationale="估值政策:加权PE上限",
            rule_source="valuation_policy",
        ))

    max_pb = _get_float(vp, "max_pb", "pb_max")
    if max_pb is not None:
        criteria.append(Criterion(
            criterion_id="screen.pb_max",
            kind="screen",
            metric="pb",
            operator="<=",
            value=max_pb,
            rule_rationale="估值政策:加权PB上限",
            rule_source="valuation_policy",
        ))

    max_peg = _get_float(vp, "max_peg", "peg_max")
    if max_peg is not None:
        criteria.append(Criterion(
            criterion_id="screen.peg_max",
            kind="screen",
            metric="peg",
            operator="<=",
            value=max_peg,
            rule_rationale="估值政策:PEG上限",
            rule_source="valuation_policy",
        ))

    max_val_pct = _get_float(vp, "max_valuation_percentile", "valuation_percentile_max")
    if max_val_pct is not None:
        criteria.append(Criterion(
            criterion_id="screen.val_pct_max",
            kind="screen",
            metric="val_pct",
            operator="<=",
            value=max_val_pct,
            rule_rationale="估值政策:估值分位上限",
            rule_source="valuation_policy",
        ))

    min_div_yield = _get_float(vp, "min_dividend_yield", "dividend_yield_min")
    if min_div_yield is not None:
        criteria.append(Criterion(
            criterion_id="screen.dividend_yield_min",
            kind="screen",
            metric="dividend_yield",
            operator=">=",
            value=min_div_yield,
            rule_rationale="估值政策:最低股息率要求",
            rule_source="valuation_policy",
        ))

    # --- 投资政策 -> preference 准则 ---
    ip = policy.get("investment_policy") or {}
    preferred_styles = ip.get("preferred_styles") or []
    for style in preferred_styles:
        if not isinstance(style, str):
            continue
        criteria.append(Criterion(
            criterion_id=f"preference.style_{style}",
            kind="preference",
            metric="match_pct",
            operator=">=",
            value=0.0,
            rule_rationale=f"投资政策:偏好风格 {style}",
            rule_source="investment_policy.preferred_styles",
        ))

    # --- 候选优先级 -> screen 准则 ---
    cp = policy.get("candidate_priority") or {}

    min_target_weight = _get_float(cp, "minimum_target_holding_weight")
    if min_target_weight is not None:
        criteria.append(Criterion(
            criterion_id="screen.match_pct_min",
            kind="screen",
            metric="match_pct",
            operator=">=",
            value=min_target_weight * 100,  # 转为百分比
            rule_rationale="候选优先级:最低目标持仓权重",
            rule_source="candidate_priority.minimum_target_holding_weight",
        ))

    min_factor_coverage = _get_float(cp, "minimum_factor_coverage_weight")
    if min_factor_coverage is not None:
        criteria.append(Criterion(
            criterion_id="screen.factor_coverage_min",
            kind="screen",
            metric="factor_coverage",
            operator=">=",
            value=min_factor_coverage * 100,  # 转为百分比
            rule_rationale="候选优先级:最低因子覆盖权重",
            rule_source="candidate_priority.minimum_factor_coverage_weight",
        ))

    min_disclosed_weight = _get_float(cp, "minimum_disclosed_holding_weight")
    if min_disclosed_weight is not None:
        criteria.append(Criterion(
            criterion_id="screen.top10_weight_min",
            kind="screen",
            metric="top10_weight",
            operator=">=",
            value=min_disclosed_weight * 100,  # 转为百分比
            rule_rationale="候选优先级:最低披露持仓权重",
            rule_source="candidate_priority.minimum_disclosed_holding_weight",
        ))

    # --- 监控政策 -> ic_hurdle 准则 ---
    mp = policy.get("monitoring_policy") or {}

    # 持仓变动阈值
    hc = mp.get("holding_change") or {}
    if isinstance(hc, dict):
        hc_threshold = _get_float(hc, "threshold", "single_position_drift")
        if hc_threshold is not None:
            # 漂移阈值是小数,转为百分比
            criteria.append(Criterion(
                criterion_id="ic_hurdle.holding_change",
                kind="ic_hurdle",
                metric="volatility",
                operator="<=",
                value=hc_threshold * 100 if hc_threshold <= 1 else hc_threshold,
                rule_rationale="监控政策:持仓变动阈值",
                rule_source="monitoring_policy.holding_change",
            ))

    # 行业偏离阈值
    idrift = mp.get("industry_drift") or {}
    if isinstance(idrift, dict):
        idrift_threshold = _get_float(idrift, "threshold", "vs_benchmark")
        if idrift_threshold is not None:
            criteria.append(Criterion(
                criterion_id="ic_hurdle.industry_drift",
                kind="ic_hurdle",
                metric="industry_top1_weight",
                operator="<=",
                value=idrift_threshold * 100 if idrift_threshold <= 1 else idrift_threshold,
                rule_rationale="监控政策:行业偏离阈值",
                rule_source="monitoring_policy.industry_drift",
            ))

    # 风格偏离阈值
    sdrift = mp.get("style_drift") or {}
    if isinstance(sdrift, dict):
        sdrift_threshold = _get_float(sdrift, "threshold", "vs_policy")
        if sdrift_threshold is not None:
            criteria.append(Criterion(
                criterion_id="ic_hurdle.style_drift",
                kind="ic_hurdle",
                metric="volatility",
                operator="<=",
                value=sdrift_threshold * 100 if sdrift_threshold <= 1 else sdrift_threshold,
                rule_rationale="监控政策:风格偏离阈值",
                rule_source="monitoring_policy.style_drift",
            ))

    # 风险阈值(最大回撤)
    rb = mp.get("risk_breach") or {}
    if isinstance(rb, dict):
        rb_threshold = _get_float(rb, "threshold", "drawdown")
        if rb_threshold is not None:
            # 回撤阈值是小数(负数),转为百分比
            drawdown_pct = rb_threshold * 100 if abs(rb_threshold) <= 1 else rb_threshold
            criteria.append(Criterion(
                criterion_id="ic_hurdle.risk_breach_drawdown",
                kind="ic_hurdle",
                metric="max_drawdown",
                operator=">=",
                value=drawdown_pct,
                rule_rationale="监控政策:最大回撤阈值",
                rule_source="monitoring_policy.risk_breach",
            ))

    # --- 排名准则(默认:按匹配度和夏普排名) ---
    # 只有当策略中存在 candidate_priority 配置时才添加排名准则
    if cp:
        criteria.append(Criterion(
            criterion_id="rank.match_pct",
            kind="rank",
            metric="match_pct",
            operator=">=",
            value=0.0,
            weight=0.6,
            rule_rationale="候选优先级:按匹配度排名",
            rule_source="candidate_priority",
        ))
        criteria.append(Criterion(
            criterion_id="rank.sharpe",
            kind="rank",
            metric="sharpe",
            operator=">=",
            value=0.0,
            weight=0.4,
            rule_rationale="候选优先级:按夏普比率排名",
            rule_source="candidate_priority",
        ))

    return criteria


# ============================================================
# Constitution 版本管理
# ============================================================
@dataclass
class ConstitutionVersion:
    """宪法版本。"""
    constitution_id: str        # 与 policy_id 对应
    version: int
    criteria: list[Criterion]
    compiled: dict[str, Any]   # compile_criteria 的输出
    validation: ValidationResult
    created_at: str
    status: str = "active"     # "active" | "superseded"

    def to_dict(self) -> dict[str, Any]:
        return {
            "constitution_id": self.constitution_id,
            "version": self.version,
            "criteria": [
                {
                    "criterion_id": c.criterion_id,
                    "kind": c.kind,
                    "metric": c.metric,
                    "operator": c.operator,
                    "value": c.value,
                    "weight": c.weight,
                    "data_support_level": c.data_support_level,
                    "rule_rationale": c.rule_rationale,
                }
                for c in self.criteria
            ],
            "compiled": {
                "screen_requirements": [
                    {
                        "criterion_id": c.criterion_id,
                        "metric": c.metric,
                        "operator": c.operator,
                        "value": c.value,
                    }
                    for c in self.compiled.get("screen_requirements", [])
                ],
                "ranking_blend": self.compiled.get("ranking_blend", []),
                "ic_hurdles": [
                    {
                        "criterion_id": c.criterion_id,
                        "metric": c.metric,
                        "operator": c.operator,
                        "value": c.value,
                    }
                    for c in self.compiled.get("ic_hurdles", [])
                ],
                "preferences": [
                    {
                        "criterion_id": c.criterion_id,
                        "metric": c.metric,
                        "rule_rationale": c.rule_rationale,
                    }
                    for c in self.compiled.get("preferences", [])
                ],
            },
            "validation": {
                "valid": self.validation.valid,
                "errors": self.validation.errors,
                "warnings": self.validation.warnings,
                "salvaged_count": len(self.validation.salvaged),
            },
            "created_at": self.created_at,
            "status": self.status,
        }


def create_constitution_from_policy(
    policy: dict[str, Any],
    policy_id: str,
    version: int,
) -> ConstitutionVersion:
    """
    从策略政策创建宪法版本。

    1. 调用 criteria_from_policy 生成准则
    2. 调用 validate_criteria 校验
    3. 调用 compile_criteria 编译
    4. 返回 ConstitutionVersion
    """
    criteria = criteria_from_policy(policy)
    validation = validate_criteria(criteria)
    compiled = compile_criteria(criteria)
    return ConstitutionVersion(
        constitution_id=policy_id,
        version=version,
        criteria=criteria,
        compiled=compiled,
        validation=validation,
        created_at=date.today().isoformat(),
    )
