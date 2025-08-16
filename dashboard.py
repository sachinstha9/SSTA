import gradio as gr
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from geopy.geocoders import Nominatim
from get_solar_estimates import get_estimates
from llm_utils import generate_insights, load_model, answer_user_question

tokenizer, model, device = load_model()
geolocator = Nominatim(user_agent="solar_dashboard_app")

def geocode_location(location_name):
    try:
        location = geolocator.geocode(location_name)
        if location:
            return location.latitude, location.longitude
        else:
            return -36.848461, 174.763336
    except:
        return -36.848461, 174.763336

def chatbot_response(summary, user_message, chat_history):
    if summary is None:
        return [("Bot", "Dashboard not updated yet. Please update first!")], ""
    if chat_history is None:
        chat_history = []
    chat_history.append(("You", user_message))
    bot_reply = answer_user_question(summary, user_message, tokenizer, model, device)
    chat_history.append(("Bot", bot_reply))
    return chat_history, ""

def update_plots(location, forecast_days, panel_area, efficiency, panel_tilt, panel_azimuth):
    """Compute plots and avg consumption quickly, without insights."""
    lat, lon = geocode_location(location)
    summary = get_estimates(
        lat, lon, "055867f3ef224c1a80c73746251608", forecast_days,
        panel_area, efficiency/100,
        [4,3,2,4,5,2,5,3,5,3,4,3,2,4,5,6,2,4,5,6],
        panel_tilt, panel_azimuth
    )

    # Hourly predictions
    predictions = {f"Day {i+1}": e["hourly_predicted_kwh"] for i, e in enumerate(summary["daily_forecast_summary"])}
    hours = list(range(24))
    fig_hourly = go.Figure()
    for day, values in predictions.items():
        fig_hourly.add_trace(go.Scatter(x=hours, y=values, mode='lines+markers', name=day, line=dict(width=2)))
    fig_hourly.update_layout(title="Hourly Predicted Solar Energy (Multiple Days)", xaxis_title="Hour", yaxis_title="Energy (kWh)", template="plotly_white")

    # Daily totals
    daily_totals = {f"Day {i+1}": e["predicted_total_kwh"] for i, e in enumerate(summary["daily_forecast_summary"])}
    df_totals = pd.DataFrame({"Day": list(daily_totals.keys()), "Total kWh": list(daily_totals.values())})
    fig_daily = px.bar(df_totals, x="Day", y="Total kWh", title="Total Daily Energy Prediction")
    avg_consumption = summary.get("daily_average_consumption", 0)

    return fig_hourly, fig_daily, avg_consumption, summary

def generate_insights_async(summary):
    """Compute LLM insights separately."""
    return generate_insights(summary, tokenizer, model, device)

# Gradio UI
with gr.Blocks() as demo:
    gr.Markdown("## 🌞 Solar Energy Forecast Dashboard")

    with gr.Row():
        with gr.Column(scale=3):
            location_input = gr.Textbox(label="Location", value="Auckland")
            forecast_days_input = gr.Slider(1, 7, value=3, step=1, label="Days to forecast")
            panel_area_input = gr.Number(value=1.0, label="Panel Area (m2)")
            efficiency_input = gr.Number(value=17, label="Efficiency (%)")
            panel_tilt_input = gr.Number(value=45.0, label="Panel Tilt (degree)")
            panel_azimuth_input = gr.Number(value=0.0, label="Panel Azimuth (degree)")
            
            update_btn = gr.Button("Update Dashboard")

        with gr.Column(scale=5):
            hourly_plot = gr.Plot(label="Hourly Predicted Solar Energy")
            daily_plot = gr.Plot(label="Total Daily Energy Prediction")
            avg_metric = gr.Number(label="Average of past 7 days")
            insights_box = gr.Textbox(label="Forecast Insights", interactive=False)
            summary_state = gr.State()  # store summary for chatbot

    # Step 1: Update plots immediately
    def update_dashboard_fast(location, forecast_days, panel_area, efficiency, panel_tilt, panel_azimuth):
        fig_h, fig_d, avg, summary = update_plots(location, forecast_days, panel_area, efficiency, panel_tilt, panel_azimuth)
        return fig_h, fig_d, avg, "", summary  # empty insights initially

    update_btn.click(
        update_dashboard_fast,
        inputs=[location_input, forecast_days_input, panel_area_input, efficiency_input, panel_tilt_input, panel_azimuth_input],
        outputs=[hourly_plot, daily_plot, avg_metric, insights_box, summary_state]
    )

    # Step 2: Update insights asynchronously
    def load_insights(summary):
        if summary is None:
            return "No summary available."
        return generate_insights_async(summary)

    summary_state.change(load_insights, inputs=[summary_state], outputs=[insights_box])

    # Chatbot
    # Chatbot UI
    gr.Markdown("## Chatbot")
    chatbot = gr.Chatbot(label="Chatbot")
    msg = gr.Textbox(label="Type your message")
    msg.submit(chatbot_response, inputs=[summary_state, msg, chatbot], outputs=[chatbot, msg])

demo.launch(share=True)
