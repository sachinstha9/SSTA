import requests
import datetime as dt

def fetch_forecast(lat, lon, api_key, days=1):
    url = "https://api.weatherapi.com/v1/forecast.json"
    params = {
        "key": api_key,
        "q": f"{lat},{lon}",
        "days": days,
        "aqi": "no",
        "alerts": "no"
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    hourly_all = []
    for day in data['forecast']['forecastday']:
        hourly_all.extend(day['hour'])
    return hourly_all

def estimate_energy(hourly, panel_area, efficiency):
    predicted_kwh_list = []
    for h in hourly:
        cloud_pct = h.get('cloud', 50)   
        precip = h.get('precip_mm', 0) 
        clear_irradiance = 800
        irr = clear_irradiance * (1 - cloud_pct / 100.0) * (1 - min(precip / 10, 1.0))
        energy_kwh = irr * panel_area * efficiency / 1000.0
        predicted_kwh_list.append(energy_kwh)
    total_kwh = sum(predicted_kwh_list)
    return predicted_kwh_list, total_kwh

def get_estimates(lat, lon, api_key=None, days=1, panel_area=1, efficiency=0.7, last_7_days_kwh=[]):
    hourly = fetch_forecast(lat, lon, api_key, days)

    predicted_list, total_kwh = estimate_energy(hourly, panel_area, efficiency)

    for i, val in enumerate(predicted_list):
        hour_time = dt.datetime.strptime(hourly[i]['time'], "%Y-%m-%d %H:%M")
    
    daily_summary = []

    MAX_IRRADIANCE = 800 
    MAX_HOUR_KWH = MAX_IRRADIANCE * panel_area * efficiency / 1000.0
    HIGH_THRESHOLD = 0.7 * MAX_HOUR_KWH
    LOW_THRESHOLD = 0.05

    for day in range(days):
        day_hours = hourly[day*24:(day+1)*24]
        day_predicted = predicted_list[day*24:(day+1)*24]
        
        total_kwh = sum(day_predicted)
        avg_cloud = sum(h.get('cloud', 50) for h in day_hours) / len(day_hours)
        total_precip = sum(h.get('precip_mm', 0) for h in day_hours)
        low_gen_hours = [
            h['time'].split()[-1] for i, h in enumerate(day_hours) if day_predicted[i] < LOW_THRESHOLD
        ]
        high_gen_hours = [
            h['time'].split()[-1] for i, h in enumerate(day_hours) if day_predicted[i] >= HIGH_THRESHOLD
        ]
        
        daily_summary.append({
            "day": day+1,
            "predicted_total_kwh": total_kwh,
            "avg_cloud_pct": avg_cloud,
            "total_precip_mm": total_precip,
            "low_generation_hours": low_gen_hours,
            "high_generation_hours": high_gen_hours
        })

    avg_consumption = sum(last_7_days_kwh) / len(last_7_days_kwh)

    return {
        "daily_average_consumption": avg_consumption,
        "daily_forecast_summary": daily_summary
    }