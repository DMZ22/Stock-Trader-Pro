"""Curated asset universe across all asset classes."""

ASSET_CATEGORIES = {
    "US Tech": [
        ("Apple", "AAPL"), ("Microsoft", "MSFT"), ("NVIDIA", "NVDA"),
        ("Alphabet", "GOOGL"), ("Amazon", "AMZN"), ("Meta", "META"),
        ("Tesla", "TSLA"), ("Netflix", "NFLX"), ("AMD", "AMD"),
        ("Intel", "INTC"), ("Oracle", "ORCL"), ("Salesforce", "CRM"),
        ("Adobe", "ADBE"), ("Broadcom", "AVGO"), ("Palantir", "PLTR"),
        ("Qualcomm", "QCOM"), ("Uber", "UBER"), ("Shopify", "SHOP"),
        ("Snowflake", "SNOW"), ("ServiceNow", "NOW"), ("ASML", "ASML"),
        ("TSMC", "TSM"), ("Micron", "MU"), ("Applied Materials", "AMAT"),
        ("Lam Research", "LRCX"), ("Cisco", "CSCO"), ("IBM", "IBM"),
    ],
    "US Finance": [
        ("JPMorgan", "JPM"), ("Bank of America", "BAC"), ("Goldman Sachs", "GS"),
        ("Visa", "V"), ("Mastercard", "MA"), ("Berkshire", "BRK-B"),
        ("PayPal", "PYPL"), ("BlackRock", "BLK"), ("Morgan Stanley", "MS"),
        ("Wells Fargo", "WFC"), ("American Express", "AXP"), ("Citigroup", "C"),
        ("Charles Schwab", "SCHW"), ("S&P Global", "SPGI"),
    ],
    "US Consumer & Industrial": [
        ("Disney", "DIS"), ("Walmart", "WMT"), ("Coca-Cola", "KO"),
        ("PepsiCo", "PEP"), ("McDonald's", "MCD"), ("Nike", "NKE"),
        ("Boeing", "BA"), ("Ford", "F"), ("GM", "GM"), ("Exxon", "XOM"),
        ("Chevron", "CVX"), ("Pfizer", "PFE"), ("Johnson & Johnson", "JNJ"),
        ("UnitedHealth", "UNH"), ("Home Depot", "HD"), ("Starbucks", "SBUX"),
        ("Costco", "COST"), ("Target", "TGT"), ("Eli Lilly", "LLY"),
        ("Merck", "MRK"), ("Procter & Gamble", "PG"),
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
        ("HCL Tech", "HCLTECH.NS"), ("Tech Mahindra", "TECHM.NS"),
        ("Sun Pharma", "SUNPHARMA.NS"), ("Nestle India", "NESTLEIND.NS"),
        ("Bajaj Auto", "BAJAJ-AUTO.NS"), ("Titan", "TITAN.NS"),
        ("UltraTech Cement", "ULTRACEMCO.NS"), ("Power Grid", "POWERGRID.NS"),
        ("NTPC", "NTPC.NS"), ("ONGC", "ONGC.NS"), ("Coal India", "COALINDIA.NS"),
        ("IndusInd Bank", "INDUSINDBK.NS"), ("Tata Steel", "TATASTEEL.NS"),
        ("JSW Steel", "JSWSTEEL.NS"), ("M&M", "M&M.NS"),
    ],
    "Major Crypto (USD)": [
        ("Bitcoin/USD", "BTC-USD"), ("Ethereum/USD", "ETH-USD"),
        ("Binance Coin/USD", "BNB-USD"), ("Solana/USD", "SOL-USD"),
        ("XRP/USD", "XRP-USD"), ("Cardano/USD", "ADA-USD"),
        ("Dogecoin/USD", "DOGE-USD"), ("Avalanche/USD", "AVAX-USD"),
        ("TRON/USD", "TRX-USD"), ("Polkadot/USD", "DOT-USD"),
        ("Polygon/USD", "MATIC-USD"), ("Chainlink/USD", "LINK-USD"),
        ("Litecoin/USD", "LTC-USD"), ("Shiba Inu/USD", "SHIB-USD"),
        ("Uniswap/USD", "UNI-USD"), ("Cosmos/USD", "ATOM-USD"),
    ],
    "Crypto USDT Pairs": [
        ("BTC/USDT", "BTC-USDT"), ("ETH/USDT", "ETH-USDT"),
        ("SOL/USDT", "SOL-USDT"), ("BNB/USDT", "BNB-USDT"),
        ("XRP/USDT", "XRP-USDT"), ("ADA/USDT", "ADA-USDT"),
        ("DOGE/USDT", "DOGE-USDT"), ("AVAX/USDT", "AVAX-USDT"),
        ("MATIC/USDT", "MATIC-USDT"), ("LINK/USDT", "LINK-USDT"),
        ("LTC/USDT", "LTC-USDT"), ("DOT/USDT", "DOT-USDT"),
    ],
    "Crypto - DeFi & L1": [
        ("Near Protocol", "NEAR-USD"), ("Aptos", "APT-USD"),
        ("Arbitrum", "ARB-USD"), ("Optimism", "OP-USD"),
        ("Sui", "SUI-USD"), ("Injective", "INJ-USD"),
        ("Sei", "SEI-USD"), ("Render", "RNDR-USD"),
        ("Celestia", "TIA-USD"), ("Kaspa", "KAS-USD"),
        ("Maker", "MKR-USD"), ("Aave", "AAVE-USD"),
        ("Lido DAO", "LDO-USD"), ("Compound", "COMP-USD"),
        ("Curve DAO", "CRV-USD"), ("Synthetix", "SNX-USD"),
        ("Stacks", "STX-USD"), ("Algorand", "ALGO-USD"),
        ("Tezos", "XTZ-USD"), ("Hedera", "HBAR-USD"),
    ],
    "Crypto - Meme & Alt": [
        ("Pepe", "PEPE-USD"), ("Bonk", "BONK-USD"),
        ("Floki", "FLOKI-USD"), ("Dogwifhat", "WIF-USD"),
        ("Book of Meme", "BOME-USD"), ("Mog Coin", "MOG-USD"),
        ("Bitcoin Cash", "BCH-USD"), ("Ethereum Classic", "ETC-USD"),
        ("Monero", "XMR-USD"), ("Zcash", "ZEC-USD"),
        ("Dash", "DASH-USD"), ("VeChain", "VET-USD"),
        ("Filecoin", "FIL-USD"), ("Internet Computer", "ICP-USD"),
        ("The Graph", "GRT-USD"), ("Fantom", "FTM-USD"),
        ("Flow", "FLOW-USD"), ("Axie Infinity", "AXS-USD"),
        ("Sandbox", "SAND-USD"), ("Decentraland", "MANA-USD"),
        ("ApeCoin", "APE-USD"), ("Chiliz", "CHZ-USD"),
    ],
    "Precious Metals & Miners": [
        ("Gold/USD", "GC=F"), ("Silver/USD", "SI=F"),
        ("Platinum/USD", "PL=F"), ("Palladium/USD", "PA=F"),
        ("Gold ETF (GLD)", "GLD"), ("Silver ETF (SLV)", "SLV"),
        ("Platinum ETF (PPLT)", "PPLT"), ("Gold Miners (GDX)", "GDX"),
        ("Junior Miners (GDXJ)", "GDXJ"), ("Silver Miners (SIL)", "SIL"),
        ("Newmont Mining", "NEM"), ("Barrick Gold", "GOLD"),
        ("Franco-Nevada", "FNV"), ("Wheaton Precious", "WPM"),
        ("Kinross Gold", "KGC"), ("AngloGold Ashanti", "AU"),
    ],
    "Commodities - Energy & Agri": [
        ("Crude Oil (WTI)", "CL=F"), ("Brent Crude", "BZ=F"),
        ("Natural Gas", "NG=F"), ("Heating Oil", "HO=F"),
        ("Gasoline", "RB=F"), ("Copper", "HG=F"),
        ("Aluminum", "ALI=F"), ("Wheat", "ZW=F"),
        ("Corn", "ZC=F"), ("Soybeans", "ZS=F"),
        ("Coffee", "KC=F"), ("Sugar", "SB=F"),
        ("Cotton", "CT=F"), ("Cocoa", "CC=F"),
        ("Live Cattle", "LE=F"), ("Lean Hogs", "HE=F"),
        ("Lumber", "LBR=F"), ("Orange Juice", "OJ=F"),
    ],
    "ETFs & Indices": [
        ("S&P 500 (SPY)", "SPY"), ("NASDAQ 100 (QQQ)", "QQQ"),
        ("Dow Jones (DIA)", "DIA"), ("Russell 2000 (IWM)", "IWM"),
        ("20Y Treasury (TLT)", "TLT"), ("VIX Index", "^VIX"),
        ("Emerging Markets (EEM)", "EEM"), ("China (MCHI)", "MCHI"),
        ("Europe (VGK)", "VGK"), ("Japan (EWJ)", "EWJ"),
        ("India (INDA)", "INDA"), ("Semiconductors (SOXX)", "SOXX"),
        ("Biotech (XBI)", "XBI"), ("Financials (XLF)", "XLF"),
        ("Energy (XLE)", "XLE"), ("Utilities (XLU)", "XLU"),
        ("Nifty 50", "^NSEI"), ("Sensex", "^BSESN"),
        ("FTSE 100", "^FTSE"), ("Nikkei 225", "^N225"),
        ("DAX", "^GDAXI"), ("Hang Seng", "^HSI"),
        ("CAC 40", "^FCHI"), ("ASX 200", "^AXJO"),
    ],
    "Forex": [
        ("EUR/USD", "EURUSD=X"), ("GBP/USD", "GBPUSD=X"),
        ("USD/JPY", "JPY=X"), ("USD/INR", "INR=X"),
        ("AUD/USD", "AUDUSD=X"), ("USD/CAD", "CAD=X"),
        ("USD/CHF", "CHF=X"), ("NZD/USD", "NZDUSD=X"),
        ("EUR/GBP", "EURGBP=X"), ("EUR/JPY", "EURJPY=X"),
        ("GBP/JPY", "GBPJPY=X"), ("AUD/JPY", "AUDJPY=X"),
        ("USD/CNY", "CNY=X"), ("USD/SGD", "SGD=X"),
        ("USD/HKD", "HKD=X"), ("USD/MXN", "MXN=X"),
        ("USD/ZAR", "ZAR=X"), ("USD/BRL", "BRL=X"),
    ],
}


def all_tickers() -> list:
    out = []
    for cat, items in ASSET_CATEGORIES.items():
        for name, symbol in items:
            out.append({"category": cat, "name": name, "symbol": symbol})
    return out


def find_symbol(query: str) -> list:
    q = query.strip().upper()
    results = []
    for cat, items in ASSET_CATEGORIES.items():
        for name, symbol in items:
            if q in symbol.upper() or q in name.upper():
                results.append({"category": cat, "name": name, "symbol": symbol})
    return results[:30]
