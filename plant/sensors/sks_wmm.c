/* World Magnetic Model field evaluation (WMM technical report, sections 1.2-1.3). */
#include "sks_wmm.h"

#include <math.h>

#define N SKS_WMM_DEGREE

static const double kPi = 3.14159265358979323846;
static const double kWgs84A = 6378.137;               /* km */
static const double kWgs84F = 1.0 / 298.257223563;
static const double kGeomagneticRadius = 6371.2;      /* km */

void sks_wmm_field_ned(double latitude_deg, double longitude_deg, double height_m, double decimal_year,
                       double field_ned_nt[3]) {
  const double deg = kPi / 180.0;
  const double e2 = kWgs84F * (2.0 - kWgs84F);
  const double phi = latitude_deg * deg, lambda = longitude_deg * deg, h = height_m / 1000.0;

  /* Geodetic -> geocentric spherical (r, phi'). */
  const double sp = sin(phi), cp = cos(phi);
  const double rc = kWgs84A / sqrt(1.0 - e2 * sp * sp);
  const double p = (rc + h) * cp, z = (rc * (1.0 - e2) + h) * sp;
  const double r = sqrt(p * p + z * z);
  const double phic = asin(z / r);

  /* Time-adjusted Gauss coefficients. */
  double g[N + 1][N + 1] = {{0}}, hh[N + 1][N + 1] = {{0}};
  const double dt = decimal_year - sks_wmm_epoch;
  for (int k = 0; k < SKS_WMM_COEFF_COUNT; k++) {
    const SksWmmCoeff *c = &sks_wmm_coeffs[k];
    g[c->n][c->m] = c->g + dt * c->gdot;
    hh[c->n][c->m] = c->h + dt * c->hdot;
  }

  /* Associated Legendre functions of cos(theta) = sin(phi'), theta = colatitude, Gauss-normalised
   * by recursion, with derivatives d/dtheta; then Schmidt semi-normalisation factors. */
  const double ct = sin(phic), st = cos(phic);
  double P[N + 1][N + 1] = {{0}}, dP[N + 1][N + 1] = {{0}}, S[N + 1][N + 1] = {{0}};
  P[0][0] = 1.0;
  S[0][0] = 1.0;
  for (int n = 1; n <= N; n++) {
    S[n][0] = S[n - 1][0] * (2.0 * n - 1.0) / n;
    for (int m = 0; m <= n; m++) {
      if (n == m) {
        P[n][m] = st * P[n - 1][m - 1];
        dP[n][m] = st * dP[n - 1][m - 1] + ct * P[n - 1][m - 1];
      } else {
        const double k = (n > 1) ? ((n - 1.0) * (n - 1.0) - (double)m * m) / ((2.0 * n - 1.0) * (2.0 * n - 3.0)) : 0.0;
        const double p2 = (n > 1 && m <= n - 2) ? P[n - 2][m] : 0.0;
        const double dp2 = (n > 1 && m <= n - 2) ? dP[n - 2][m] : 0.0;
        P[n][m] = ct * P[n - 1][m] - k * p2;
        dP[n][m] = ct * dP[n - 1][m] - st * P[n - 1][m] - k * dp2;
      }
      if (m > 0) S[n][m] = S[n][m - 1] * sqrt((n - m + 1.0) * (m == 1 ? 2.0 : 1.0) / (n + m));
    }
  }

  /* Field components in the geocentric frame: X' north, Y' east, Z' down. */
  double x = 0.0, y = 0.0, zc = 0.0;
  double ratio = kGeomagneticRadius / r, ar = ratio * ratio; /* (a/r)^(n+2) starts at n = 0 */
  for (int n = 1; n <= N; n++) {
    ar *= ratio;
    for (int m = 0; m <= n; m++) {
      const double cm = cos(m * lambda), sm = sin(m * lambda);
      const double gs = g[n][m] * S[n][m], hs = hh[n][m] * S[n][m];
      const double term = gs * cm + hs * sm;
      x += ar * term * dP[n][m];
      y += ar * m * (gs * sm - hs * cm) * P[n][m];
      zc -= ar * (n + 1.0) * term * P[n][m];
    }
  }
  y /= st;
  /* WMM report eq. 17: rotate from geocentric to geodetic. */
  const double psi = phic - phi;
  field_ned_nt[0] = x * cos(psi) - zc * sin(psi);
  field_ned_nt[1] = y;
  field_ned_nt[2] = x * sin(psi) + zc * cos(psi);
}
