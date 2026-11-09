-- Opening hours per weekday. Keys "1".."7" (1 = Monday, ISO weekday), value {"open": "HH:MM", "close": "HH:MM"}
-- or null = day off. close earlier than open = past midnight; open = close = the whole day. Column null = open all day.
-- ponytail: no CHECK on the shape; PATCH /sellers/me/hours validates and a malformed day is read as a day off
-- (core/store_hours.py). Add a CHECK if another writer appears. One slot per day; two slots = a list per day later.
-- opening_time / closing_time stay for now (dropping them = later, once no deployed admin build writes them);
-- the app and admin no longer read them.
alter table public.seller_profiles add column if not exists weekly_hours jsonb;

-- Same daily hours on all 7 days. Equal times meant 24 hours, i.e. all day = null, like no hours.
update public.seller_profiles
set weekly_hours = (
  select jsonb_object_agg(d::text, jsonb_build_object('open', to_char(opening_time, 'HH24:MI'),
                                                      'close', to_char(closing_time, 'HH24:MI')))
  from generate_series(1, 7) d
)
where weekly_hours is null
  and opening_time is not null and closing_time is not null
  and opening_time <> closing_time;
