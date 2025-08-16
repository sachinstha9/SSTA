# dashboard.py
import streamlit as st
import pandas as pd
import plotly.express as px
from get_solar_estimates import get_estimates
from llm_utils import load_model, generate_explanation, answer_user_question
import plotly.graph_objects as go

st.set_page_config(page_title="Solar Energy Forecast Dashboard", layout="wide")
st.title("🌞 Solar Energy Forecast Dashboard")

st.sidebar.header("Configuration")

with st.sidebar:
    location = st.text_input("Location", value="Auckland")
    forecast_days = st.number_input("Days to forecast (max 7 days)", min_value=1, max_value=7, value=3)
    panel_area = st.number_input("Panel Area (m2)", min_value=0.0, value=1.0, step=0.1)
    efficiency = st.number_input("Efficiency (%)", min_value=0, value=17)
    panel_tilt = st.number_input("Panel Tilt (degree)", min_value=0.0, max_value=90.0, value=45.0, step=0.1)
    panel_azimuth = st.number_input("Panel Azimuth (degree)", min_value=0.0, max_value=360.0, value=0.0, step=0.1)


summary_for_llm = get_estimates(-36.848461, 174.763336, "055867f3ef224c1a80c73746251608", 2, 5, 0.15, [4,3,2,4,5,2,5,3,5,3,4,3,2,4,5,6,2,4,5,6], 45, 0)

df = pd.DataFrame({
    "Hour": list(range(24)),
    "Predicted kWh": summary_for_llm["daily_forecast_summary"][0]["hourly_predicted_kwh"]
})

predictions = {}
for i, e in enumerate(summary_for_llm["daily_forecast_summary"]):
    predictions["Day " + str(i + 1)] = e["hourly_predicted_kwh"]

hours = list(range(24))
fig = go.Figure()

for day, values in predictions.items():
    fig.add_trace(go.Scatter(
        x=hours,
        y=values,
        mode='lines+markers',
        name=day,
        line=dict(width=2),
        hoverinfo='name+x+y',  
        opacity=0.8 
    ))

for trace in fig.data:
    trace.hoverlabel = dict(bgcolor="yellow", font_size=14, font_family="Arial")

# Layout
fig.update_layout(
    title="Hourly Predicted Solar Energy (Multiple Days)",
    xaxis_title="Hour",
    yaxis_title="Energy (kWh)",
    xaxis=dict(tickmode='linear'),
    hovermode="x unified", 
    template="plotly_white"
)
fig.update_layout(title=dict(
    text="Hourly Predicted Solar Energy (Multiple Days)", 
    font=dict(size=20)                    
))

col1, col2 = st.columns([5, 2],  gap="large")

with col1:
    st.plotly_chart(fig, use_container_width=True)


daily_totals = {}
for i, e in enumerate(summary_for_llm["daily_forecast_summary"]):
    daily_totals["Day " + str(i + 1)] = e["predicted_total_kwh"]
df = pd.DataFrame({
    "Day": list(daily_totals.keys()),
    "Total kWh": list(daily_totals.values())
})
fig = px.bar(df, x="Day", y="Total kWh", title="Total Daily Energy Prediction")
fig.update_traces(marker_line_width=0, marker_line_color="black", width=0.3)  
fig.update_layout(height=400)
fig.update_yaxes(dtick=0.2)
fig.update_layout(title=dict(
    text="Total Daily Energy Prediction", 
    font=dict(size=20)                    
))

with col2:
    st.metric(label="Average of past 7 days", value=f"{summary_for_llm["daily_average_consumption"]} kWh")
    st.plotly_chart(fig, use_container_width=True)