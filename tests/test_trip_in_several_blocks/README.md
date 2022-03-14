This example comes from the GTFS specification: 
<https://github.com/google/transit/blob/master/gtfs/spec/en/reference.md#example-blocks-and-service-day>

The converter detects that the implied order of the trips is 4-5-1-2-3. 

## Standard simplification

For each transfer, consumers must check that both `from_trip` and `to_trip`
are in operation on a particular day. The following cases result:

* Mon-Thu: 4-5-1
* Fri-Sat: 1-2-3
* Sun: 1-2

## Linear simplification

The converter detects the implied order of the trips, and duplicates trips
whose continuation varies based on the day of the week, so that `from_trip` and
`to_trip` are in a 1:1 relation that is always applicable.


* Mon-Thu: 4-5-[Variant of 1 for Mon-Thu]
* Fri-Sat: [Variant of 1 for Fri-Sat]-[Variant of 2 for Fri-Sat]-3
* Sun: [Variant of 1 for Sun]-[Variant of 2 for Sun]
