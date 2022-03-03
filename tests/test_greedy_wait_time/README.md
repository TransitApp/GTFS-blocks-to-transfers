In this test `trip_1` and `trip_3` are part of the same block, but on Fridays,
 a short trip named `trip_2` runs in between the two trips. Trips are selected
so as to minimize rider wait time, giving rise to three cases.

* Mon-Thu: 1 -> [Variant form of 3 that excludes Fridays]
* Fri: 1 -> 2 -> [Variant form of 3 running only on Fridays]

Two variants of `trip_3` must be created so that consumers always know which
trip follows `trip_1` on a particular day of the week. 
