# -*- coding: utf-8 -*-
import streamlit as st

# --- 頁面設定 ---
st.set_page_config(
    page_title="微台指：動態加碼模組",
    page_icon="📈",
    layout="wide"
)

def calculate_logic_a_scaling(initial_price, initial_qty, addon_price, addon_qty, stop_loss_risk=100, point_value=10):
    # 初始設定與目標
    initial_target_pts = 3000
    target_price = initial_price - initial_target_pts # 做空的目標價 (例如: 31000)

    # 1. 計算總部位與新均價 (平均成本)
    total_qty = initial_qty + addon_qty
    avg_price = ((initial_price * initial_qty) + (addon_price * addon_qty)) / total_qty

    # 2. 設定保本點與強制停損點
    break_even_price = avg_price 
    # 做空如果遇到大漲需要停損，停損價為均價往上加風險點數
    real_stop_loss = avg_price + stop_loss_risk

    # 3. 邏輯 A 停利點 (維持最初設定的目標價)
    take_profit_price = target_price 
    
    # 4. 預期獲利試算 (做空：均價 - 停利價)
    expected_profit = (avg_price - take_profit_price) * total_qty * point_value

    return {
        "total_qty": total_qty,
        "avg_price": avg_price,
        "stop_loss": break_even_price,
        "real_stop_loss": real_stop_loss,
        "take_profit": take_profit_price,
        "expected_profit": expected_profit
    }

# --- Streamlit 介面呈現 ---
st.title("📈 微台指：動態加碼與風控運算模組 (邏輯 A)")
st.markdown("遵守「有賺不能賠」原則，用帳面獲利加碼，並維持原始目標價讓獲利奔跑。")

# 側邊欄輸入參數
st.sidebar.header("⚙️ 輸入交易參數")
initial_price = st.sidebar.number_input("初始進場價 (做空)", value=34000, step=10)
initial_qty = st.sidebar.number_input("初始口數", value=1, step=1)
addon_price = st.sidebar.number_input("加碼進場價 (做空)", value=33500, step=10)
addon_qty = st.sidebar.number_input("加碼口數", value=1, step=1)

st.sidebar.markdown("---")
st.sidebar.subheader("🛡️ 風控設定")
stop_loss_risk = st.sidebar.number_input("能承受的加碼後風險(點)", value=100, step=10, help="以新均價往上計算的最後防線(停損點)")

st.sidebar.markdown("---")
# 執行運算
if st.sidebar.button("🚀 計算動態停損利", type="primary", use_container_width=True):
    result = calculate_logic_a_scaling(
        initial_price, initial_qty, addon_price, addon_qty, stop_loss_risk=stop_loss_risk
    )
    
    st.subheader("📊 加碼後部位狀態")
    col1, col2 = st.columns(2)
    col1.metric("總曝險口數", f"{result['total_qty']} 口")
    col2.metric("新平均成本 (均價)", f"{result['avg_price']:,.0f} 點")
    
    col3, col4 = st.columns(2)
    col3.metric("保本停損點", f"{result['stop_loss']:,.0f} 點", "獲利歸0即出場", delta_color="off")
    col4.metric("🚨 強制停損價位", f"{result['real_stop_loss']:,.0f} 點", f"虧損 {int(stop_loss_risk)} 點出場", delta_color="inverse")
    
    st.divider()
    
    st.subheader("🎯 邏輯 A 停利目標")
    col4, col5 = st.columns(2)
    col4.metric("最終停利價位 (進攻)", f"{result['take_profit']:,.0f} 點")
    col5.metric("達標預期總獲利", f"NT$ {result['expected_profit']:,.0f}")
    
    st.info(f"💡 **模組指示**：請將你的停損單（Stop Loss）移動至 **{result['stop_loss']:,.0f}**；停利單（Take Profit）掛在 **{result['take_profit']:,.0f}**。")
else:
    st.info("👈 請在左邊設定好條件後，點擊「🚀 計算動態停損利」按鈕。")
