#ifndef SKS_WMM_H
#define SKS_WMM_H
/* World Magnetic Model (spherical harmonics to degree 12), as specified in the WMM technical
 * report. Coefficients in sks_wmm_coeffs.c (generated). Standard C99, no state. */
#ifdef __cplusplus
extern "C" {
#endif

#define SKS_WMM_DEGREE 12
#define SKS_WMM_COEFF_COUNT (SKS_WMM_DEGREE * (SKS_WMM_DEGREE + 3) / 2)

typedef struct {
  int n, m;
  double g, h, gdot, hdot; /* nT, nT/yr */
} SksWmmCoeff;

extern const double sks_wmm_epoch;
extern const char sks_wmm_name[];
extern const SksWmmCoeff sks_wmm_coeffs[SKS_WMM_COEFF_COUNT];

/* Magnetic field in the local geodetic NED frame, nT, at geodetic latitude/longitude (deg),
 * height above the WGS84 ellipsoid (m) and decimal year. */
void sks_wmm_field_ned(double latitude_deg, double longitude_deg, double height_m, double decimal_year,
                       double field_ned_nt[3]);

#ifdef __cplusplus
}
#endif
#endif
