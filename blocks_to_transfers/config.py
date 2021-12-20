config = {
    # Limits to be detected as transfer_type=5 (vehicle continues; passenger may not remain on board)
    'vehicle_cont': {
        'max_wait_time_in_seconds': 900,
        'max_distance_between_end_stops_in_meters': 1000,
        'max_similarity_between_shapes_in_percent': 80,
        'max_distance_between_inner_stops': 100
    }
}