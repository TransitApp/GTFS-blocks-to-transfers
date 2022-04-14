This example tests the Hausdorff metric to make sure that similar trips (but not identical trips) are still modeled as in-seat continuations. This particular example is route 125 from King County Metro in Seattle, Washington, which in the GTFS is modelled peculiarly. The inbound trip is cut off halfway to downtown, and the outbound trip is modelled as the last half of the inbound trip, plus the outbound trip. The agency models a continuation between the half-inbound trip and the 'the rest' trip. There is enough difference between these two trips that the Hausdorff metric should _not_ model these as too similar for in-seat continuation.

The converter should detect that the order is 1-2, and that the continuation is in-seat.