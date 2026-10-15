import streamlit as st
import pandas as pd
import numpy as np
import math
import yfinance as yf
from datetime import datetime, timedelta

# ------------------------------------------------------------------
# १. DIGIT SUM FUNCTION (ओपन प्राईसच्या अंकांची बेरीज)
# ------------------------------------------------------------------
def get_digit_sum(price):
    int_price = math.floor(abs(price))
    sum_digits = 0
    temp = int_price
    for _ in range(12):
        if temp <= 0:
            break
        sum_digits += temp % 10
        temp = math.floor(temp / 10)
    return 15 if sum_digits == 0 else sum_digits

# ------------------------------------------------------------------
# २. ATM STRIKE SELECTION FUNCTION
# ------------------------------------------------------------------
def get_atm_strike(price):
    return round(price / 50) * 50

# ------------------------------------------------------------------
# ३. मुख्य बॅकटेस्टिंग इंजिन (CORE ALGO ENGINE)
# ------------------------------------------------------------------
def run_backtest(df_data):
    df_data = df_data.reset_index()
    if 'Datetime' in df_data.columns:
        df_data['datetime'] = pd.to_datetime(df_data['Datetime'])
    elif 'Date' in df_data.columns:
        df_data['datetime'] = pd.to_datetime(df_data['Date'])
    else:
        df_data['datetime'] = pd.to_datetime(df_data.iloc[:, 0])
        
    df_data['date'] = df_data['datetime'].dt.date
    df_data['time'] = df_data['datetime'].dt.time
    
    trade_logs = []
    daily_groups = df_data.groupby('date')
    
    for date, group in daily_groups:
        group = group.sort_values('datetime').reset_index(drop=True)
        if len(group) == 0:
            continue
            
        open_col = 'Open' if 'Open' in group.columns else 'open'
        high_col = 'High' if 'High' in group.columns else 'high'
        low_col = 'Low' if 'Low' in group.columns else 'low'
        close_col = 'Close' if 'Close' in group.columns else 'close'
        
        open_915 = group.loc[0, open_col]
        digit_sum = get_digit_sum(open_915)
        
        time_cycle_idx = min(digit_sum, len(group) - 1)
        
        time_candle = group.iloc[time_cycle_idx]
        tc_high = time_candle[high_col]
        tc_low = time_candle[low_col]
        atm_strike = get_atm_strike(time_candle[close_col])
        
        trades_count = 0
        is_profit_day = False
        active_trade = None
        cutoff_time = datetime.strptime("10:16:00", "%H:%M:%S").time()
        
        for i in range(time_cycle_idx + 1, len(group)):
            row = group.iloc[i]
            current_time = row['time']
            
            if current_time >= cutoff_time:
                if active_trade:
                    exit_price = row[close_col]
                    pnl = (exit_price - active_trade['entry_price']) if active_trade['type'] == 'CE' else (active_trade['entry_price'] - exit_price)
                    trade_logs.append({
                        'Date': date, 'Type': active_trade['type'], 'Strike': atm_strike,
                        'Entry Time': active_trade['entry_time'], 'Entry Price': round(active_trade['entry_price'], 2),
                        'Exit Time': current_time, 'Exit Price': round(exit_price, 2), 'Status': 'Auto Square-Off (10:16)', 'PnL_Points': round(pnl, 2)
                    })
                    active_trade = None
                break
                
            if is_profit_day:
                break
                
            if active_trade:
                if active_trade['type'] == 'CE':
                    if row[high_col] >= active_trade['entry_price'] * 1.05 and not active_trade['is_trailed']:
                        active_trade['is_trailed'] = True
                        
                    if row[high_col] >= active_trade['target_price']:
                        pnl = active_trade['target_price'] - active_trade['entry_price']
                        trade_logs.append({
                            'Date': date, 'Type': 'CE', 'Strike': atm_strike, 'Entry Time': active_trade['entry_time'],
                            'Entry Price': round(active_trade['entry_price'], 2), 'Exit Time': current_time,
                            'Exit Price': round(active_trade['target_price'], 2), 'Status': 'TARGET HIT 🎯', 'PnL_Points': round(pnl, 2)
                        })
                        is_profit_day = True
                        active_trade = None
                        trades_count += 1
                        continue
                        
                    elif row[close_col] < tc_low:
                        sl_exit_price = active_trade['entry_price'] if active_trade['is_trailed'] else row[close_col]
                        pnl = sl_exit_price - active_trade['entry_price']
                        trade_logs.append({
                            'Date': date, 'Type': 'CE', 'Strike': atm_strike, 'Entry Time': active_trade['entry_time'],
                            'Entry Price': round(active_trade['entry_price'], 2), 'Exit Time': current_time,
                            'Exit Price': round(sl_exit_price, 2), 'Status': 'STOP LOSS HIT 🛑', 'PnL_Points': round(pnl, 2)
                        })
                        active_trade = None
                        trades_count += 1
                        
                elif active_trade['type'] == 'PE':
                    if row[low_col] <= active_trade['entry_price'] * 0.95 and not active_trade['is_trailed']:
                        active_trade['is_trailed'] = True
                        
                    if row[low_col] <= active_trade['target_price']:
                        pnl = active_trade['entry_price'] - active_trade['target_price']
                        trade_logs.append({
                            'Date': date, 'Type': 'PE', 'Strike': atm_strike, 'Entry Time': active_trade['entry_time'],
                            'Entry Price': round(active_trade['entry_price'], 2), 'Exit Time': current_time,
                            'Exit Price': round(active_trade['target_price'], 2), 'Status': 'TARGET HIT 🎯', 'PnL_Points': round(pnl, 2)
                        })
                        is_profit_day = True
                        active_trade = None
                        trades_count += 1
                        continue
                        
                    elif row[close_col] > tc_high:
                        sl_exit_price = active_trade['entry_price'] if active_trade['is_trailed'] else row[close_col]
                        pnl = active_trade['entry_price'] - sl_exit_price
                        trade_logs.append({
                            'Date': date, 'Type': 'PE', 'Strike': atm_strike, 'Entry Time': active_trade['entry_time'],
                            'Entry Price': round(active_trade['entry_price'], 2), 'Exit Time': current_time,
                            'Exit Price': round(sl_exit_price, 2), 'Status': 'STOP LOSS HIT 🛑', 'PnL_Points': round(pnl, 2)
                        })
                        active_trade = None
                        trades_count += 1

            else:
                if trades_count < 2:
                    if row[high_col] > tc_high:
                        active_trade = {
                            'type': 'CE', 'entry_time': current_time, 'entry_price': tc_high,
                            'target_price': tc_high * 1.10, 'is_trailed': False
                        }
                    elif row[low_col] < tc_low:
                        active_trade = {
                            'type': 'PE', 'entry_time': current_time, 'entry_price': tc_low,
                            'target_price': tc_low * 0.90, 'is_trailed': False
                        }
                        
    return pd.DataFrame(trade_logs)

# ------------------------------------------------------------------
# ४. STREAMLIT USER INTERFACE (AUTO LOAD MODE)
# ------------------------------------------------------------------
st.set_page_config(page_title="Time Cycle Auto Pro", layout="wide")
st.title("📊 Time Cycle Customizable V27 - 30-Days Auto Backtester")

ticker = "NIFTY_50.NS" 
lot_size = 25  

st.info("🔄 सिस्टीम मागील ३० दिवसांचा निफ्टी डेटा इंटरनेटवरून थेट लोड करत आहे, कृपया ५ सेकंद थांबा...")

# कोणत्याही बटणाशिवाय थेट डेटा लोड करणे (No Button Required)
try:
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=30)
    df_data = yf.download(ticker, start=start_dt, end=end_dt, interval="5m")
    
    if not df_data.empty:
        results_df = run_backtest(df_data)
        
        if not results_df.empty:
            results_df['Net_Profit_Rs'] = results_df['PnL_Points'] * lot_size
            total_trades = len(results_df)
            win_trades = len(results_df[results_df['Status'].str.contains('TARGET HIT')])
            win_rate = (win_trades / total_trades) * 100 if total_trades > 0 else 0
            total_pnl = results_df['Net_Profit_Rs'].sum()
            
            # रिझल्ट डिस्प्ले
            col1, col2, col3 = st.columns(3)
            col1.metric("📊 एकूण ट्रेड्स", f"{total_trades}")
            col2.metric("🎯 विन रेट (Win Rate)", f"{win_rate:.2f}%")
            col3.metric("💰 एकूण निव्वळ नफा/तोटा", f"₹ {total_pnl:,.2f}")
            
            st.markdown("---")
            st.subheader("📜 मागील ३० दिवसांची सविस्तर ट्रेड रिपोर्ट डायरी")
            st.dataframe(results_df, use_container_width=True)
            
            csv_data = results_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 संपूर्ण रिपोर्ट Excel मध्ये डाऊनलोड करा", csv_data, "Time_Cycle_30Days_Report.csv", "text/csv")
        else:
            st.warning("या कालावधीत सिस्टीमच्या नियमांनुसार एकही ट्रेड ट्रिगर झाला नाही.")
    else:
        st.error("❌ मार्केट सुरू झाल्यामुळे NSE सर्व्हर बिझी आहे, कृपया १ मिनिटाने पेज रिफ्रेश करा.")
except Exception as e:
    st.error(f"डेटा लोड करताना चूक झाली: {e}")
