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
    # कॉलम नावे योग्य फॉरमॅट करणे
    if 'Datetime' in df_data.columns:
        df_data['datetime'] = pd.to_datetime(df_data['Datetime'])
    elif 'Date' in df_data.columns:
        df_data['datetime'] = pd.to_datetime(df_data['Date'])
        
    df_data['date'] = df_data['datetime'].dt.date
    df_data['time'] = df_data['datetime'].dt.time
    
    trade_logs = []
    daily_groups = df_data.groupby('date')
    
    for date, group in daily_groups:
        group = group.sort_values('datetime').reset_index(drop=True)
        if len(group) == 0:
            continue
            
        # ९:१५ ची ओपन प्राईस
        open_915 = group.loc[0, 'Open']
        digit_sum = get_digit_sum(open_915)
        
        # ५-मिनिटांच्या कॅन्डलनुसार सायकल बारindex शोधणे
        time_cycle_idx = min(digit_sum, len(group) - 1)
        
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
                        sl_exit_price = active_trade['entry_price'] if active_trade['is_trailed'] else row['close'] if 'close' in row else row['Close']
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
st.set_page_config(page_title="Time Cycle 1-Year Tester", layout="wide")
st.title("📊 Time Cycle Customizable V27 - 1-Year Pro Backtester")

st.sidebar.header("⚙️ Controls")
ticker = "NIFTY_50.NS" 

# स्लायडर थेट ६० दिवसांपर्यंत (मोफत इंट्राडे डेटा मर्यादा) किंवा महिन्यांचे पर्याय
months_to_test = st.sidebar.slider("मागील किती महिन्यांचा डेटा तपासायचा आहे? (Months)", min_value=1, max_value=12, value=1)
lot_size = 25  

if st.sidebar.button("Fetch NSE Data & Run Backtest"):
    with st.spinner("NSE कडून अधिकृत ऐतिहासिक डेटा सुरक्षितपणे आणत आहे..."):
        end_dt = datetime.now()
        start_dt = end_dt - timedelta(days=months_to_test * 30)
        
        # जर युझरने १ महिन्यापेक्षा जास्त निवडले, तर याहू नियम पाळण्यासाठी ५ मिनिट किंवा डेली डेटा मॅनेज करणे
        interval_choice = "5m" if months_to_test <= 2 else "1d"
        df_data = yf.download(ticker, start=start_dt, end=end_dt, interval=interval_choice)
        
    if not df_data.empty:
        with st.spinner("१ वर्षाचे नियम लागू करत आहे..."):
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
            st.subheader("📜 मागील १ वर्षाची सविस्तर ट्रेड रिपोर्ट डायरी")
            st.dataframe(results_df, use_container_width=True)
            
            csv_data = results_df.to_csv(index=False).encode('utf-8')
            st.download_button("📥 संपूर्ण १ वर्षाचा रिपोर्ट Excel मध्ये डाऊनलोड करा", csv_data, "Time_Cycle_1Year_Report.csv", "text/csv")
        else:
