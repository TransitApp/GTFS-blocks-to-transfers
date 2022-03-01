# gtfs-blocks-to-transfers

Converts GTFS blocks, defined by setting [trip.block\_id](https://github.com/google/transit/blob/master/gtfs/spec/en/reference.md#example-blocks-and-service-day) into a series of [trip-to-trip transfers (proposal)](https://github.com/google/transit/pull/303). Uses configurable heuristics  to predict whether two trips are connected as _in-seat transfers_ or as _vehicle continuations_ only. This tool also validates predefined trip-to-trip transfers in `transfers.txt`.

Usage: `./convert.py <input feed> <directory for output>`


## How it works

Throughout this tool, sets of _service days_ are used to relate trips. They are defined in [service\_days.py](#), and are represented as a bitmap per `service_id`, with bit `n` set to 1 if that service operates on the `n`th day since the beginning of the feed. The term _trip's service days_ refers to the service days for `trip.service_id`. If the first departure of a trip is after `24:00:00`, the service days are stored _as-if_ the trip began the next day between `00:00:00` and `23:59:59`.

For each block defined in the feed, [`convert_blocks.py`](#) finds the most likely continuations for each trip, starting the search after the final arrival time of the trip. The program searches for a matching continuation for all of the trip's service days, greedily selecting continuation trips in order of wait time. Some days may remain unmatched if a configurable threshold is exceeded (`config.TripToTripTransfers.max_wait_time`). [`classify_transfers.py`](#) uses heuristics to assign `transfer_type=4` (in-seat transfer) or `transfer_type=5` to each continuation.

Generated transfers are combined with predefined transfers from `transfers.txt` in [`simplify_graph.py`](#). If necessary, this step will split trips such that for any given `from_trip_id`, each of the potential `to_trip_id`, will operate on a disjoint set of service days. For example bus 50 could continue to bus 15 on Monday through Thursday, but continue to bus 20 on Fridays. Both generated and predefined transfers are validated to ensure they are unambiguous and conform to the specification.

[`simplify_export.py`](#) converts the continuation graph back to a series of transfers, resuing the feed's existing `trip_id`s and `service_id`s when an exact match can be found, or creating new entities if required. This step will preserve trip-to-trip transfers that don't represent vehicle continuations (e.g. [`transfer_type=2`](https://github.com/google/transit/blob/master/gtfs/spec/en/reference.md#transferstxt) used to estimate walk time between two vehicles).

## Heuristics

An in-seat transfer is likely if:

* Riders only need to wait a short time between trips.
* The next trip begins at the same stop as the preceding trip ended, or the two stops are very close to each other.
* The next trip goes a different destination than the preceding trip, or the two trips serve a loop route.


Riders probably won't be able to, or want to, to stay on board if:

* The wait time aboard the bus is quite long.
* The next trip is very similar to the preceding trip, but in reverse. We assess similarity by comparing the sequence of stop locations of the two trips using a modified [Hausdorrf metric](https://en.wikipedia.org/wiki/Hausdorff_distance).

You can adjust thresholds or entirely disable a heuristic in [`blocks_to_transfers/config.py`](#).


## Advanced

* `simplify_linear.py`: You probably don't want to enable this option, unless your system happens to have the same constraints described in this section. If enabled, trips will be split so that each trip has at most one incoming continuation, and at most one outgoing continuation. Where cycles exist (e.g. an automated people mover that serves trip 1 -> trip 2 -> trip 1 every day until the end of the feed), back edges are removed. Trips that decouple into multiple vehicles, or that are formed through the coupling of multiple vehicles are preserved as is. 
* Test cases can be found in the `tests/` directory.
