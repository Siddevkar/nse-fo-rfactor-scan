# File: nse_fo_rfactor_scan.py
import pandas as pd
import numpy as np
from nsepython import nse_get_fno_lot_sizes, nse_quote
from datetime import datetime, time
import pytz
import logging
import os
import time

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def is_trading_window():
    """Check if current time is between 9:15 AM and 10:00 AM IST."""
    ist = pytz.timezone('Asia/Kolkata')
    current_time = datetime.now(ist).time()
    return time(9, 15) <= current_time <= time(10, 0)

def fetch_fo_stocks():
    """Fetch the list of F&O stocks from NSE."""
    try:
        fo_data = nse_get_fno_lot_sizes()
        if fo_data.empty:
            logging.error("No F&O stocks retrieved.")
            return None
        fo_stocks = fo_data['SYMBOL'].unique().tolist()
        logging.info(f"Fetched {len(fo_stocks)} F&O stocks.")
        return fo_stocks
    except Exception as e:
        logging.error(f"Error fetching F&O stocks: {e}")
        return None

def fetch_stock_data(symbol):
    """Fetch real-time stock data for a given symbol."""
    try:
        quote = nse_quote(symbol)
        if not quote or 'priceInfo' not in quote:
            return None
        price_info = quote['priceInfo']
        data = {
            'symbol': symbol,
            'last_price': price_info.get('lastPrice', 0),
            'open_price': price_info.get('open', 0),
            'volume': price_info.get('totalTradedVolume', 0),
            'avg_volume': quote.get('averageDailyVolume', 1),
            'oi_change': quote.get('oi', 0)  # Simplified OI data
        }
        return data
    except Exception as e:
        logging.warning(f"Error fetching data for {symbol}: {e}")
        return None

def calculate_r_factor(df):
    """Calculate R Factor for each stock."""
    df['volume_score'] = (df['volume'] / df['avg_volume']) * 100
    df['momentum_score'] = ((df['last_price'] - df['open_price']) / df['open_price']) * 100
    df['order_flow_score'] = df['oi_change']
    
    for col in ['volume_score', 'momentum_score', 'order_flow_score']:
        df[col] = (df[col] - df[col].min()) / (df[col].max() - df[col].min() + 1e-10) * 100
    
    weights = {'volume': 0.4, 'momentum': 0.3, 'order_flow': 0.3}
    df['r_factor'] = (weights['volume'] * df['volume_score'] +
                      weights['momentum'] * df['momentum_score'] +
                      weights['order_flow'] * df['order_flow_score'])
    
    return df.sort_values('r_factor', ascending=False)

def main():
    """Scan F&O stocks between 9:15 AM and 10:00 AM IST."""
    if not is_trading_window():
        print("Script runs only between 9:15 AM and 10:00 AM IST.")
        return
    
    os.makedirs('output', exist_ok=True)
    fo_stocks = fetch_fo_stocks()
    if not fo_stocks:
        print("Failed to fetch F&O stocks.")
        return
    
    stock_data = []
    for symbol in fo_stocks[:50]:  # Limit to 50 to avoid rate limits
        data = fetch_stock_data(symbol)
        if data:
            stock_data.append(data)
        time.sleep(1)  # Avoid API rate limits
    
    if not stock_data:
        print("No stock data retrieved.")
        return
    
    df = pd.DataFrame(stock_data)
    df = calculate_r_factor(df)
    
    output_file = f"output/nse_fo_rfactor_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    df[['symbol', 'r_factor', 'last_price', 'volume']].to_csv(output_file, index=False)
    print(f"Results saved to {output_file}")
    print("\nTop 5 F&O Stocks by R Factor:")
    print(df[['symbol', 'r_factor', 'last_price']].head())

if __name__ == "__main__":
    main()
