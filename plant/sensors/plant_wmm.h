#ifndef PLANT_WMM_H
#define PLANT_WMM_H
/* World Magnetic Model (spherical harmonics to degree 12), as specified in the WMM technical
 * report. Coefficients in plant_wmm_coeffs.c (generated). Standard C99, no state. */
#ifdef __cplusplus
extern "C" {
#endif

#define PLANT_WMM_DEGREE 12
#define PLANT_WMM_COEFF_COUNT (PLANT_WMM_DEGREE * (PLANT_WMM_DEGREE + 3) / 2)

typedef struct {
  int n, m;
  double g, h, gdot, hdot; /* nT, nT/yr */
} PlantWmmCoeff;

extern const double plant_wmm_epoch;
extern const char plant_wmm_name[];
extern const PlantWmmCoeff plant_wmm_coeffs[PLANT_WMM_COEFF_COUNT];

/* Magnetic field in the local geodetic NED frame, nT, at geodetic latitude/longitude (deg),
 * height above the WGS84 ellipsoid (m) and decimal year. */
void plant_wmm_field_ned(double latitude_deg, double longitude_deg, double height_m, double decimal_year,
                       double field_ned_nt[3]);

#ifdef __cplusplus
}
#endif
#endif
