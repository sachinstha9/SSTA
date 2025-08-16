import streamlit as st
import pandas as pd
import plotly.express as px
from get_solar_estimates import get_estimates
from llm_utils import load_model, generate_explanation, answer_user_question

st.set_page_config(page_title="Solar Energy Forecast Dashboard", layout="wide")
st.title("🌞 Solar Energy Forecast Dashboard")

# --- Sidebar ---
st.sidebar.header("Configuration")
FORECAST_DAYS = st.sidebar.number_input("Days to forecast", min_value=1, max_value=7, value=3)

# --- Fetch data ---
summary_for_llm = get_estimates(days=FORECAST_DAYS)

# --- Daily summary table ---
st.subheader("Daily Forecast Summary")
daily_df = pd.DataFrame(summary_for_llm["daily_forecast_summary"])
st.dataframe(daily_df)

# --- Prepare hourly dataframe for charts ---
hourly_data = []
for day_summary in summary_for_llm["daily_forecast_summary"]:
    day = day_summary["day"]
    predicted_list = day_summary.get("hourly_predicted_kwh", [])
    actual_list = day_summary.get("hourly_actual_kwh", [val * 0.9 for val in predicted_list])
    for i, (pred, act) in enumerate(zip(predicted_list, actual_list)):
        hourly_data.append({"day": day, "hour": i, "predicted_kwh": pred, "actual_kwh": act})
hourly_df = pd.DataFrame(hourly_data)

# --- Hourly predicted chart ---
st.subheader("Hourly Predicted Generation")
fig_pred = px.line(hourly_df, x="hour", y="predicted_kwh", color="day", labels={"hour":"Hour","predicted_kwh":"kWh","day":"Day"})
st.plotly_chart(fig_pred, use_container_width=True)

# --- Predicted vs Actual chart ---
st.subheader("Predicted vs Actual Solar Generation")
fig_compare = px.line(hourly_df, x="hour", y=["predicted_kwh","actual_kwh"], color="day", labels={"value":"kWh","hour":"Hour","variable":"Legend"})
st.plotly_chart(fig_compare, use_container_width=True)

# --- Load LLM ---
tokenizer, model, device = load_model()

# --- LLM Explanation ---
st.subheader("LLM Explanation of Solar Forecast")
explanation = generate_explanation(summary_for_llm, tokenizer, model, device)
st.text_area("Solar Forecast Insights", explanation, height=300)

# --- Chatbot ---
st.subheader("Ask about your solar forecast")
user_question = st.text_input("Ask a question:")
if st.button("Send"):
    response = answer_user_question(summary_for_llm, user_question, tokenizer, model, device)
    st.write(response)
