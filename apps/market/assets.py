"""Curated asset universe across all classes."""

ASSET_CATEGORIES = {
    "US Tech": [
        ("Apple", "AAPL"), ("Microsoft", "MSFT"), ("NVIDIA", "NVDA"),
        ("Alphabet", "GOOGL"), ("Amazon", "AMZN"), ("Meta", "META"),
        ("Tesla", "TSLA"), ("Netflix", "NFLX"), ("AMD", "AMD"),
        ("Intel", "INTC"), ("Oracle", "ORCL"), ("Salesforce", "CRM"),
        ("Adobe", "ADBE"), ("Broadcom", "AVGO"), ("Palantir", "PLTR"),
        ("Qualcomm", "QCOM"), ("Uber", "UBER"), ("Shopify", "SHOP"),
        ("Snowflake", "SNOW"), ("ServiceNow", "NOW"),
    ],
    "US Finance": [
        ("JPMorgan", "JPM"), ("Bank of America", "BAC"), ("Goldman Sachs", "GS"),
        ("Visa", "V"), ("Mastercard", "MA"), ("Berkshire", "BRK-B"),
        ("PayPal", "PYPL"), ("BlackRock", "BLK"), ("Morgan Stanley", "MS"),
        ("Wells Fargo", "WFC"), ("American Express", "AXP"), ("Citigroup", "C"),
    ],
    "US Consumer & Industrial": [
        ("Disney", "DIS"), ("Walmart", "WMT"), ("Coca-Cola", "KO"),
        ("PepsiCo", "PEP"), ("McDonald's", "MCD"), ("Nike", "NKE"),
        ("Boeing", "BA"), ("Ford", "F"), ("GM", "GM"), ("Exxon", "XOM"),
        ("Chevron", "CVX"), ("Pfizer", "PFE"), ("Johnson & Johnson", "JNJ"),
        ("UnitedHealth", "UNH"), ("Home Depot", "HD"), ("Starbucks", "SBUX"),
    ],
    "Indian NSE": [
        ("Reliance", "RELIANCE.NS"), ("TCS", "TCS.NS"), ("HDFC Bank", "HDFCBANK.NS"),
        ("Infosys", "INFY.NS"), ("ICICI Bank", "ICICIBANK.NS"), ("SBI", "SBIN.NS"),
        ("Tata Motors", "TATAMOTORS.NS"), ("Wipro", "WIPRO.NS"),
        ("Adani Enterprises", "ADANIENT.NS"), ("Bajaj Finance", "BAJFINANCE.NS"),
        ("Asian Paints", "ASIANPAINT.NS"), ("Hindustan Unilever", "HINDUNILVR.NS"),
        ("Maruti Suzuki", "MARUTI.NS"), ("Axis Bank", "AXISBANK.NS"),
        ("Larsen & Toubro", "LT.NS"), ("ITC", "ITC.NS"),
        ("Bharti Airtel", "BHARTIARTL.NS"), ("Kotak Bank", "KOTAKBANK.NS"),
        ("Zomato", "ZOMATO.NS"), ("Paytm", "PAYTM.NS"),
    ],
    "Crypto": [
        ("Bitcoin", "BTC-USD"), ("Ethereum", "ETH-USD"), ("Solana", "SOL-USD"),
        ("Binance Coin", "BNB-USD"), ("XRP", "XRP-USD"), ("Cardano", "ADA-USD"),
        ("Dogecoin", "DOGE-USD"), ("Polygon", "MATIC-USD"),
        ("Avalanche", "AVAX-USD"), ("Chainlink", "LINK-USD"),
        ("Polkadot", "DOT-USD"), ("Litecoin", "LTC-USD"),
        ("Shiba Inu", "SHIB-USD"), ("Uniswap", "UNI-USD"),
        ("Cosmos", "ATOM-USD"), ("TRON", "TRX-USD"),
    ],
    "ETFs & Indices": [
        ("S&P 500 (SPY)", "SPY"), ("NASDAQ 100 (QQQ)", "QQQ"),
        ("Dow Jones (DIA)", "DIA"), ("Russell 2000 (IWM)", "IWM"),
        ("Gold ETF", "GLD"), ("Silver ETF", "SLV"), ("Oil ETF", "USO"),
        ("20Y Treasury", "TLT"), ("VIX", "^VIX"), ("Nifty 50", "^NSEI"),
        ("Sensex", "^BSESN"), ("FTSE 100", "^FTSE"), ("Nikkei 225", "^N225"),
        ("DAX", "^GDAXI"), ("Hang Seng", "^HSI"),
    ],
    "Forex": [
        ("EUR/USD", "EURUSD=X"), ("GBP/USD", "GBPUSD=X"),
        ("USD/JPY", "JPY=X"), ("USD/INR", "INR=X"),
        ("AUD/USD", "AUDUSD=X"), ("USD/CAD", "CAD=X"),
        ("USD/CHF", "CHF=X"), ("NZD/USD", "NZDUSD=X"),
        ("EUR/GBP", "EURGBP=X"), ("EUR/JPY", "EURJPY=X"),
    ],
    "Commodities": [
        ("Gold Futures", "GC=F"), ("Silver Futures", "SI=F"),
        ("Crude Oil", "CL=F"), ("Natural Gas", "NG=F"),
        ("Copper", "HG=F"), ("Wheat", "ZW=F"),
        ("Corn", "ZC=F"), ("Coffee", "KC=F"),
        ("Sugar", "SB=F"), ("Cotton", "CT=F"),
    ],
}


def all_tickers() -> list:
    out = []
    for cat, items in ASSET_CATEGORIES.items():
        for name, symbol in items:
            out.append({"category": cat, "name": name, "symbol": symbol})
    return out


def find_symbol(query: str) -> list:
    """Simple search over asset universe."""
    q = query.strip().upper()
    results = []
    for cat, items in ASSET_CATEGORIES.items():
        for name, symbol in items:
            if q in symbol.upper() or q in name.upper():
                results.append({"category": cat, "name": name, "symbol": symbol})
    return results[:20]
