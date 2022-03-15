This example tests a 'classic' trip continuation case, where one route 'becomes' another route in the middle of the run. This is the case in cities like Seattle, between routes like the 1 and 14 or the 24/33 and 124. It additionally tests that existing transfers of other types are not overwritten.

The converter should detect that the order is 1-2 and 3-4, and both continuations should be in-seat. The converter should also copy over existing transfers of other types.
