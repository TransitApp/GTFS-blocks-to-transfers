from math import *
# NIST Percentile estimation: https://www.itl.nist.gov/div898/handbook/prc/section2/prc262.htm




def hausdorff(shape_a, shape_b):
    return max(directed_hausdorff(shape_a, shape_b), directed_hausdorff(shape_b, shape_a))


def directed_hausdorff(shape_a, shape_b):
    d_max_min = 0

    for a in shape_a:
        d_nearest_segment = inf


        for i_b in range(len(shape_b) - 1):
            d_ab = a.dist_to_segment(shape_b[i_b], shape_b[i_b + 1])
            if d_ab < d_nearest_segment:
                d_nearest_segment = d_ab
                #nearest_segment = (shape_b[i_b].geojson(), shape_b[i_b + 1].geojson())

        if d_nearest_segment > d_max_min:
            d_max_min = d_nearest_segment
            #furthest_pair = (a.geojson(), nearest_segment)

    #print(furthest_pair[0], furthest_pair[1][0], furthest_pair[1][1], d_max_min)
    return d_max_min


class LatLon:
    # Sources:
    # http://www.movable-type.co.uk/scripts/gis-faq-5.1.html
    # http://www.movable-type.co.uk/scripts/latlong.html
    EARTH_RADIUS_M = 6_371_009.0

    def __init__(self, lat, lon, unit=degrees):
        self.lat = radians(lat) if unit == degrees else lat
        self.lon = radians(lon) if unit == degrees else lon

    def geojson(self):
        return f'[{degrees(self.lon)}, {degrees(self.lat)}]'

    def __repr__(self):
        return repr((degrees(self.lat), degrees(self.lon)))

    def angular_dist_to(self, other):
        d_lat = other.lat - self.lat
        d_lon = other.lon - self.lon
        a = sin(d_lat / 2)**2 + cos(self.lat) * cos(other.lat) * sin(d_lon / 2)**2
        return 2 * asin(sqrt(a))

    def dist_to(self, other):
        return LatLon.EARTH_RADIUS_M * self.angular_dist_to(other)

    def bearing_to(self, other):
        y = sin(other.lon - self.lon) * cos(other.lat)
        x = cos(self.lat) * sin(other.lat) - sin(self.lat) * cos(other.lat) * cos(other.lon - self.lon)
        return atan2(y, x)

    def add_bearing_and_angular_dist(self, bearing, dist):
        lat = asin(sin(self.lat)*cos(dist) + cos(self.lat)*sin(dist)*cos(bearing))
        lon = self.lon \
              + atan2(sin(bearing)*sin(dist)*cos(self.lat), cos(dist) - sin(self.lat)*sin(lat))

        return LatLon(lat, lon, unit=radians)

    def dist_to_segment(x, l1, l2):
        """
                     x
                     |
                     |
        l1 ---------lx------------ l2
        """

        d_l1_x, t_l1_x = l1.angular_dist_to(x), l1.bearing_to(x)
        d_l1_l2, t_l1_l2 = l1.angular_dist_to(l2), l1.bearing_to(l2)
        d_l2_x = l2.angular_dist_to(x)

        d_cross = asin(sin(d_l1_x) * sin(t_l1_x - t_l1_l2))
        d_along = acos(cos(d_l1_x)/cos(d_cross))

        lx = l1.add_bearing_and_angular_dist(t_l1_l2, d_along)
        d_lx_x = lx.angular_dist_to(x)

        if d_along < d_l1_l2 and d_lx_x < d_l1_x and d_lx_x < d_l2_x:
            # closest point is somewhere along l1-l2 as in the above figure
            return LatLon.EARTH_RADIUS_M * d_lx_x
        else:
            # closest point is l1, l2 depending on which end is nearer to x
            return LatLon.EARTH_RADIUS_M * min(d_l1_x, d_l2_x)