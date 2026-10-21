import datetime
import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import fear_greed
import requests

app = FastAPI(title="CNN Fear & Greed + SPY Fibonacci PWA")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Fear & Greed Library Endpoints ---

@app.get("/api/get")
def api_get():
    return fear_greed.get()

@app.get("/api/score")
def api_score():
    return {"score": fear_greed.get_score()}

@app.get("/api/rating")
def api_rating():
    return {"rating": fear_greed.get_rating()}

@app.get("/api/history")
def api_history(last: str = Query(default="30d"), start: str = None, end: str = None):
    kwargs = {}
    if last: kwargs["last"] = last
    if start: kwargs["start"] = start
    if end: kwargs["end"] = end
    return fear_greed.get_history(**kwargs)

@app.get("/api/raw")
def api_raw():
    return fear_greed.fetch()

# --- SPY 1-Month Fibonacci Endpoint ---

@app.get("/api/spy/fibonacci")
def get_spy_fibonacci():
    """
    Computes Fibonacci retracement levels from the highest to lowest close
    prices for SPY over the past 1 month.
    """
    # 1. Primary Method: yfinance
    try:
        import yfinance as yf
        ticker = yf.Ticker("SPY")
        hist = ticker.history(period="1mo")
        if not hist.empty and len(hist) >= 5:
            highest_close = float(hist["Close"].max())
            lowest_close = float(hist["Close"].min())
            current_close = float(hist["Close"].iloc[-1])
            highest_date = hist["Close"].idxmax().strftime("%Y-%m-%d")
            lowest_date = hist["Close"].idxmin().strftime("%Y-%m-%d")

            diff = highest_close - lowest_close
            levels = [
                {"ratio": 0.0, "label": "0.0% (1M High Close)", "type": "Swing High (Resistance)", "price": round(highest_close, 2), "color": "#f87171"},
                {"ratio": 0.236, "label": "23.6% Retracement", "type": "Minor Pullback", "price": round(highest_close - 0.236 * diff, 2), "color": "#fb923c"},
                {"ratio": 0.382, "label": "38.2% Retracement", "type": "Fib Retracement", "price": round(highest_close - 0.382 * diff, 2), "color": "#facc15"},
                {"ratio": 0.500, "label": "50.0% Midpoint", "type": "Equilibrium", "price": round(highest_close - 0.500 * diff, 2), "color": "#38bdf8"},
                {"ratio": 0.618, "label": "61.8% Golden Ratio", "type": "Golden Ratio Support", "price": round(highest_close - 0.618 * diff, 2), "color": "#4ade80"},
                {"ratio": 0.786, "label": "78.6% Retracement", "type": "Deep Pullback", "price": round(highest_close - 0.786 * diff, 2), "color": "#a78bfa"},
                {"ratio": 1.0, "label": "100.0% (1M Low Close)", "type": "Swing Low (Support)", "price": round(lowest_close, 2), "color": "#34d399"}
            ]

            history = []
            for dt, row in hist.iterrows():
                history.append({
                    "date": dt.strftime("%Y-%m-%d"),
                    "close": round(float(row["Close"]), 2),
                    "open": round(float(row["Open"]), 2) if "Open" in row else None,
                    "high": round(float(row["High"]), 2) if "High" in row else None,
                    "low": round(float(row["Low"]), 2) if "Low" in row else None,
                })

            return {
                "symbol": "SPY",
                "period": "1mo",
                "current_close": round(current_close, 2),
                "highest_close": round(highest_close, 2),
                "highest_date": highest_date,
                "lowest_close": round(lowest_close, 2),
                "lowest_date": lowest_date,
                "range": round(diff, 2),
                "levels": levels,
                "history": history
            }
    except Exception as e:
        print(f"yfinance lookup failed: {e}. Trying fallback chart endpoint...")

    # 2. Resilient Direct HTTP Fallback
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/SPY?range=1mo&interval=1d"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code == 200:
            result = resp.json()["chart"]["result"][0]
            timestamps = result["timestamp"]
            closes = result["indicators"]["quote"][0]["close"]

            valid_history = []
            for ts, c in zip(timestamps, closes):
                if c is not None:
                    d_str = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d")
                    valid_history.append({"date": d_str, "close": round(float(c), 2)})

            if valid_history:
                highest_pt = max(valid_history, key=lambda x: x["close"])
                lowest_pt = min(valid_history, key=lambda x: x["close"])
                current_close = valid_history[-1]["close"]
                diff = highest_pt["close"] - lowest_pt["close"]

                levels = [
                    {"ratio": 0.0, "label": "0.0% (1M High Close)", "type": "Swing High (Resistance)", "price": round(highest_pt["close"], 2), "color": "#f87171"},
                    {"ratio": 0.236, "label": "23.6% Retracement", "type": "Minor Pullback", "price": round(highest_pt["close"] - 0.236 * diff, 2), "color": "#fb923c"},
                    {"ratio": 0.382, "label": "38.2% Retracement", "type": "Fib Retracement", "price": round(highest_pt["close"] - 0.382 * diff, 2), "color": "#facc15"},
                    {"ratio": 0.500, "label": "50.0% Midpoint", "type": "Equilibrium", "price": round(highest_pt["close"] - 0.500 * diff, 2), "color": "#38bdf8"},
                    {"ratio": 0.618, "label": "61.8% Golden Ratio", "type": "Golden Ratio Support", "price": round(highest_pt["close"] - 0.618 * diff, 2), "color": "#4ade80"},
                    {"ratio": 0.786, "label": "78.6% Retracement", "type": "Deep Pullback", "price": round(highest_pt["close"] - 0.786 * diff, 2), "color": "#a78bfa"},
                    {"ratio": 1.0, "label": "100.0% (1M Low Close)", "type": "Swing Low (Support)", "price": round(lowest_pt["close"], 2), "color": "#34d399"}
                ]

                return {
                    "symbol": "SPY",
                    "period": "1mo",
                    "current_close": current_close,
                    "highest_close": highest_pt["close"],
                    "highest_date": highest_pt["date"],
                    "lowest_close": lowest_pt["close"],
                    "lowest_date": lowest_pt["date"],
                    "range": round(diff, 2),
                    "levels": levels,
                    "history": valid_history
                }
    except Exception as e:
        print(f"Direct chart request failed: {e}")

    raise HTTPException(status_code=500, detail="Unable to retrieve SPY price data at this time.")

# --- Serve Single-File PWA ---
@app.get("/")
def serve_index():
    return FileResponse("index.html")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port)