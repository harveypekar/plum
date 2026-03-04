# Garmin Connect Data Fetcher — Design

## Goal

Fetch ALL available data from Garmin Connect and save it locally. Never discard any fields. Save raw API responses verbatim.

## Output Layout

```
projects/coach/data/garmin/
  .tokens/                    # garth session tokens (gitignored)
  activities/
    list.json                 # all activities, full API response
    {id}/
      summary.json            # get_activity()
      details.json            # get_activity_details()
      splits.json             # get_activity_splits()
      typed_splits.json       # get_activity_typed_splits()
      split_summaries.json    # get_activity_split_summaries()
      hr_zones.json           # get_activity_hr_in_timezones()
      power_zones.json        # get_activity_power_in_timezones()
      weather.json            # get_activity_weather()
      exercise_sets.json      # get_activity_exercise_sets()
      gear.json               # get_activity_gear()
  daily/
    {date}/                   # YYYY-MM-DD
      summary.json            # get_user_summary()
      heart_rates.json        # get_heart_rates()
      stress.json             # get_all_day_stress()
      stress_detail.json      # get_stress_data()
      events.json             # get_all_day_events()
      steps.json              # get_steps_data()
      floors.json             # get_floors()
      sleep.json              # get_sleep_data()
      body_battery.json       # get_body_battery()
      body_battery_events.json # get_body_battery_events()
      rhr.json                # get_rhr_day()
      hrv.json                # get_hrv_data()
      spo2.json               # get_spo2_data()
      respiration.json        # get_respiration_data()
      intensity_minutes.json  # get_intensity_minutes_data()
      training_readiness.json # get_training_readiness()
      training_status.json    # get_training_status()
      endurance_score.json    # get_endurance_score()
      hill_score.json         # get_hill_score()
      max_metrics.json        # get_max_metrics()
      race_predictions.json   # get_race_predictions()
      body_composition.json   # get_body_composition()
      weigh_ins.json          # get_daily_weigh_ins()
      hydration.json          # get_hydration_data()
      lifestyle.json          # get_lifestyle_logging_data()
  weekly/
    {date}/                   # Monday of the week
      steps.json              # get_weekly_steps()
      stress.json             # get_weekly_stress()
      intensity_minutes.json  # get_weekly_intensity_minutes()
  profile/
    user.json                 # get_user_profile()
    settings.json             # get_userprofile_settings()
    full_name.json            # get_full_name()
    units.json                # get_unit_system()
    fitness_age.json          # get_fitnessage_data()
    personal_records.json     # get_personal_record()
    lactate_threshold.json    # get_lactate_threshold()
    cycling_ftp.json          # get_cycling_ftp()
    activity_types.json       # get_activity_types()
  devices/
    list.json                 # get_devices()
    primary.json              # get_primary_training_device()
    last_used.json            # get_device_last_used()
    {device_id}/
      settings.json           # get_device_settings()
      solar.json              # get_device_solar_data()
  gear/
    list.json                 # get_gear()
    defaults.json             # get_gear_defaults()
    {gear_id}/
      stats.json              # get_gear_stats()
      activities.json         # get_gear_activities()
  goals/
    active.json               # get_goals("active")
    future.json               # get_goals("future")
    past.json                 # get_goals("past")
  badges/
    earned.json               # get_earned_badges()
    available.json            # get_available_badges()
    in_progress.json          # get_in_progress_badges()
  challenges/
    adhoc.json                # get_adhoc_challenges()
    badge.json                # get_badge_challenges()
    available_badge.json      # get_available_badge_challenges()
    non_completed_badge.json  # get_non_completed_badge_challenges()
    virtual_in_progress.json  # get_inprogress_virtual_challenges()
  workouts/
    list.json                 # get_workouts()
    {workout_id}.json         # get_workout_by_id()
  blood_pressure/
    all.json                  # get_blood_pressure() full range
  weight/
    all.json                  # get_weigh_ins() full range
  progress/
    summary.json              # get_progress_summary_between_dates()
```

## Script

`projects/coach/fetch_garmin.py` — single file, depends on `garminconnect` (pip).

### Authentication

- Prompt for email/password on first run (never stored to disk)
- Persist OAuth session token to `data/garmin/.tokens/` via garth
- Reuse token on subsequent runs; re-prompt if expired/invalid
- Support MFA prompt if account requires it

### Fetch Strategy

1. **Profile/devices/gear/badges/goals/workouts** — fetched once per run (small, cheap)
2. **Activities list** — `get_activities_by_date()` paginated (100 per page), ALL types (not just running). Save every activity.
3. **Per-activity data** — for each activity, fetch all 9 sub-endpoints (summary, details, splits, typed_splits, split_summaries, hr_zones, power_zones, weather, exercise_sets, gear). 1s sleep between activities.
4. **Daily data** — for each date in range, fetch all 20 daily endpoints. 0.5s sleep between dates.
5. **Weekly data** — for each Monday in range, fetch 3 weekly endpoints.
6. **Range data** — blood pressure, weight, progress summary across full date range.

### Incremental Mode

- On re-run, detect what's already been fetched:
  - Activities: find newest activity date, only fetch newer ones
  - Per-activity sub-files: skip activities that have all 9 files
  - Daily: skip dates that have all daily files
  - Weekly: skip weeks that have all weekly files
- Profile/devices/gear/badges/goals always re-fetched (cheap, may change)
- `--full` flag to force re-fetch everything

### Error Handling

- Auth failure: clear tokens, re-prompt
- Individual endpoint failure: log warning, save nothing for that endpoint, continue
- 429 rate limit: back off exponentially (2s, 4s, 8s...), retry up to 3 times
- Network timeout (30s): retry once, then skip
- Print progress: `[142/856] Fetching activity 12345678 details...`

## Dependencies

- `garminconnect` (uses garth for OAuth internally)
- Python 3.10+

## Future Work (out of scope)

- Mapping Garmin data to Intervals.icu format for analyze.py
- Computing CTL/ATL/TSB from raw data
