This test case illustrates a situation where the old `block_id` format
implicitly requires us to select a trip on only some of its days of service. 

In this scenario, `trip_1` is followed by a short trip named `loop` on Fridays 
and Saturdays. On Monday through Saturday,  `trip_3` begins 19 minutes after 
the end of `trip_1`.

This requires the splitting of trips even with output in the standard form:

* Mon-Thu: 1 - [Variant of 3 with only Mon-Thu]
* Fri-Sat: 1 - loop - [Variant of 3 with only Fri-Sat]


With linear simplification, this becomes:

* Mon-Thu: [Variant of 1 with only Mon-Thu] - [Variant of 3 with only Mon-Thu]
* Fri-Sat: [Variant of 1 with only Fri-Sat] - loop - [Variant of 3 with only Fri-Sat]
