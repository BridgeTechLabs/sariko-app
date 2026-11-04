"""Go-live switch: admin_settings app_live (0 = buyer pages show "coming soon", 1 = live, open for sales)
and launch_date (YYYYMMDD, Vietnam date, only shown on that page; reaching it does not go live)."""

NO_DATE = 99991231  # launch_date: hide the date line


def launch_status(app_live: int, launch_date: int) -> dict:
    """{prelaunch, launch_date as YYYY-MM-DD or None}: only app_live decides the redirect."""
    shown = None if launch_date == NO_DATE else f"{launch_date // 10000:04d}-{launch_date // 100 % 100:02d}-{launch_date % 100:02d}"
    return {"prelaunch": app_live == 0, "launch_date": shown}
