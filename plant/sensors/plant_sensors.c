/* C sensors. See plant_sensors.h. */
#include "plant_sensors.h"

#include <math.h>
#include <string.h>

#include "plant_geo.h"
#include "plant_wmm.h"

static const double kPi = 3.14159265358979323846;
static const double kG0 = 9.80665;                 /* m/s^2 per g, for datasheet ug values */

struct PlantSensors {
  PlantSensorConfig config;
  uint64_t rng_state, rng_inc; /* PCG32 */
  double spare;                /* second value of the polar Box-Muller pair */
  uint32_t has_spare;
  uint32_t ready;
  uint64_t step_index;
  PlantSensorOutput gps_latch;   /* GPS fields of the last fix */
};

/* PCG32 (O'Neill, pcg-random.org), XSH RR variant. */
static uint32_t pcg32(PlantSensors *s) {
  const uint64_t old = s->rng_state;
  s->rng_state = old * 6364136223846793005ULL + s->rng_inc;
  const uint32_t xorshifted = (uint32_t)(((old >> 18u) ^ old) >> 27u);
  const uint32_t rot = (uint32_t)(old >> 59u);
  return (xorshifted >> rot) | (xorshifted << ((32u - rot) & 31u));
}

static double uniform_open(PlantSensors *s) { /* (0, 1) */
  return ((double)pcg32(s) + 0.5) / 4294967296.0;
}

static double gaussian(PlantSensors *s) { /* standard normal, polar Box-Muller */
  if (s->has_spare) {
    s->has_spare = 0;
    return s->spare;
  }
  double x1, x2, w;
  do {
    x1 = 2.0 * uniform_open(s) - 1.0;
    x2 = 2.0 * uniform_open(s) - 1.0;
    w = x1 * x1 + x2 * x2;
  } while (w >= 1.0 || w == 0.0);
  w = sqrt(-2.0 * log(w) / w);
  s->spare = x2 * w;
  s->has_spare = 1;
  return x1 * w;
}

static double noise(PlantSensors *s, double sigma) {
  if (!s->config.noise_enabled || sigma == 0.0) return 0.0;
  return sigma * gaussian(s);
}

uint32_t plant_sensors_api_version(void) { return PLANT_SENSORS_API_VERSION; }

size_t plant_sensors_size(void) { return sizeof(PlantSensors); }

void plant_sensors_default_config(PlantSensorConfig *c) {
  if (c == NULL) return;
  memset(c, 0, sizeof(*c));
  c->dt_s = 0.004;
  c->gps_decimation = 25;
  c->noise_enabled = 1;
  /* ICM-42688-P datasheet: accel 65 / 65 / 70 ug/sqrt(Hz), gyro 2.8 mdps/sqrt(Hz). */
  c->accel_noise_density[0] = 65e-6 * kG0;
  c->accel_noise_density[1] = 65e-6 * kG0;
  c->accel_noise_density[2] = 70e-6 * kG0;
  for (int k = 0; k < 3; k++) c->gyro_noise_density[k] = 2.8e-3 * (kPi / 180.0);
  /* PX4 v1.17 sensor_mag_sim: 0.02 / 0.02 / 0.03 gauss. */
  c->mag_noise_ut[0] = 2.0;
  c->mag_noise_ut[1] = 2.0;
  c->mag_noise_ut[2] = 3.0;
  /* MS5611 at OSR 1024 (PX4 v1.17 driver): 0.027 mbar RMS. */
  c->baro_noise_pa = 2.7;
  c->diff_pressure_noise_pa = 0.0; /* decided: no airspeed noise */
  /* PX4 v1.17 sensor_gps_sim. */
  c->gps_horizontal_noise_m = 0.2;
  c->gps_vertical_noise_m = 0.5;
  c->gps_velocity_noise_m_s[0] = 0.06;
  c->gps_velocity_noise_m_s[1] = 0.077;
  c->gps_velocity_noise_m_s[2] = 0.158;
  c->wmm_decimal_year = 2026.0;
  /* PX4 v1.17 SIH (Bulka & Nahon 2018), used only when vibration_enabled. */
  c->vibration_enabled = 0;
  c->vibration_accel_m_s2[0] = 0.5;
  c->vibration_accel_m_s2[1] = 1.7;
  c->vibration_accel_m_s2[2] = 1.4;
  c->vibration_gyro_rad_s[0] = 0.14;
  c->vibration_gyro_rad_s[1] = 0.07;
  c->vibration_gyro_rad_s[2] = 0.03;
}

static int sigma_valid(double v) { return isfinite(v) && v >= 0.0; }

static int config_valid(const PlantSensorConfig *c) {
  if (!(c->dt_s > 0.0) || !isfinite(c->dt_s) || c->gps_decimation == 0) return 0;
  for (int k = 0; k < 3; k++) {
    if (!sigma_valid(c->accel_noise_density[k]) || !sigma_valid(c->gyro_noise_density[k]) ||
        !sigma_valid(c->mag_noise_ut[k]) || !sigma_valid(c->gps_velocity_noise_m_s[k]) ||
        !sigma_valid(c->vibration_accel_m_s2[k]) || !sigma_valid(c->vibration_gyro_rad_s[k])) {
      return 0;
    }
  }
  return sigma_valid(c->baro_noise_pa) && sigma_valid(c->diff_pressure_noise_pa) &&
         sigma_valid(c->gps_horizontal_noise_m) && sigma_valid(c->gps_vertical_noise_m) &&
         isfinite(c->wmm_decimal_year);
}

int32_t plant_sensors_init(PlantSensors *s, const PlantSensorConfig *config, uint32_t seed) {
  if (s == NULL || config == NULL || !config_valid(config)) return PLANT_ERR_INPUT;
  memset(s, 0, sizeof(*s));
  s->config = *config;
  /* PCG32 seeding (pcg32_srandom_r): fixed stream, state from the seed. */
  s->rng_inc = (0xda3e39cb94b95bdbULL << 1u) | 1u;
  pcg32(s);
  s->rng_state += (uint64_t)seed;
  pcg32(s);
  s->ready = 1;
  return PLANT_OK;
}

void plant_sensors_magnetic_field_ned(const PlantSensorConfig *config, double latitude_deg, double longitude_deg,
                                    double height_m, double field_ned_ut[3]) {
  double nt[3];
  plant_wmm_field_ned(latitude_deg, longitude_deg, height_m, config->wmm_decimal_year, nt);
  for (int k = 0; k < 3; k++) field_ned_ut[k] = nt[k] / 1000.0;
}

/* v_body = R(q)^T v_ned, q = [w x y z] rotating body to NED. */
static void ned_to_body(const double q[4], const double v[3], double out[3]) {
  const double w = q[0], x = q[1], y = q[2], z = q[3];
  const double r[3][3] = {
      {1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)},
      {2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)},
      {2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)}};
  for (int i = 0; i < 3; i++) out[i] = r[0][i] * v[0] + r[1][i] * v[1] + r[2][i] * v[2];
}

int32_t plant_sensors_step(PlantSensors *s, const PlantTruth *t, PlantSensorOutput *o) {
  if (s == NULL || t == NULL || o == NULL) return PLANT_ERR_INPUT;
  if (!s->ready) return PLANT_ERR_STATE;
  const PlantSensorConfig *c = &s->config;
  memset(o, 0, sizeof(*o));
  o->time_s = t->time_s;

  /* IMU: ideal specific force and body rates plus white noise (and optional vibration). */
  const double root = sqrt(1.0 / (2.0 * c->dt_s));
  const int vibrating = c->vibration_enabled && t->throttle_actual > 0.0;
  for (int k = 0; k < 3; k++) {
    o->accel_m_s2[k] = t->specific_force_body_m_s2[k] + noise(s, c->accel_noise_density[k] * root);
    o->gyro_rad_s[k] = t->rates_body_rad_s[k] + noise(s, c->gyro_noise_density[k] * root);
  }
  if (vibrating) {
    for (int k = 0; k < 3; k++) {
      o->accel_m_s2[k] += noise(s, c->vibration_accel_m_s2[k]);
      o->gyro_rad_s[k] += noise(s, c->vibration_gyro_rad_s[k]);
    }
  }

  /* Magnetometer: WMM at the true position (geoid separation 0), rotated into body axes. */
  double b_ned[3], b_body[3];
  plant_sensors_magnetic_field_ned(c, t->latitude_deg, t->longitude_deg, t->altitude_msl_m, b_ned);
  ned_to_body(t->quaternion_nb, b_ned, b_body);
  for (int k = 0; k < 3; k++) o->magnetic_ut[k] = b_body[k] + noise(s, c->mag_noise_ut[k]);

  /* Barometer: ISA static pressure from the core. */
  o->absolute_pressure_pa = t->static_pressure_pa + noise(s, c->baro_noise_pa);
  o->temperature_k = t->air_temperature_k;

  /* Pitot: dynamic pressure of the body x air-relative velocity, signed (as PX4 sensor_airspeed_sim). */
  const double u_air = t->airspeed_true_m_s * cos(t->alpha_rad) * cos(t->beta_rad);
  o->differential_pressure_pa = (u_air < 0.0 ? -0.5 : 0.5) * t->air_density_kg_m3 * u_air * u_air +
                                noise(s, c->diff_pressure_noise_pa);

  /* GPS at 1 / gps_decimation of the step rate; hold the last fix in between. */
  o->imu_updated = 1;
  if (s->step_index % c->gps_decimation == 0) {
    PlantSensorOutput *g = &s->gps_latch;
    const double dn = noise(s, c->gps_horizontal_noise_m), de = noise(s, c->gps_horizontal_noise_m);
    /* Same local flat-earth step as the Truth, so the result is wrapped into [-90, 90] x [-180, 180]
     * (crossing a pole flips the longitude). Very close to a pole, east noise maps to a large
     * longitude change: geometrically right, and still a legal coordinate. */
    plant_geo_flat_to_lla(dn, de, t->latitude_deg, t->longitude_deg, &g->gps_lla_msl[0], &g->gps_lla_msl[1]);
    g->gps_lla_msl[2] = t->altitude_msl_m + noise(s, c->gps_vertical_noise_m);
    for (int k = 0; k < 3; k++) {
      g->gps_velocity_ned_m_s[k] = t->velocity_ned_m_s[k] + noise(s, c->gps_velocity_noise_m_s[k]);
    }
    g->gps_ground_speed_m_s = hypot(g->gps_velocity_ned_m_s[0], g->gps_velocity_ned_m_s[1]);
    double course = atan2(g->gps_velocity_ned_m_s[1], g->gps_velocity_ned_m_s[0]) * (180.0 / kPi);
    if (course < 0.0) course += 360.0;
    g->gps_course_deg = course >= 360.0 ? 0.0 : course;
    g->gps_sample_time_s = t->time_s;
    o->gps_updated = 1;
  }
  memcpy(o->gps_lla_msl, s->gps_latch.gps_lla_msl, sizeof(o->gps_lla_msl));
  memcpy(o->gps_velocity_ned_m_s, s->gps_latch.gps_velocity_ned_m_s, sizeof(o->gps_velocity_ned_m_s));
  o->gps_ground_speed_m_s = s->gps_latch.gps_ground_speed_m_s;
  o->gps_course_deg = s->gps_latch.gps_course_deg;
  o->gps_sample_time_s = s->gps_latch.gps_sample_time_s;
  s->step_index++;
  return PLANT_OK;
}

int32_t plant_sensors_copy(PlantSensors *dst, const PlantSensors *src) {
  if (dst == NULL || src == NULL) return PLANT_ERR_INPUT;
  if (dst != src) memcpy(dst, src, sizeof(*dst)); /* no internal pointers */
  return PLANT_OK;
}
