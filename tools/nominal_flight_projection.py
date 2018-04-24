import pandas as pd
import numpy as np
import math
from pymongo import MongoClient

cl = MongoClient()
db = cl['flights']
col = db['adsb_flights']


def find_coord_dst_hdg(coord1, hdg, dst):
    # https://stackoverflow.com/questions/7222382/get-lat-long-given-current-point-distance-and-bearing

    R = 6378.1  # Radius of the Earth in km
    hdg = math.radians(hdg)  # Bearing is converted to radians.
    d = dst / 1000  # Distance in km

    lat1 = math.radians(coord1[0])  # Current lat point converted to radians
    lon1 = math.radians(coord1[1])  # Current long point converted to radians

    lat2 = math.asin(math.sin(lat1) * math.cos(d / R) +
                     math.cos(lat1) * math.sin(d / R) * math.cos(hdg))

    x = math.sin(hdg) * math.sin(d / R) * math.cos(lat1)
    y = math.cos(d / R) - math.sin(lat1) * math.sin(lat2)

    lon2 = lon1 + math.atan2(y, x)

    lat2 = math.degrees(lat2)
    lon2 = math.degrees(lon2)

    return (lat2, lon2)


def nominal_proj(fl_df, look_ahead_t=600):
    proj_coord_lat = []
    proj_coord_lon = []

    for i, r in fl_df.iterrows():
        if i < 3:
            coord_start = (r['lat'], r['lon'])
            hdg_start = r['hdg']
            spd_start = r['spd']
            ts_start = r['ts']
            proj_coord_lat.extend([np.nan])
            proj_coord_lon.extend([np.nan])
        else:
            if (r['ts'] - ts_start) < look_ahead_t:
                dst_start = (r['ts'] - ts_start) * (spd_start * 0.514444)
                crd = find_coord_dst_hdg(coord_start, hdg_start, dst_start)
                proj_coord_lat.extend([crd[0]])
                proj_coord_lon.extend([crd[1]])
            else:
                proj_coord_lat.extend([np.nan])
                proj_coord_lon.extend([np.nan])

    fl_df['proj_lat'] = proj_coord_lat
    fl_df['proj_lon'] = proj_coord_lon

    return fl_df


def nominal_proj_avg(fl_df, look_ahead_t=600, hdg_start_nr=5):
    proj_coord_lat = []
    proj_coord_lon = []

    coord_start = (fl_df['lat'].iloc[hdg_start_nr], fl_df['lon'].iloc[hdg_start_nr])
    hdg_avg_start = fl_df['hdg'].iloc[list(range(0, hdg_start_nr))].mean()
    spd_avg_start = fl_df['spd'].iloc[list(range(0, hdg_start_nr))].mean()
    ts_start = fl_df['ts'].iloc[hdg_start_nr]
    fl_df['proj_lat'] = np.nan
    fl_df['proj_lon'] = np.nan

    for i in range(hdg_start_nr, len(fl_df)):
        if (fl_df['ts'].iloc[i] - ts_start) < look_ahead_t:
            dst_start = (fl_df['ts'].iloc[i] - ts_start) * (spd_avg_start * 0.514444)
            crd = find_coord_dst_hdg(coord_start, hdg_avg_start, dst_start)
            proj_coord_lat.extend([crd[0]])
            proj_coord_lon.extend([crd[1]])
        else:
            proj_coord_lat.extend([np.nan])
            proj_coord_lon.extend([np.nan])

    fl_df['proj_lat'].iloc[range(hdg_start_nr, len(fl_df))] = proj_coord_lat
    fl_df['proj_lon'].iloc[range(hdg_start_nr, len(fl_df))] = proj_coord_lon

    return fl_df


def calc_coord_dst(c1, c2):
    R = 6371.1 * 1000  # Radius of the Earth in m

    lat1 = c1[0]
    lon1 = c1[1]
    lat2 = c2[0]
    lon2 = c2[1]

    [lon1, lat1, lon2, lat2] = [math.radians(l) for l in [lon1, lat1, lon2, lat2]]

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    d = R * c
    return d


def calc_coord_dst_simple(c1, c2):
    R = 6371.1 * 1000  # Radius of the Earth in m

    lon1 = c1[0]
    lat1 = c1[1]
    lon2 = c2[0]
    lat2 = c2[1]

    [lon1, lat1, lon2, lat2] = [math.radians(l) for l in [lon1, lat1, lon2, lat2]]

    dlon = lon2 - lon1
    dlat = lat2 - lat1

    x = dlon * math.cos(dlat / 2)
    y = dlat
    d = math.sqrt(x * x + y * y) * R

    return d


def calc_bearing(c0, c1):
    if not all(isinstance(i, tuple) for i in [c0, c1]):
        return np.nan

    lat1 = c0[0]
    lon1 = c0[1]
    lat2 = c1[0]
    lon2 = c1[1]

    [lon1, lat1, lon2, lat2] = [math.radians(l) for l in [lon1, lat1, lon2, lat2]]

    dlon = lon2 - lon1

    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    y = math.sin(dlon) * math.cos(lat2)
    bearing = math.atan2(y, x)

    return math.degrees(bearing)


def calc_compass_bearing(c0, c1):
    if not all(isinstance(i, tuple) for i in [c0, c1]):
        return np.nan

    lat1 = c0[0]
    lon1 = c0[1]
    lat2 = c1[0]
    lon2 = c1[1]

    [lon1, lat1, lon2, lat2] = [math.radians(l) for l in [lon1, lat1, lon2, lat2]]

    dlon = lon2 - lon1

    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    y = math.sin(dlon) * math.cos(lat2)
    bearing = math.atan2(y, x)

    return (math.degrees(bearing) + 360) % 360


def get_triangle_corner(d0, d1, d2):
    bb = (d0 ** 2 + d1 ** 2 - d2 ** 2) / (2 * d0 * d1)
    return math.acos(bb)


def convert_knts_ms(spd):
    return spd*0.51444


def calc_track_errors(wp_0, wp_ac, speed_wp0, hdg_wp0, t_wp0, t_ac, wp_1=None):
    assert all(isinstance(i, tuple) for i in [wp_0, wp_ac]), "Coordinate entries are not tuples"
    td = t_ac - t_wp0

    if wp_1:
        assert isinstance(wp_1, tuple), "Coordinate entries are not tuples"
        lat1 = wp_0[0]
        lon1 = wp_0[1]
        lat2 = wp_1[0]
        lon2 = wp_1[1]
        hdg_wp0 = calc_bearing(lat1, lon1, lat2, lon2)

    dst_proj = td * convert_knts_ms(speed_wp0)
    wp_proj = find_coord_dst_hdg(wp_0, hdg_wp0, dst_proj)
    dst_ac = calc_coord_dst_simple(wp_0, wp_ac)
    dst_wp_proj = calc_coord_dst_simple(wp_0, wp_proj)
    dst_proj_ac = calc_coord_dst_simple(wp_ac, wp_proj)

    hdg_wp0_wpproj = calc_bearing(wp_0, wp_proj)
    hdg_wp0_wpac = calc_bearing(wp_0, wp_ac)

    alpha_2 = get_triangle_corner(dst_ac, dst_wp_proj, dst_proj_ac)

    if hdg_wp0_wpproj - hdg_wp0_wpac < 0:
        alpha_2 = -1*alpha_2

    cte = math.sin(alpha_2) * dst_ac
    tte = dst_proj_ac
    ate = math.sqrt(tte ** 2 - cte ** 2)

    if dst_ac < dst_proj:
        ate = -1*ate

    return cte, ate, tte


def create_projection_dict(fl_dd):

    fl_dd = fl_dd[fl_dd['hdg'].first_valid_index():]
    fl_dd = fl_dd.reset_index(drop=True)

    fl_dd = fl_dd.iloc[fl_dd.first_valid_index():]

    if len(fl_dd) == 0:
        return None

    wp_0 = (fl_dd['lat'][0], fl_dd['lon'][0])
    speed_wp0 = fl_dd['spd'][0]
    hdg_wp0 = fl_dd['hdg'][0]
    t_wp0 = fl_dd['ts'][0]

    cte_arr = []
    ate_arr = []
    tte_arr = []

    for ii, r in fl_dd.iterrows():
        if ii != 0:
            wp_ac = (r['lat'], r['lon'])
            t_ac = r['ts']

            cte, ate, tte = calc_track_errors(wp_0, wp_ac, speed_wp0,
                                              hdg_wp0, t_wp0, t_ac, wp_1=None)
            cte_arr.append(cte)
            ate_arr.append(ate)
            tte_arr.append(tte)
        else:
            cte_arr.append(0)
            ate_arr.append(0)
            tte_arr.append(0)

    fl_dd['cte'] = cte_arr
    fl_dd['ate'] = ate_arr
    fl_dd['tte'] = tte_arr
    fl_dd['time_proj'] = fl_dd['time_el'] - fl_dd['time_el'].min()

    fl_dd = fl_dd.drop(columns=['_id'])
    dct = fl_dd.to_dict(orient="list")

    return dct


if __name__ == "__main__":

    la_time = 900
    cnt = 0
    cnt_max = np.inf  # np.inf
    fl_len_min = la_time*1.2
    flight_level_min = 20000
    db['projected_flights'].delete_many({})

    crs = col.find({"flight_length": {"$gt": fl_len_min}})

    for fl in crs:
        fl_count = crs.count()

        if cnt < cnt_max:
            fl_d = pd.DataFrame.from_dict(fl)
            fl_d = fl_d[fl_d['alt'] > flight_level_min]
            fl_d['time_el'] = fl_d['ts'] - fl_d['ts'].min()

            if fl_d['time_el'].max() < la_time:
                print("flight too short")
                continue

            try:
                steps = int(fl_d['time_el'].max() / la_time)

                for i in range(steps):
                    dct = create_projection_dict(fl_d[fl_d['time_el'] > i * la_time])
                    if dct:
                        db['projected_flights'].insert_one(dct)

            except Exception as e:
                print(e)
                continue

            cnt = cnt + 1