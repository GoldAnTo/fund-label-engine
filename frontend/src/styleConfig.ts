/**
 * 风格标签统一配置
 *
 * 所有页面共享的风格标签定义：名称、颜色分类、分组。
 * 避免在多个页面重复定义。
 */

// 风格标签中文名
export const STYLE_NAMES: Record<string, string> = {
  // 价值
  deep_value: "深度价值",
  low_valuation: "低估值",
  high_valuation: "高估值",
  // 成长
  quality_growth: "质量成长",
  high_roe: "高盈利",
  profit_growth_strong: "利润高增长",
  // 红利
  dividend_steady: "红利稳健",
  high_dividend_financial: "金融高股息",
  consumer_quality: "消费质量",
  // 规模
  large_cap: "大盘",
  mid_cap: "中盘",
  small_cap: "小盘",
  // 主题
  tech_focused: "科技主题",
  finance_focused: "金融主题",
  consumer_focused: "消费主题",
  healthcare_focused: "医药主题",
  cyclical_focused: "周期主题",
  // 观察类
  style_pending_rule_definition: "风格未定",
  style_balanced: "风格均衡",
  style_stable: "风格稳定",
  style_drift: "风格漂移",
  // 组合风格
  value_dividend: "价值红利",
  growth_large_cap: "大盘成长",
  growth_small_cap: "小盘成长",
  small_cap_growth: "小盘高成长",
  quality_dividend: "高质量红利",
  value_quality: "价值质量",
  growth_profit: "成长盈利",
};

// 风格标签颜色分类
export type StyleColor = "value" | "growth" | "dividend" | "size" | "theme" | "composite";

export const STYLE_COLORS: Record<string, StyleColor> = {
  // 价值 = 绿色系
  deep_value: "value",
  low_valuation: "value",
  high_valuation: "value",
  // 成长 = 蓝色系
  quality_growth: "growth",
  high_roe: "growth",
  profit_growth_strong: "growth",
  // 红利 = 橙色系
  dividend_steady: "dividend",
  high_dividend_financial: "dividend",
  consumer_quality: "dividend",
  // 规模 = 灰色系
  large_cap: "size",
  mid_cap: "size",
  small_cap: "size",
  // 主题 = 紫色系
  tech_focused: "theme",
  finance_focused: "theme",
  consumer_focused: "theme",
  healthcare_focused: "theme",
  cyclical_focused: "theme",
  // 组合 = 青色系
  value_dividend: "composite",
  growth_large_cap: "composite",
  growth_small_cap: "composite",
  small_cap_growth: "composite",
  quality_dividend: "composite",
  value_quality: "composite",
  growth_profit: "composite",
};

// 风格分组（用于快捷筛选和分布展示）
export const STYLE_GROUPS: { title: string; color: StyleColor; codes: string[] }[] = [
  { title: "价值", color: "value", codes: ["deep_value", "low_valuation", "high_valuation"] },
  { title: "成长", color: "growth", codes: ["quality_growth", "high_roe", "profit_growth_strong"] },
  { title: "红利", color: "dividend", codes: ["dividend_steady", "high_dividend_financial", "consumer_quality"] },
  { title: "规模", color: "size", codes: ["large_cap", "mid_cap", "small_cap"] },
  { title: "主题", color: "theme", codes: ["tech_focused", "finance_focused", "consumer_focused", "healthcare_focused", "cyclical_focused"] },
  { title: "组合", color: "composite", codes: ["value_dividend", "growth_large_cap", "growth_small_cap", "small_cap_growth", "quality_dividend", "value_quality", "growth_profit"] },
];

// 所有风格标签代码集合
export const ALL_STYLE_CODES = new Set(Object.keys(STYLE_NAMES));

// 获取风格标签的 CSS class
export function styleTagClass(code: string): string {
  const color = STYLE_COLORS[code];
  return color ? `style-tag style-${color}` : "style-tag";
}

// 获取风格标签的中文名
export function styleName(code: string): string {
  return STYLE_NAMES[code] ?? code;
}
