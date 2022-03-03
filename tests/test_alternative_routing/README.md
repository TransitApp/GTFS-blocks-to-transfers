In this example, alternative routing is used depending on the day of the week.

- For example, `trip_1_route_99` is usually followed by `trip_2_route_3` while 
  school is in session, but on Saturdays, instead the bus immediately returns 
  along route 99 on `trip_2_route_99`.
- `trip_3_route_3` usually continues to `trip_4_route_1` but on some holidays,
  it continues to `trip_5_route_1_short_run`.
