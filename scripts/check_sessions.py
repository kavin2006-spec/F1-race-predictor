import fastf1

fastf1.Cache.enable_cache("cache/")

# Test one 2024 and one 2025 round qualifying session
test_cases = [
    (2024, 1, "Q"),
    (2024, 1, "SQ"),  # Sprint Qualifying (renamed in 2024)
    (2024, 5, "S"),   # Sprint race
    (2025, 1, "Q"),
    (2025, 1, "SQ"),
]

for year, round_num, session_type in test_cases:
    try:
        session = fastf1.get_session(year, round_num, session_type)
        session.load(telemetry=False, weather=False, messages=False)
        print(f"OK     {year} round {round_num} '{session_type}' "
              f"— {len(session.results)} drivers")
    except Exception as e:
        print(f"FAILED {year} round {round_num} '{session_type}' — {e}")