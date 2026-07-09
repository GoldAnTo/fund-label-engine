"""API冒烟测试：验证认知引擎API端到端可用"""
from fastapi.testclient import TestClient
from app.main import create_app

app = create_app(
    source_db_path="/tmp/fle-run/source.sqlite",
    output_db_path="/tmp/fle-run/output.sqlite",
)
client = TestClient(app)

# 1. 测试 /v1/themes
print("=== /v1/themes ===")
resp = client.get("/v1/themes")
print(f"Status: {resp.status_code}")
themes = resp.json()["themes"]
for t in themes:
    print(f"  {t['key']}: {t['name']} - {t['belief']}")

# 2. 测试 /v1/cognition
print("\n=== /v1/cognition (AI) ===")
resp = client.post("/v1/cognition", json={"theme_key": "AI", "top_n": 3})
print(f"Status: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    theme = data.get("theme", {})
    print(f"Theme: {theme.get('name', '?')}")
    print(f"Belief: {theme.get('belief', '?')}")

    val = data.get("validation", {})
    print(f"\nValidation: {val.get('verdict', '?')}")
    for s in val.get("supporting_evidence", []):
        print(f"  + {s if isinstance(s, str) else s.get('message', s)}")
    for o in val.get("opposing_evidence", []):
        print(f"  - {o if isinstance(o, str) else o.get('message', o)}")

    matches = data.get("matches", [])
    print(f"\nMatches: {len(matches)} funds")
    for m in matches[:3]:
        v = m.get("valuation", {})
        t = m.get("trend", {})
        print(f"  {m['fund_code']} {m.get('fund_name','?')[:16]}  match={m['match_pct']}%  PE={v.get('weighted_pe')}  pct={v.get('weighted_val_pct')}%  trend={t.get('trend','?')}")

    portfolio = data.get("portfolio", {})
    selected = portfolio.get("selected_funds", [])
    defense = portfolio.get("defense_position")
    print(f"\nPortfolio: {len(selected)} selected, defense={'yes' if defense else 'no'}, cash={portfolio.get('cash_pct')}%")
    for s in selected:
        print(f"  {s['fund_code']} {s.get('fund_name','?')[:16]}  weight={s.get('weight')}%  match={s.get('match_pct')}%")
    if defense:
        print(f"  {defense['fund_code']} {defense.get('fund_name','?')[:16]}  weight={defense.get('weight')}%  (defense)")
    print(f"  Cash: {portfolio.get('cash_pct')}%")
else:
    print(f"Error: {resp.text[:500]}")
