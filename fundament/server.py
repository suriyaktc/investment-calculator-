#!/usr/bin/env python3
"""
Fundament — Investor Education Backend
Zero-dependency Python server (stdlib only)
Runs on Windows, macOS, Linux with Python 3.6+
"""

import json
import math
import os
import sys
import webbrowser
import threading
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

# ─────────────────────────────────────────
# CALCULATION ENGINE
# ─────────────────────────────────────────

def calc_sip(monthly, rate, years, inflation, stepup):
    """
    SIP calculator with optional step-up.
    Returns yearly snapshots and summary stats.
    """
    mr = rate / 100 / 12
    current_monthly = monthly
    corpus = 0.0
    total_invested = 0.0
    yearly = []

    for y in range(1, int(years) + 1):
        for _ in range(12):
            corpus = (corpus + current_monthly) * (1 + mr)
            total_invested += current_monthly
        if stepup > 0:
            current_monthly *= (1 + stepup / 100)
        real_val = corpus / ((1 + inflation / 100) ** y)
        yearly.append({
            "year": y,
            "invested": round(total_invested, 2),
            "value": round(corpus, 2),
            "gains": round(corpus - total_invested, 2),
            "real": round(real_val, 2),
        })

    gains = corpus - total_invested
    real_final = corpus / ((1 + inflation / 100) ** years)
    gain_pct = (gains / total_invested * 100) if total_invested else 0

    return {
        "corpus": round(corpus, 2),
        "total_invested": round(total_invested, 2),
        "gains": round(gains, 2),
        "gain_pct": round(gain_pct, 2),
        "real_value": round(real_final, 2),
        "multiplier": round(corpus / total_invested, 2) if total_invested else 0,
        "yearly": yearly,
    }


def calc_lumpsum(principal, rate, years, inflation, freq):
    """
    Lump sum with compound vs simple interest comparison.
    freq = compounding frequency per year (1, 2, 4, 12)
    """
    n = freq
    compound = principal * ((1 + rate / 100 / n) ** (n * years))
    simple = principal * (1 + rate / 100 * years)
    real_val = compound / ((1 + inflation / 100) ** years)
    bonus = compound - simple
    rule72_years = 72 / rate if rate else 0
    doubles = years / rule72_years if rule72_years else 0

    yearly = []
    for y in range(1, int(years) + 1):
        c = principal * ((1 + rate / 100 / n) ** (n * y))
        s = principal * (1 + rate / 100 * y)
        r = c / ((1 + inflation / 100) ** y)
        yearly.append({
            "year": y,
            "compound": round(c, 2),
            "simple": round(s, 2),
            "real": round(r, 2),
        })

    return {
        "corpus": round(compound, 2),
        "simple": round(simple, 2),
        "bonus": round(bonus, 2),
        "real_value": round(real_val, 2),
        "multiplier": round(compound / principal, 2) if principal else 0,
        "rule72_years": round(rule72_years, 1),
        "doubles": round(doubles, 2),
        "yearly": yearly,
    }


def calc_goal(target, years, rate, inflation, existing=0):
    """
    Reverse calculator: what SIP/lump sum to reach a goal?
    """
    # Inflation-adjusted target
    real_target = target * ((1 + inflation / 100) ** years)
    target_after_existing = real_target - existing * ((1 + rate / 100) ** years)
    target_after_existing = max(target_after_existing, 0)

    mr = rate / 100 / 12
    months = years * 12

    # Required SIP formula: FV = P * [((1+r)^n - 1) / r] * (1+r)
    if mr > 0:
        sip_needed = target_after_existing / (
            (((1 + mr) ** months - 1) / mr) * (1 + mr)
        )
    else:
        sip_needed = target_after_existing / months

    # Required lump sum
    if rate > 0:
        lump_needed = target_after_existing / ((1 + rate / 100) ** years)
    else:
        lump_needed = target_after_existing

    return {
        "target": round(target, 2),
        "inflation_adjusted_target": round(real_target, 2),
        "sip_needed": round(max(sip_needed, 0), 2),
        "lumpsum_needed": round(max(lump_needed, 0), 2),
        "years": years,
        "rate": rate,
    }


def calc_xirr_approx(cashflows):
    """
    Approximate XIRR using bisection method.
    cashflows: list of {amount, days} where amount is negative for outflow.
    """
    def npv(rate, cfs):
        return sum(
            cf["amount"] / ((1 + rate) ** (cf["days"] / 365.0))
            for cf in cfs
        )

    lo, hi = -0.9, 10.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if npv(mid, cashflows) > 0:
            lo = mid
        else:
            hi = mid
        if abs(hi - lo) < 1e-8:
            break
    return round(mid * 100, 4)


FUND_DATA = {
    "largecap": {
        "name": "Large Cap Equity", "color": "#e8a020", "type": "Equity — Domestic",
        "risk": "Moderate-High", "risk_score": 6, "return_range": "10–14%",
        "return_score": 7, "liquidity": "T+3 days", "liq_score": 7,
        "horizon": "5+ years", "min_invest": "₹500", "exp_ratio": "0.5–1.5%",
        "lock_in": "None", "ltcg": "12.5% >₹1.25L", "stcg": "20%",
        "description": "Invests in top 100 companies by market cap. More stable than mid/small cap but lower upside.",
        "ideal": "Conservative to moderate investors wanting equity exposure",
    },
    "midcap": {
        "name": "Mid Cap Equity", "color": "#1a8080", "type": "Equity — Domestic",
        "risk": "High", "risk_score": 8, "return_range": "12–18%",
        "return_score": 8, "liquidity": "T+3 days", "liq_score": 7,
        "horizon": "7+ years", "min_invest": "₹500", "exp_ratio": "0.6–1.8%",
        "lock_in": "None", "ltcg": "12.5% >₹1.25L", "stcg": "20%",
        "description": "Companies ranked 101–250 by market cap. Higher growth potential with more volatility.",
        "ideal": "Investors with higher risk tolerance and long horizons",
    },
    "smallcap": {
        "name": "Small Cap Equity", "color": "#c04830", "type": "Equity — Domestic",
        "risk": "Very High", "risk_score": 10, "return_range": "14–22%*",
        "return_score": 9, "liquidity": "T+3 days", "liq_score": 5,
        "horizon": "10+ years", "min_invest": "₹500", "exp_ratio": "0.8–2.0%",
        "lock_in": "None", "ltcg": "12.5% >₹1.25L", "stcg": "20%",
        "description": "Companies outside top 250. Highest potential returns but extreme volatility.",
        "ideal": "Aggressive investors with 10+ year horizon",
    },
    "hybrid": {
        "name": "Hybrid / Balanced", "color": "#7b5ea7", "type": "Equity + Debt Mix",
        "risk": "Moderate", "risk_score": 5, "return_range": "8–12%",
        "return_score": 6, "liquidity": "T+3 days", "liq_score": 7,
        "horizon": "3–5 years", "min_invest": "₹500", "exp_ratio": "0.5–1.5%",
        "lock_in": "None", "ltcg": "Depends on equity %", "stcg": "Depends on equity %",
        "description": "Mix of equity and debt. Smoother ride than pure equity.",
        "ideal": "Moderate risk investors wanting a one-fund portfolio",
    },
    "debt": {
        "name": "Debt / Bond Fund", "color": "#4a7c8e", "type": "Fixed Income",
        "risk": "Low-Moderate", "risk_score": 3, "return_range": "6–9%",
        "return_score": 4, "liquidity": "T+3 days", "liq_score": 6,
        "horizon": "1–3 years", "min_invest": "₹500", "exp_ratio": "0.2–1.0%",
        "lock_in": "None", "ltcg": "Slab rate", "stcg": "Slab rate",
        "description": "Invests in government and corporate bonds. Returns more predictable.",
        "ideal": "Conservative investors or near-term goals",
    },
    "liquid": {
        "name": "Liquid Fund", "color": "#5a8a5a", "type": "Money Market",
        "risk": "Very Low", "risk_score": 1, "return_range": "5–7%",
        "return_score": 3, "liquidity": "Same day / T+1", "liq_score": 10,
        "horizon": "Days to 3 months", "min_invest": "₹500", "exp_ratio": "0.1–0.5%",
        "lock_in": "None", "ltcg": "Slab rate", "stcg": "Slab rate",
        "description": "Invests in very short-term instruments. Highly stable and liquid.",
        "ideal": "Parking short-term surplus or emergency fund",
    },
    "elss": {
        "name": "ELSS (Tax Saver)", "color": "#c85a1a", "type": "Equity — Tax Benefit",
        "risk": "High", "risk_score": 8, "return_range": "10–15%",
        "return_score": 7, "liquidity": "Locked 3 years", "liq_score": 3,
        "horizon": "3+ years", "min_invest": "₹500", "exp_ratio": "0.5–1.8%",
        "lock_in": "3 years", "ltcg": "12.5% >₹1.25L", "stcg": "N/A (locked)",
        "description": "Equity fund with 3-year lock-in qualifying for 80C deduction up to ₹1.5L.",
        "ideal": "Investors seeking 80C deductions and equity returns",
    },
    "index": {
        "name": "Index Fund", "color": "#2a6a9a", "type": "Passive Equity",
        "risk": "Moderate-High", "risk_score": 6, "return_range": "10–13%*",
        "return_score": 7, "liquidity": "T+3 days", "liq_score": 7,
        "horizon": "5+ years", "min_invest": "₹500", "exp_ratio": "0.1–0.3%",
        "lock_in": "None", "ltcg": "12.5% >₹1.25L", "stcg": "20%",
        "description": "Passively tracks an index (e.g., Nifty 50). Very low costs.",
        "ideal": "Cost-conscious long-term investors who trust the market",
    },
}


QUIZ_QUESTIONS = [
    {
        "id": 1,
        "question": "What does NAV stand for, and what does it represent?",
        "context": "The most basic price concept in mutual funds.",
        "options": [
            "Net Asset Value — the per-unit price of a fund",
            "National Asset Value — the fund's total worth",
            "Net Allocation Value — how much you can invest",
            "Nominal Annual Value — the expected return",
        ],
        "answer": 0,
        "explanation": "NAV (Net Asset Value) is the per-unit price of a mutual fund, calculated daily as total assets minus liabilities divided by outstanding units. Invest ₹10,000 when NAV is ₹100 → you get 100 units.",
    },
    {
        "id": 2,
        "question": "The Rule of 72 helps you estimate what?",
        "context": "A powerful mental math shortcut used by investors worldwide.",
        "options": [
            "Your tax liability on gains",
            "How many years it takes to double your money",
            "A fund's expense ratio impact",
            "The minimum investment required",
        ],
        "answer": 1,
        "explanation": "Divide 72 by your annual return rate to estimate doubling time. At 12% → 72÷12 = 6 years. At 8% → 9 years. Simple, powerful, and surprisingly accurate for most rates.",
    },
    {
        "id": 3,
        "question": "You invest ₹1,000/month. Jan NAV = ₹50; Feb NAV = ₹40. What is your average cost per unit?",
        "context": "This tests Rupee Cost Averaging — the core benefit of SIP investing.",
        "options": ["₹45.00", "₹44.44", "₹42.50", "₹47.50"],
        "answer": 1,
        "explanation": "Jan: 20 units (₹1000/₹50). Feb: 25 units (₹1000/₹40). Total: 45 units for ₹2000. Avg cost = ₹2000/45 ≈ ₹44.44 — lower than the arithmetic average of ₹45. That's Rupee Cost Averaging!",
    },
    {
        "id": 4,
        "question": "Which 80C instrument has the SHORTEST mandatory lock-in?",
        "context": "Thinking about tax-saving investments under Section 80C.",
        "options": [
            "PPF (Public Provident Fund)",
            "NPS (National Pension System)",
            "ELSS (Equity Linked Savings Scheme)",
            "NSC (National Savings Certificate)",
        ],
        "answer": 2,
        "explanation": "ELSS has the shortest 3-year lock-in among 80C investments. PPF = 15 years, NSC = 5 years, NPS locks until retirement. ELSS also invests in equities, offering higher potential returns.",
    },
    {
        "id": 5,
        "question": "A fund has Beta = 1.4. If the market falls 10%, the fund likely:",
        "context": "Beta measures sensitivity to market movements.",
        "options": ["Falls 10%", "Falls 14%", "Falls 4%", "Rises 4%"],
        "answer": 1,
        "explanation": "Beta measures relative movement vs the market. Beta 1.4 = fund moves 1.4× the market. Market falls 10% → fund falls ~14%. Higher Beta = more upside in bull markets too, but more downside in bear markets.",
    },
    {
        "id": 6,
        "question": "What is the primary impact of a high expense ratio over time?",
        "context": "Costs compound just like returns — but against you.",
        "options": [
            "It means the fund is riskier",
            "It directly reduces your net returns every year",
            "It indicates poor diversification",
            "It means the fund is illiquid",
        ],
        "answer": 1,
        "explanation": "Expense ratio is charged annually as a % of AUM. 1.5% vs 0.5% ER on ₹10L over 20 years at 12% gross return = ~₹10–15 Lakh less in corpus. Index funds often win here with very low ERs (0.1–0.2%).",
    },
    {
        "id": 7,
        "question": "What is CAGR primarily used for?",
        "context": "The single most important metric for comparing investments.",
        "options": [
            "Calculating tax on capital gains",
            "Comparing growth across different investments and time periods",
            "Determining the fund manager's fee",
            "Setting the SIP amount",
        ],
        "answer": 1,
        "explanation": "CAGR (Compound Annual Growth Rate) shows the steady annual rate at which an investment grew. It makes comparing a 3-year and a 7-year investment meaningful, which raw % returns cannot. Formula: (End/Start)^(1/years) − 1.",
    },
    {
        "id": 8,
        "question": "You hold equity fund units for 14 months and sell with ₹2 Lakh gain. Tax payable?",
        "context": "LTCG rules for equity mutual funds as of Budget 2024.",
        "options": [
            "₹25,000 (12.5% on full ₹2L)",
            "Zero — equity gains are tax-free",
            "₹9,375 (12.5% on ₹75K above the ₹1.25L exemption)",
            "₹40,000 (20% on full ₹2L)",
        ],
        "answer": 2,
        "explanation": "Held >12 months → LTCG. Budget 2024: LTCG on equity is exempt up to ₹1.25L/year, taxed at 12.5% beyond. So: ₹2L − ₹1.25L = ₹75,000 taxable. Tax = 12.5% × ₹75,000 = ₹9,375.",
    },
]


# ─────────────────────────────────────────
# HTTP REQUEST HANDLER
# ─────────────────────────────────────────

class FundamentHandler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        # Custom clean logging
        print(f"  [{self.command}] {self.path} → {args[1] if len(args) > 1 else ''}")

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, path, content_type):
        try:
            with open(path, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache")
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        qs = parse_qs(parsed.query)

        def gp(key, default, cast=float):
            try:
                return cast(qs[key][0])
            except (KeyError, ValueError):
                return default

        # ── API ROUTES ──

        if path == "/api/health":
            self.send_json({"status": "ok", "version": "1.0.0", "app": "Fundament"})

        elif path == "/api/sip":
            result = calc_sip(
                monthly=gp("monthly", 5000),
                rate=gp("rate", 12),
                years=gp("years", 15),
                inflation=gp("inflation", 6),
                stepup=gp("stepup", 5),
            )
            self.send_json(result)

        elif path == "/api/lumpsum":
            result = calc_lumpsum(
                principal=gp("principal", 100000),
                rate=gp("rate", 12),
                years=gp("years", 10),
                inflation=gp("inflation", 6),
                freq=gp("freq", 4, int),
            )
            self.send_json(result)

        elif path == "/api/goal":
            result = calc_goal(
                target=gp("target", 1000000),
                years=gp("years", 10),
                rate=gp("rate", 12),
                inflation=gp("inflation", 6),
                existing=gp("existing", 0),
            )
            self.send_json(result)

        elif path == "/api/funds":
            self.send_json({"funds": FUND_DATA})

        elif path == "/api/fund":
            fund_id = qs.get("id", ["largecap"])[0]
            if fund_id in FUND_DATA:
                self.send_json(FUND_DATA[fund_id])
            else:
                self.send_json({"error": "Fund not found"}, 404)

        elif path == "/api/quiz":
            self.send_json({"questions": QUIZ_QUESTIONS, "total": len(QUIZ_QUESTIONS)})

        elif path == "/api/quiz/check":
            q_id = gp("id", 1, int)
            chosen = gp("chosen", 0, int)
            q = next((q for q in QUIZ_QUESTIONS if q["id"] == q_id), None)
            if not q:
                self.send_json({"error": "Question not found"}, 404)
                return
            correct = chosen == q["answer"]
            self.send_json({
                "correct": correct,
                "answer": q["answer"],
                "explanation": q["explanation"],
            })

        elif path == "/api/compare":
            a = qs.get("a", ["largecap"])[0]
            b = qs.get("b", ["midcap"])[0]
            fa = FUND_DATA.get(a)
            fb = FUND_DATA.get(b)
            if not fa or not fb:
                self.send_json({"error": "Fund not found"}, 404)
                return
            # Compute comparison insights
            insights = []
            if fa["risk_score"] > fb["risk_score"]:
                insights.append(f"{fa['name']} carries higher risk than {fb['name']}.")
            elif fa["risk_score"] < fb["risk_score"]:
                insights.append(f"{fb['name']} carries higher risk than {fa['name']}.")
            else:
                insights.append("Both funds carry similar risk profiles.")
            if fa["return_score"] > fb["return_score"]:
                insights.append(f"{fa['name']} has higher return potential.")
            elif fa["return_score"] < fb["return_score"]:
                insights.append(f"{fb['name']} has higher return potential.")
            if fa["liq_score"] != fb["liq_score"]:
                more_liquid = fa if fa["liq_score"] > fb["liq_score"] else fb
                insights.append(f"{more_liquid['name']} is more liquid.")
            self.send_json({"fund_a": fa, "fund_b": fb, "insights": insights})

        elif path == "/api/xirr":
            # Accepts JSON body cashflows via query for simplicity
            # cashflows=[[amount,days],...] base64 encoded
            import base64
            try:
                raw = qs.get("data", ["W10="])[0]
                decoded = base64.b64decode(raw).decode()
                pairs = json.loads(decoded)
                cashflows = [{"amount": p[0], "days": p[1]} for p in pairs]
                xirr = calc_xirr_approx(cashflows)
                self.send_json({"xirr": xirr})
            except Exception as e:
                self.send_json({"error": str(e)}, 400)

        # ── STATIC FILES ──

        elif path == "/" or path == "/index.html":
            self.send_file(os.path.join(BASE_DIR, "static", "index.html"), "text/html; charset=utf-8")

        elif path.startswith("/static/"):
            rel = path[1:]  # strip leading /
            file_path = os.path.join(BASE_DIR, rel)
            ext = os.path.splitext(file_path)[1]
            types = {
                ".html": "text/html; charset=utf-8",
                ".css": "text/css",
                ".js": "application/javascript",
                ".json": "application/json",
                ".png": "image/png",
                ".ico": "image/x-icon",
                ".svg": "image/svg+xml",
                ".woff2": "font/woff2",
            }
            self.send_file(file_path, types.get(ext, "application/octet-stream"))

        else:
            self.send_json({"error": "Not found", "path": path}, 404)

    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            data = {}

        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/quiz/submit":
            answers = data.get("answers", {})
            results = []
            score = 0
            for q in QUIZ_QUESTIONS:
                qid = str(q["id"])
                chosen = answers.get(qid, -1)
                correct = chosen == q["answer"]
                if correct:
                    score += 1
                results.append({
                    "id": q["id"],
                    "correct": correct,
                    "chosen": chosen,
                    "answer": q["answer"],
                    "explanation": q["explanation"],
                })
            pct = round(score / len(QUIZ_QUESTIONS) * 100, 1)
            self.send_json({
                "score": score,
                "total": len(QUIZ_QUESTIONS),
                "percentage": pct,
                "results": results,
            })

        elif path == "/api/sip/batch":
            # Compare multiple SIP scenarios at once
            scenarios = data.get("scenarios", [])
            results = []
            for s in scenarios[:5]:  # max 5 scenarios
                try:
                    result = calc_sip(
                        monthly=s.get("monthly", 5000),
                        rate=s.get("rate", 12),
                        years=s.get("years", 15),
                        inflation=s.get("inflation", 6),
                        stepup=s.get("stepup", 0),
                    )
                    result["label"] = s.get("label", "Scenario")
                    results.append(result)
                except Exception:
                    pass
            self.send_json({"results": results})

        else:
            self.send_json({"error": "Not found"}, 404)


# ─────────────────────────────────────────
# ENTRY POINT
# ─────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", 8080))


def open_browser():
    time.sleep(1.2)
    webbrowser.open(f"http://localhost:{PORT}")


def main():
    print()
    print("  ╔══════════════════════════════════════╗")
    print("  ║   F U N D A M E N T  v1.0.0          ║")
    print("  ║   Investor Education Platform         ║")
    print("  ╚══════════════════════════════════════╝")
    print()
    print(f"  🚀 Server starting on http://localhost:{PORT}")
    print(f"  📂 Serving from: {BASE_DIR}")
    print()
    print("  API Endpoints:")
    print(f"    GET  /api/health")
    print(f"    GET  /api/sip?monthly=5000&rate=12&years=15&inflation=6&stepup=5")
    print(f"    GET  /api/lumpsum?principal=100000&rate=12&years=10&inflation=6&freq=4")
    print(f"    GET  /api/goal?target=1000000&years=10&rate=12&inflation=6")
    print(f"    GET  /api/funds")
    print(f"    GET  /api/compare?a=largecap&b=midcap")
    print(f"    GET  /api/quiz")
    print(f"    POST /api/quiz/submit")
    print(f"    POST /api/sip/batch")
    print()
    print("  Press Ctrl+C to stop the server.")
    print()

    # Auto-open browser
    t = threading.Thread(target=open_browser, daemon=True)
    t.start()

    server = HTTPServer(("0.0.0.0", PORT), FundamentHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n  Shutting down gracefully. Goodbye!\n")
        server.shutdown()


if __name__ == "__main__":
    main()
