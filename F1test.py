import fastf1
fastf1.Cache.enable_cache("cache/")

session = fastf1.get_session(2024, "Bahrain", "R")
session.load()
laps = session.laps
print(laps[["Driver", "Compound", "TyreLife", "LapTime"]].head(20))