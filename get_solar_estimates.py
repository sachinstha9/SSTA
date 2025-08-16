import math
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

def day_of_year(dt_obj):
    return dt_obj.timetuple().tm_yday

def declination_angle(n):
    return math.radians(23.45) * math.sin(2 * math.pi * (284 + n) / 365.0)

def equation_of_time_correction(n):
    B = 2 * math.pi * (n - 81) / 364.0
    return 9.87 * math.sin(2 * B) - 7.53 * math.cos(B) - 1.5 * math.sin(B)

def solar_time(local_dt, longitude, tz_offset_hours):
    n = day_of_year(local_dt)
    local_decimal_hour = local_dt.hour + local_dt.minute / 60.0 + local_dt.second / 3600.0
    eot = equation_of_time_correction(n)
    time_correction = 4 * (longitude - (tz_offset_hours * 15.0)) + eot
    solar_time_decimal = local_decimal_hour + time_correction / 60.0
    return solar_time_decimal

def hour_angle_from_solar_time(solar_time_decimal):
    return math.radians(15 * (solar_time_decimal - 12.0))

def solar_zenith_azimuth(lat_deg, lon_deg, timestamp_local, tz_offset_hours):
    n = day_of_year(timestamp_local)
    delta = declination_angle(n)  # radians
    solar_t = solar_time(timestamp_local, lon_deg, tz_offset_hours)
    h_angle = hour_angle_from_solar_time(solar_t)

    lat = math.radians(lat_deg)

    cos_zenith = math.sin(lat) * math.sin(delta) + math.cos(lat) * math.cos(delta) * math.cos(h_angle)
    cos_zenith = max(-1.0, min(1.0, cos_zenith))
    zenith = math.acos(cos_zenith)

    sin_az = (math.cos(delta) * math.sin(h_angle)) / math.sin(zenith) if math.sin(zenith) != 0 else 0.0
    cos_az = (math.sin(delta) - math.sin(lat) * math.cos(zenith)) / (math.cos(lat) * math.sin(zenith)) if math.sin(zenith) != 0 else 0.0
    azimuth = math.atan2(sin_az, cos_az)  

    if azimuth < 0:
        azimuth += 2 * math.pi

    return zenith, azimuth

def incidence_angle(zenith_rad, solar_az_rad, panel_tilt_deg, panel_azimuth_deg):
    beta = math.radians(panel_tilt_deg)
    gamma_p = math.radians(panel_azimuth_deg)
    cos_theta = math.cos(zenith_rad) * math.cos(beta) + math.sin(zenith_rad) * math.sin(beta) * math.cos(solar_az_rad - gamma_p)
    cos_theta = max(-1.0, min(1.0, cos_theta))
    return math.acos(cos_theta), cos_theta  

def estimate_energy(hourly, panel_area, efficiency, lat, lon, tz_offset_hours=12, panel_tilt=30, panel_azimuth=180):
    predicted_kwh_list = []
    for h in hourly:
        cloud_pct = h.get('cloud', 50)
        precip = h.get('precip_mm', 0)
        clear_irradiance = 800.0

        ghi_approx = clear_irradiance * max(0.0, (1.0 - cloud_pct / 100.0)) * (1 - min(precip / 10.0, 1.0))

        ts = dt.datetime.strptime(h['time'], "%Y-%m-%d %H:%M")
        zenith, solar_az = solar_zenith_azimuth(lat, lon, ts, tz_offset_hours)

        if zenith >= math.radians(90):
            poa_irradiance = 0.0
        else:
            inc_angle_rad, cos_inc = incidence_angle(zenith, solar_az, panel_tilt, panel_azimuth)
            direct_component = max(0.0, cos_inc) * ghi_approx
            diffuse_fraction = 0.1 + 0.4 * (cloud_pct / 100.0)  
            diffuse_component = ghi_approx * diffuse_fraction * (1 + math.cos(math.radians(panel_tilt))) / 2.0
            poa_irradiance = direct_component + diffuse_component

        energy_kwh = poa_irradiance * panel_area * efficiency / 1000.0
        predicted_kwh_list.append(energy_kwh)

    total_kwh = sum(predicted_kwh_list)
    return predicted_kwh_list, total_kwh

def get_estimates(lat, lon, api_key=None, days=1, panel_area=1.0, efficiency=0.7, last_7_days_kwh=None, panel_tilt=30, panel_azimuth=180, tz_offset_hours=12):
    if last_7_days_kwh is None:
        last_7_days_kwh = []

    hourly = fetch_forecast(lat, lon, api_key, days)
    predicted_list, total_kwh = estimate_energy(hourly, panel_area, efficiency, lat, lon, tz_offset_hours, panel_tilt, panel_azimuth)

    daily_summary = []

    MAX_IRRADIANCE = 1000.0 
    MAX_HOUR_KWH = MAX_IRRADIANCE * panel_area * efficiency / 1000.0
    HIGH_THRESHOLD = 0.7 * MAX_HOUR_KWH
    LOW_THRESHOLD = 0.05

    for day in range(days):
        day_hours = hourly[day*24:(day+1)*24]
        day_predicted = predicted_list[day*24:(day+1)*24]
        total_day_kwh = sum(day_predicted)
        avg_cloud = sum(h.get('cloud', 50) for h in day_hours) / len(day_hours) if len(day_hours) else 0
        total_precip = sum(h.get('precip_mm', 0) for h in day_hours)
        low_gen_hours = [
            h['time'].split()[-1] for i, h in enumerate(day_hours) if day_predicted[i] < LOW_THRESHOLD
        ]
        high_gen_hours = [
            h['time'].split()[-1] for i, h in enumerate(day_hours) if day_predicted[i] >= HIGH_THRESHOLD
        ]

        daily_summary.append({
            "day": day+1,
            "predicted_total_kwh": total_day_kwh,
            "avg_cloud_pct": avg_cloud,
            "total_precip_mm": total_precip,
            "low_generation_hours": low_gen_hours,
            "high_generation_hours": high_gen_hours,
            "hourly_predicted_kwh": day_predicted
        })

    avg_consumption = sum(last_7_days_kwh) / len(last_7_days_kwh) if last_7_days_kwh else 0.0

    return {
        "daily_average_consumption": avg_consumption,
        "daily_forecast_summary": daily_summary
    }

# estimates = get_estimates( -36.8485, 174.7633, api_key="055867f3ef224c1a80c73746251608", days=1,
#                           panel_area=6.5, efficiency=0.18, last_7_days_kwh=[4.1,3.9], panel_tilt=30, panel_azimuth=180, tz_offset_hours=12)
# print(estimates)