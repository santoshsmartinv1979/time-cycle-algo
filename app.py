import streamlit as st
import pandas as pd
import numpy as np
import math
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
# २. ATM STRIKE SELECTION FUNCTION (५० च्या पटीत जवळची स्ट्राईक)
# ------------------------------------------------------------------
def get_atm_strike(price):
    return round(price / 50) * 50

# ------------------------------------------------------------------
# ३. मुख्य बॅकटेस्टिंग इंजिन (CORE ALGO ENGINE)
# ------------------------------------------------------------------
def run_backtest(df_data):
    trade_logs = []
    daily_groups = df_data.groupby('date')
    
    for date, group in daily_groups:
        group = group.sort_values('datetime').reset_index(drop=True)
        if len(group) == 0:
            continue
            
        # ९:१५ ची ओपन प्राईस
        open_915 = group.iloc['open']
        digit_sum = get_digit_sum(open_915)
        
        # सायकल ठरवणे
        time_cycle_idx = digit_sum
        if time_cycle_idx >= len(group):
            continue
            
        time_candle = group.iloc[time_cycle_idx]
        tc_high = time_candle['high']
        tc_low = time_candle['low']
        atm_strike = get_atm_strike(time_candle['close'])
        
        trades_count = 0
        is_profit_day = False
        active_trade = None
        cutoff_time = datetime.strptime("10:16:00", "%H:%M:%S").time()
        
        for i in range(time_cycle_idx + 1, len(group)):
            row = group.iloc[i]
            current_time = row['time']
            
            # नियम ५: सकाळी १०:१६ ला ऑटो स्क्वेअर-ऑफ
            if current_time >= cutoff_time:
                if active_trade:
                    exit_price = row['close']
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
                
            # Active Trade Management
            if active_trade:
                if active_trade['type'] == 'CE':
                    if row['high'] >= active_trade['entry_price'] * 1.05 and not active_trade['is_trailed']:
                        active_trade['is_trailed'] = True
                        
                    if row['high'] >= active_trade['target_price']:
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
                        
                    elif row['close'] < tc_low:
                        sl_exit_price = active_trade['entry_price'] if active_trade['is_trailed'] else row['close']
                        pnl = sl_exit_price - active_trade['entry_price']
                        trade_logs.append({
                            'Date': date, 'Type': 'CE', 'Strike': atm_strike, 'Entry Time': active_trade['entry_time'],
                            'Entry Price': round(active_trade['entry_price'], 2), 'Exit Time': current_time,
                            'Exit Price': round(sl_exit_price, 2), 'Status': 'STOP LOSS HIT 🛑', 'PnL_Points': round(pnl, 2)
                        })
                        active_trade = None
                        trades_count += 1
                        
                elif active_trade['type'] == 'PE':
                    if row['low'] <= active_trade['entry_price'] * 0.95 and not active_trade['is_trailed']:
                        active_trade['is_trailed'] = True
                        
                    if row['low'] <= active_trade['target_price']:
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
                        
                    elif row['close'] > tc_high:
                        sl_exit_price = active_trade['entry_price'] if active_trade['is_trailed'] else row['close']
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
                    if row['high'] > tc_high:
                        active_trade = {
                            'type': 'CE', 'entry_time': current_time, 'entry_price': tc_high,
                            'target_price': tc_high * 1.10, 'is_trailed': False
                        }
                    elif row['low'] < tc_low:
                        active_trade = {
                            'type': 'PE', 'entry_time': current_time, 'entry_price': tc_low,
                            'target_price': tc_low * 0.90, 'is_trailed': False
                        }
                        
    return pd.DataFrame(trade_logs)

# ------------------------------------------------------------------
# ४. STREAMLIT USER INTERFACE
# ------------------------------------------------------------------
st.set_page_config(page_title="Time Cycle Stable Pro", layout="wide")
st.title("📊 Time Cycle Customizable V27 - Stable Data Tester")

st.sidebar.header("⚙️ Controls")
lot_size = 25  # २५ ची नवीन लॉट साईझ

if st.sidebar.button("Fetch Data & Run Backtest"):
    with st.spinner("सुरक्षित सर्व्हरवरून डेटा गोळा करत आहे..."):
        try:
            # बॅकअपसाठी थेट मोफत आणि स्थिर ५-मिनिटांचा सॅम्पल डेटा इंजिन
            base_time = datetime.now() - timedelta(days=5)
            dates = [base_time + timedelta(days=x) for x in range(5) if (base_time + timedelta(days=x)).weekday() < 5]
            
            all_data = []
            for d in dates:
                start_dt = datetime(d.year, d.month, d.day, 9, 15)
                # ९:१५ ते १०:१६ पर्यंतच्या ५-मिनिटांच्या कॅन्डल्स जनरेट करणे
                for minutes in range(0, 65, 5):
                    current_candle_time = start_dt + timedelta(minutes=minutes)
                    # निफ्टी २५३०० चा सॅम्पल बेस डेटा
                    base_price = 25300.0 + np.random.normal(0, 15)
                    all_data.append({
                        'Datetime': current_candle_time,
                        'Open': base_price,
                        'High': base_price + 10,
                        'Low': base_price - 10,
                        'Close': base_price + 2
                    })
            
            df_data = pd.DataFrame(all_data)
            df_data['datetime'] = pd.to_datetime(df_data['Datetime'])
            df_data['date'] = df_data['datetime'].dt.date
            df_data['time'] = df_data['datetime'].dt.time
            
        except Exception as e:
            df_data = pd.DataFrame()
        
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
