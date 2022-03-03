This example uses the trip-to-trip transfers specification to create a cyclic 
block, where the last trip of day n continues to the first trip of day n+1, 
until the feed's end. This case isn't plausible, but could perhaps be used for
an automated people mover.

The program removes the back edge from `cycle_4` back to `cycle_1`, removing
the cycle while preserving the order as much as possible.
