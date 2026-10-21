import calendar
import datetime
import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import fear_greed
import requests

app = FastAPI(title="CNN Fear & Greed + SPY Fibonacci PWA", version="1.0.0")

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
    try:
        return fear_greed.get()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/score")
def api_score():
    try:
        return {"score": fear_greed.get_score()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/rating")
def api_rating():
    try:
        return {"rating": fear_greed.get_rating()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/history")
def api_history(
    last: str = Query(default="30d", description="e.g. 7d, 30d, 90d, 1y"),
    start: str = None,
    end: str = None
):
    try:
        kwargs = {}
        if last: kwargs["last"] = last
        if start: kwargs["start"] = start
        if end: kwargs["end"] = end
        return fear_greed.get_history(**kwargs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/raw")
def api_raw():
    try:
        return fear_greed.fetch()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- SPY Fibonacci Retracement Endpoint ---

@app.get("/api/spy/fibonacci")
def get_spy_fibonacci(
    mode: str = Query(default="calendar", description="'calendar' for prior full month, 'rolling' for past 30 days")
):
    today = datetime.date.today()
    
    if mode == "calendar":
        first_day_curr_month = today.replace(day=1)
        last_day_prev_month = first_day_curr_month - datetime.timedelta(days=1)
        first_day_prev_month = last_day_prev_month.replace(day=1)
        end_fetch = last_day_prev_month + datetime.timedelta(days=1)
        
        start_str = first_day_prev_month.strftime("%Y-%m-%d")
        end_str = end_fetch.strftime("%Y-%m-%d")
        period_label = first_day_prev_month.strftime("%B %Y")
        end_display = last_day_prev_month.strftime("%Y-%m-%d")
    else:
        start_date = today - datetime.timedelta(days=30)
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = (today + datetime.timedelta(days=1)).strftime("%Y-%m-%d")
        period_label = "Past 30 Days (Rolling)"
        end_display = today.strftime("%Y-%m-%d")

    # 1. Primary Method: yfinance
    try:
        import yfinance as yf
        ticker = yf.Ticker("SPY")
        hist = ticker.history(start=start_str, end=end_str)
        
        if not hist.empty and len(hist) >= 3:
            highest_close = float(hist["Close"].max())
            lowest_close = float(hist["Close"].min())
            
            cur_hist = yf.Ticker("SPY").history(period="1d")
            current_close = float(cur_hist["Close"].iloc[-1]) if not cur_hist.empty else float(hist["Close"].iloc[-1])

            highest_date = hist["Close"].idxmax().strftime("%Y-%m-%d")
            lowest_date = hist["Close"].idxmin().strftime("%Y-%m-%d")
            diff = highest_close - lowest_close

            # 0% = Lowest Close, 100% = Highest Close
            levels = [
                {"ratio": 1.0,   "label": "100.0% (1M High Close)", "type": "Swing High (Resistance)", "price": round(lowest_close + 1.000 * diff, 2), "color": "#f87171"},
                {"ratio": 0.786, "label": "78.6% Fib Level",        "type": "Deep Pullback Target",     "price": round(lowest_close + 0.786 * diff, 2), "color": "#a78bfa"},
                {"ratio": 0.618, "label": "61.8% Golden Ratio",     "type": "Golden Ratio Support",     "price": round(lowest_close + 0.618 * diff, 2), "color": "#4ade80"},
                {"ratio": 0.500, "label": "50.0% Midpoint",         "type": "Equilibrium",              "price": round(lowest_close + 0.500 * diff, 2), "color": "#38bdf8"},
                {"ratio": 0.382, "label": "38.2% Fib Level",        "type": "First Major Retracement",  "price": round(lowest_close + 0.382 * diff, 2), "color": "#facc15"},
                {"ratio": 0.236, "label": "23.6% Fib Level",        "type": "Shallow Retracement",      "price": round(lowest_close + 0.236 * diff, 2), "color": "#fb923c"},
                {"ratio": 0.0,   "label": "0.0% (1M Low Close)",    "type": "Swing Low (Base Support)", "price": round(lowest_close, 2),                "color": "#34d399"}
            ]

            # Daily history with High, Low, Close
            history = [
                {
                    "date": dt.strftime("%Y-%m-%d"),
                    "high": round(float(row["High"]), 2),
                    "low": round(float(row["Low"]), 2),
                    "close": round(float(row["Close"]), 2)
                }
                for dt, row in hist.iterrows()
            ]

            return {
                "symbol": "SPY",
                "period": period_label,
                "mode": mode,
                "start_date": start_str,
                "end_date": end_display,
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
        print(f"yfinance failed: {e}. Trying direct HTTP fallback...")

    # 2. Resilient Direct HTTP Fallback
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/SPY?range=1mo&interval=1d"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code == 200:
            result = resp.json()["chart"]["result"][0]
            timestamps = result["timestamp"]
            quote = result["indicators"]["quote"][0]
            highs = quote.get("high", [])
            lows = quote.get("low", [])
            closes = quote.get("close", [])

            valid_history = []
            for ts, h, l, c in zip(timestamps, highs, lows, closes):
                if c is not None and h is not None and l is not None:
                    d_str = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).strftime("%Y-%m-%d")
                    valid_history.append({
                        "date": d_str,
                        "high": round(float(h), 2),
                        "low": round(float(l), 2),
                        "close": round(float(c), 2)
                    })

            if valid_history:
                highest_pt = max(valid_history, key=lambda x: x["close"])
                lowest_pt = min(valid_history, key=lambda x: x["close"])
                current_close = valid_history[-1]["close"]
                diff = highest_pt["close"] - lowest_pt["close"]

                levels = [
                    {"ratio": 1.0,   "label": "100.0% (1M High Close)", "type": "Swing High (Resistance)", "price": round(lowest_pt["close"] + 1.000 * diff, 2), "color": "#f87171"},
                    {"ratio": 0.786, "label": "78.6% Fib Level",        "type": "Deep Pullback Target",     "price": round(lowest_pt["close"] + 0.786 * diff, 2), "color": "#a78bfa"},
                    {"ratio": 0.618, "label": "61.8% Golden Ratio",     "type": "Golden Ratio Support",     "price": round(lowest_pt["close"] + 0.618 * diff, 2), "color": "#4ade80"},
                    {"ratio": 0.500, "label": "50.0% Midpoint",         "type": "Equilibrium",              "price": round(lowest_pt["close"] + 0.500 * diff, 2), "color": "#38bdf8"},
                    {"ratio": 0.382, "label": "38.2% Fib Level",        "type": "First Major Retracement",  "price": round(lowest_pt["close"] + 0.382 * diff, 2), "color": "#facc15"},
                    {"ratio": 0.236, "label": "23.6% Fib Level",        "type": "Shallow Retracement",      "price": round(lowest_pt["close"] + 0.236 * diff, 2), "color": "#fb923c"},
                    {"ratio": 0.0,   "label": "0.0% (1M Low Close)",    "type": "Swing Low (Base Support)", "price": round(lowest_pt["close"], 2),                "color": "#34d399"}
                ]

                return {
                    "symbol": "SPY",
                    "period": period_label,
                    "mode": mode,
                    "start_date": valid_history[0]["date"],
                    "end_date": valid_history[-1]["date"],
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
        print(f"Fallback request failed: {e}")

    raise HTTPException(status_code=500, detail="Unable to retrieve SPY price data at this time.")

@app.get("/")
def serve_index():
    return FileResponse("index.html")

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port)