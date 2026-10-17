import math
from datetime import datetime


def get_diurnal_load_factor(dt: datetime, is_business_district: bool = False) -> float:
    """
    Computes a realistic cellular traffic diurnal activity multiplier [0.12 - 1.0]
    based on the hour of day, weekday/weekend shift, and cell morphology.
    """
    hour_float = dt.hour + (dt.minute / 60.0)
    is_weekend = dt.weekday() in (4, 5)  # Friday/Saturday in Egypt/MENA region or Sat/Sun

    if is_business_district:
        # Commercial / Downtown: High during working hours (08:30 - 18:00), drops sharply at night & weekends
        if is_weekend:
            # Low activity during weekend
            base = 0.20 + 0.15 * math.sin(math.pi * (hour_float - 10) / 12) if 10 <= hour_float <= 22 else 0.15
        else:
            # Dual work peaks: 10:00 and 15:00
            if 8 <= hour_float <= 18:
                base = 0.75 + 0.20 * math.sin(math.pi * (hour_float - 8) / 10)
            elif 18 < hour_float <= 22:
                base = 0.40 - 0.20 * ((hour_float - 18) / 4)
            else:
                base = 0.12
    else:
        # Residential & Suburban: High evening streaming peak (19:30 - 23:30), night lull (02:00 - 06:00)
        if 2 <= hour_float <= 6:
            # Deep night lull
            base = 0.12 + 0.05 * (hour_float - 2) / 4
        elif 7 <= hour_float <= 9:
            # Morning commute surge
            base = 0.45 + 0.20 * (hour_float - 7) / 2
        elif 10 <= hour_float <= 18:
            # Steady daytime baseline
            base = 0.60 + 0.10 * math.sin(math.pi * (hour_float - 10) / 8)
        elif 19 <= hour_float <= 23:
            # Evening prime-time video streaming peak (Peak Hour / Busy Hour)
            base = 0.85 + 0.15 * math.sin(math.pi * (hour_float - 19) / 4)
        else:
            # Transition midnight to 2 AM
            base = 0.40 - 0.25 * (hour_float / 2)

    # Bound factor between 0.10 and 1.0
    return max(0.10, min(1.0, float(base)))
