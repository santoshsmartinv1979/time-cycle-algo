import streamlit as st
import pandas as pd
import numpy as np
import math
import yfinance as yf
from datetime import datetime, timedelta

# ------------------------------------------------------------------
# १. DIGIT SUM FUNCTION
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
# २. ATM STRIKE SELECTION
# ------------------------------------------------------------------
def get_atm_strike(price):
    return round(price / 50) * 50

# ------------------------------------------------------------------
# ३. मुख्य बॅकटेस्टिंग इंजिन (CORE ALGO ENGINE)
# ------------------------------------------------------------------
def run_backtest(df_1min):
    df_1min = df_1min.reset_index()
    df_1min['datetime'] = pd.to_datetime(df_1min['Datetime'])
    df_1min['date'] = df_1min['datetime'].dt.date
    df_1min['time'] = df_1min['datetime'].dt.time
    
    trade_logs = []
    daily_groups = df_1min.groupby('date')
    
    for date, group in daily_groups:
        group = group.sort_values('datetime').reset_index(drop=True)
        if len(group) == 0:
            continue
            
        open_915 = group.iloc['Open']
        digit_sum = get_digit_sum(open_915)
        
        time_cycle_idx = digit_sum
        if time_cycle_idx >= len(group):
            continue
            
        time_candle = group.iloc[time_cycle_idx]
        tc_high = time_candle['High']
        tc_low = time_candle['Low']
        atm_strike = get_atm_strike(time_candle['Close'])
        
        trades_count = 0
        is_profit_day = False
        active_trade = None
        cutoff_time = datetime.strptime("10:16:00", "%H:%M:%S").time()
        
        for i in range(time_cycle_idx + 1, len(group)):
            row = group.iloc[i]
            current_time = row['time']
            
            if current_time >= cutoff_time:
                if active_trade:
                    exit_price = row['Close']
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
                    if row['High'] >= active_trade['entry_price'] * 1.05 and not active_trade['is_trailed']:
                        active_trade['is_trailed'] = True
                        
                    if row['High'] >= active_trade['target_price']:
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
                        
                    elif row['Close'] < tc_low:
                        sl_exit_price = active_trade['entry_price'] if active_trade['is_trailed'] else row['Close']
                        pnl = sl_exit_price - active_trade['entry_price']
                        trade_logs.append({
                            'Date': date, 'Type': 'CE', 'Strike': atm_strike, 'Entry Time': active_trade['entry_time'],
                            'Entry Price': round(active_trade['entry_price'], 2), 'Exit Time': current_time,
                            'Exit Price': round(sl_exit_price, 2), 'Status': 'STOP LOSS HIT 🛑', 'PnL_Points': round(pnl, 2)
                        })
                        active_trade = None
                        trades_count += 1
                        
                elif active_trade['type'] == 'PE':
                    if row['Low'] <= active_trade['entry_price'] * 0.95 and not active_trade['is_trailed']:
                        active_trade['is_trailed'] = True
                        
                    if row['Low'] <= active_trade['target_price']:
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
                        
                    elif row['Close'] > tc_high:
                        sl_exit_price = active_trade['entry_price'] if active_trade['is_trailed'] else row['Close']
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
                    if row['High'] > tc_high:
                        active_trade = {
                            'type': 'CE', 'entry_time': current_time, 'entry_price': tc_high,
                            'target_price': tc_high * 1.10, 'is_trailed': False
                        }
                    elif row['Low'] < tc_low:
                        active_trade = {
                            'type': 'PE', 'entry_time': current_time, 'entry_price': tc_low,
                            'target_price': tc_low * 0.90, 'is_trailed': False
                        }
                        
    return pd.DataFrame(trade_logs)

# ------------------------------------------------------------------
# ४. STREAMLIT USER INTERFACE
# ------------------------------------------------------------------
st.set_page_config(page_title="Time Cycle Auto Tester", layout="wide")
st.title("📊 Time Cycle Customizable V27 - Live Free Data Tester")

st.sidebar.header("⚙️ Controls")
ticker = "^NSEI" 

days_to_test = st.sidebar.slider("मागील किती दिवसांचा डेटा तपासायचा आहे? (Days)", min_value=5, max_value=30, value=15)
lot_size = 65

if st.sidebar.button("Fetch Data & Run Backtest"):
    with st.spinner("NSE कडून १-मिनिटांचा लाईव्ह डेटा आणत आहे..."):
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=days_to_test)
        df_data = yf.download(ticker, start=start_dt, end=end_dt, interval="1m")
        
    if not df_data.empty:
        with st.spinner("अल्गोचे नियम लागू करत आहे..."):
            results_df = run_backtest(df_data)
            
        if not results_df.empty:
            results_df['Net_Profit_Rs'] = results_df['PnL_Points'] * lot_size
            total_trades = len(results_df)
            win_trades = len(results_df[results_df['Status'].str.contains('TARGET HIT')])
            win_rate = (win_trades / total_trades) * 100 if total_trades > 0 else 0
            total_pnl = results_df['Net_Profit_Rs'].sum()
            
            col1, col2, col3 = st.columns(3)
            col1.metric("📊 एकूण ट्रेड्स", f"{total_trades}")
            col2.metric("🎯 विन रेट (Win Rate)", f"{win_rate:.2f}%")
            col3.metric("💰 एकूण निव्वळ नफा/तोटा", f"₹ {total_pnl:,.2f}")
            
            st.markdown("---")
            st.subheader("📜 सविस्तर ट्रेड रिपोर्ट डायरी")
            st.dataframe(results_df, use_container_width=True)
            
            csv_data = results_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Excel CSV डाउनलोड करा", csv_data, "Time_Cycle_Auto_Report.csv", "text/csv")
        else:
            st.warning("या कालावधीत एकही ट्रेड ट्रिगर झाला नाही.")
    else:
        st.error("डेटा गोळा करता आला नाही. कृपया काही वेळाने प्रयत्न करा.")
else:
    st.info("👋 डाव्या बाजूला दिवस निवडून 'Fetch Data & Run Backtest' वर क्लिक करा.")
