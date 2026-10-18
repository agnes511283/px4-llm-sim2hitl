#ifndef PLANT_GEO_H
#define PLANT_GEO_H
/* Geodetic helpers shared by the C Truth and the C sensors (header only, standard C99).
 * They follow MATLAB R2026b flat2lla and its Aero.internal.geodesy.wraplatitude / wraplongitude
 * (checked against MATLAB by plant/core/validate_plant.py), which is the algorithm of the source
 * block Flat Earth to LLA. */
#include <math.h>

#define PLANT_GEO_PI 3.14159265358979323846
#define PLANT_WGS84_A_M 6378137.0
#define PLANT_WGS84_F (1.0 / 298.257223563)

/* Angle in degrees wrapped as MATLAB wraplongitude(x, 180): unchanged inside [-180, 180]
 * (both ends kept), otherwise rem(x +- 180, 360) -+ 180. */
static inline double plant_geo_wrap180(double x) {
  if (x > 180.0) return fmod(x + 180.0, 360.0) - 180.0;
  if (x < -180.0) return fmod(x - 180.0, 360.0) + 180.0;
  return x;
}

/* Latitude folded into [-90, 90] (crossing a pole adds 180 deg of longitude), then longitude
 * wrapped, as MATLAB wraplatitude(lat, lon, 180) followed by wraplongitude(lon, 180). */
static inline void plant_geo_wrap_lat_lon(double *lat_deg, double *lon_deg) {
  double lat = plant_geo_wrap180(*lat_deg), lon = *lon_deg;
  if (lat > 90.0) {
    lat = 180.0 - lat;
    lon += 180.0;
  } else if (lat < -90.0) {
    lat = -180.0 - lat;
    lon += 180.0;
  }
  *lat_deg = lat;
  *lon_deg = plant_geo_wrap180(lon);
}

/* WGS84 radii of curvature (m) at geodetic latitude lat_rad: meridian rm, prime vertical rn. */
static inline void plant_geo_radii(double lat_rad, double *rm, double *rn) {
  const double e2 = 2.0 * PLANT_WGS84_F - PLANT_WGS84_F * PLANT_WGS84_F;
  const double s2 = sin(lat_rad) * sin(lat_rad);
  *rn = PLANT_WGS84_A_M / sqrt(1.0 - e2 * s2);
  *rm = *rn * ((1.0 - e2) / (1.0 - e2 * s2));
}

/* Small north/east displacement (m) from a reference point to latitude/longitude (deg):
 * flat2lla with psi = 0. */
static inline void plant_geo_flat_to_lla(double north_m, double east_m, double lat0_deg, double lon0_deg,
                                       double *lat_deg, double *lon_deg) {
  double lat0 = lat0_deg, lon0 = lon0_deg, rm, rn;
  plant_geo_wrap_lat_lon(&lat0, &lon0);
  const double mu0 = lat0 * (PLANT_GEO_PI / 180.0);
  plant_geo_radii(mu0, &rm, &rn);
  double lat = (180.0 / PLANT_GEO_PI) * (north_m / rm) + lat0;
  double lon = (180.0 / PLANT_GEO_PI) * (east_m / (rn * cos(mu0))) + lon0;
  plant_geo_wrap_lat_lon(&lat, &lon);
  *lat_deg = lat;
  *lon_deg = lon;
}

#endif
