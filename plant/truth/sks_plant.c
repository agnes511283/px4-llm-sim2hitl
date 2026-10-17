/* SksPlant: one generated plant core (sks_core.h) plus the C Truth. See skysurfer_plant.h. */
#include "skysurfer_plant.h"

#include "sks_geo.h"

#include <math.h>
#include <stddef.h>
#include <string.h>

/* Aircraft and environment constants of the source model (FW_SkySurfer_InitialFunction.m). The
 * core does not output them; plant/core/validate_plant.py checks |F_gravity| = mass * g every
 * step, so a change in the initialisation script cannot silently disagree with these. */
#define SKS_MASS_KG 1.3
#define SKS_GRAVITY_M_S2 9.80665

/* Aerodynamic table breakpoints (import_aerostates_avl.m). */
#define SKS_TABLE_ALPHA_MIN_DEG -10.0
#define SKS_TABLE_ALPHA_MAX_DEG 15.0
#define SKS_TABLE_BETA_MAX_DEG 10.0
#define SKS_TABLE_MACH_MIN 0.05
#define SKS_TABLE_MACH_MAX 0.10

static const double kPi = 3.14159265358979323846;

struct SksPlant {
  double origin_latitude_deg, origin_longitude_deg;
  uint32_t ready;
  uint32_t reserved;
  double core[]; /* sks_core_size() bytes; double keeps pointer/double alignment */
};

static SksCore *core_of(SksPlant *plant) { return (SksCore *)plant->core; }

uint32_t sks_plant_api_version(void) { return SKS_PLANT_API_VERSION; }

size_t sks_plant_size(void) { return offsetof(SksPlant, core) + sks_core_size(); }

int32_t sks_plant_init(SksPlant *plant, const SksInitialConditions *initial) {
  if (plant == NULL || initial == NULL) return SKS_ERR_INPUT;
  for (int k = 0; k < 3; k++) {
    if (initial->rates_body_rad_s[k] != 0.0) return SKS_ERR_INPUT; /* source supports zero only */
  }
  if (initial->site_msl_m != 0.0) return SKS_ERR_INPUT;
  if (!isfinite(initial->latitude_deg) || !isfinite(initial->longitude_deg) ||
      fabs(initial->latitude_deg) > 90.0 || fabs(initial->longitude_deg) > 180.0) {
    return SKS_ERR_INPUT;
  }
  SksCoreInitial ic;
  for (int k = 0; k < 3; k++) {
    ic.velocity_body_m_s[k] = initial->velocity_body_m_s[k];
    ic.euler_deg[k] = initial->euler_rad[k] * (180.0 / kPi);
  }
  ic.height_m = initial->height_agl_m;
  plant->ready = 0;
  int32_t code = sks_core_init(core_of(plant), &ic);
  if (code != SKS_CORE_OK) return code == SKS_CORE_ERR_INPUT ? SKS_ERR_INPUT : SKS_ERR_STATE;
  plant->origin_latitude_deg = initial->latitude_deg;
  plant->origin_longitude_deg = initial->longitude_deg;
  plant->ready = 1;
  return SKS_OK;
}

static void fill_truth(const SksPlant *plant, const double *y, double time_s, SksTruth *t) {
  const double deg = kPi / 180.0;
  memset(t, 0, sizeof(*t));
  t->time_s = time_s;
  for (int k = 0; k < 3; k++) {
    t->position_ned_m[k] = y[SKS_CORE_POSITION_NED_M + k];
    t->velocity_ned_m_s[k] = y[SKS_CORE_VELOCITY_NED_M_S + k];
    t->velocity_body_m_s[k] = y[SKS_CORE_VELOCITY_BODY_M_S + k];
    t->euler_rad[k] = y[SKS_CORE_EULER_RAD + k];
    t->rates_body_rad_s[k] = y[SKS_CORE_RATES_BODY_RAD_S + k];
    t->angular_accel_body_rad_s2[k] = y[SKS_CORE_ANGULAR_ACCEL_RAD_S2 + k];
    t->accel_ned_m_s2[k] = y[SKS_CORE_ACCEL_NED_M_S2 + k];
    t->force_aero_body_N[k] = y[SKS_CORE_FORCE_AERO_N + k];
    t->moment_aero_body_Nm[k] = y[SKS_CORE_MOMENT_AERO_NM + k];
    t->force_thrust_body_N[k] = y[SKS_CORE_FORCE_THRUST_N + k];
    t->moment_thrust_body_Nm[k] = y[SKS_CORE_MOMENT_THRUST_NM + k];
    t->force_ground_body_N[k] = y[SKS_CORE_FORCE_GROUND_N + k];
    t->force_gravity_body_N[k] = y[SKS_CORE_FORCE_GRAVITY_N + k];
  }
  for (int k = 0; k < 4; k++) {
    t->quaternion_nb[k] = y[SKS_CORE_QUATERNION + k];
    t->surface_deflection_rad[k] = y[SKS_CORE_SURFACE_DEG + k] * deg;
  }
  /* Source block Flat Earth to LLA: WGS84, psi = 0, reference height 0 (sks_geo.h). */
  sks_geo_flat_to_lla(t->position_ned_m[0], t->position_ned_m[1], plant->origin_latitude_deg,
                      plant->origin_longitude_deg, &t->latitude_deg, &t->longitude_deg);
  t->height_agl_m = -t->position_ned_m[2];
  t->altitude_msl_m = t->height_agl_m; /* site_msl = 0 */
  t->ground_speed_m_s = hypot(t->velocity_ned_m_s[0], t->velocity_ned_m_s[1]);
  t->course_rad = atan2(t->velocity_ned_m_s[1], t->velocity_ned_m_s[0]);
  if (t->course_rad < 0.0) t->course_rad += 2.0 * kPi;
  if (t->course_rad >= 2.0 * kPi) t->course_rad = 0.0; /* -tiny + 2*pi rounds to 2*pi */

  /* Ideal accelerometer, as the source Measurement/acc: Ab - Vb x w - DCM*[0 0 g], where the
   * gravity term is F_gravity / mass (the source Gravity block is DCM*[0 0 g]*mass). */
  const double *v = t->velocity_body_m_s, *w = t->rates_body_rad_s;
  const double vxw[3] = {v[1] * w[2] - v[2] * w[1], v[2] * w[0] - v[0] * w[2], v[0] * w[1] - v[1] * w[0]};
  for (int k = 0; k < 3; k++) {
    t->specific_force_body_m_s2[k] =
        y[SKS_CORE_ACCEL_BODY_M_S2 + k] - vxw[k] - t->force_gravity_body_N[k] / SKS_MASS_KG;
  }

  t->airspeed_true_m_s = y[SKS_CORE_AIRSPEED_M_S];
  t->alpha_rad = y[SKS_CORE_ALPHA_DEG] * deg;
  t->beta_rad = y[SKS_CORE_BETA_DEG] * deg;
  t->mach = y[SKS_CORE_MACH];
  t->air_density_kg_m3 = y[SKS_CORE_AIR_DENSITY_KG_M3];
  t->static_pressure_pa = y[SKS_CORE_STATIC_PRESSURE_PA];
  t->air_temperature_k = y[SKS_CORE_AIR_TEMPERATURE_K];
  t->dynamic_pressure_pa = 0.5 * t->air_density_kg_m3 * t->airspeed_true_m_s * t->airspeed_true_m_s;
  /* wind_ned_m_s stays zero: the core accepts zero wind only (sks_plant_step rejects others). */
  t->throttle_actual = y[SKS_CORE_THROTTLE];

  const double *fg = t->force_ground_body_N;
  t->on_ground = (fg[0] != 0.0 || fg[1] != 0.0 || fg[2] != 0.0) ? 1u : 0u;
  t->aero_active = y[SKS_CORE_AERO_ACTIVE] > 0.5 ? 1u : 0u;
  if (t->aero_active) {
    const double a = y[SKS_CORE_ALPHA_DEG], b = y[SKS_CORE_BETA_DEG];
    if (a < SKS_TABLE_ALPHA_MIN_DEG || a > SKS_TABLE_ALPHA_MAX_DEG || fabs(b) > SKS_TABLE_BETA_MAX_DEG) t->flags |= 1u;
    if (t->mach < SKS_TABLE_MACH_MIN || t->mach > SKS_TABLE_MACH_MAX) t->flags |= 2u;
  }
}

int32_t sks_plant_step(SksPlant *plant, const SksPlantInput *input, SksTruth *truth) {
  if (plant == NULL || input == NULL || truth == NULL) return SKS_ERR_INPUT;
  if (!plant->ready) return SKS_ERR_STATE;
  for (int k = 0; k < 3; k++) {
    if (input->wind_ned_m_s[k] != 0.0) return SKS_ERR_INPUT; /* source supports zero only */
  }
  const SksActuatorCommand *c = &input->command;
  double controls[SKS_CORE_CONTROL_COUNT] = {0};
  controls[SKS_CORE_CTRL_AILERON_LEFT] = c->aileron_left;
  controls[SKS_CORE_CTRL_AILERON_RIGHT] = c->aileron_right;
  controls[SKS_CORE_CTRL_ELEVATOR] = c->elevator;
  controls[SKS_CORE_CTRL_RUDDER] = c->rudder;
  controls[SKS_CORE_CTRL_THROTTLE] = c->throttle;
  const double time_s = sks_core_time_s(core_of(plant));
  double y[SKS_CORE_SNAPSHOT_COUNT];
  int32_t code = sks_core_step(core_of(plant), controls, y);
  if (code == SKS_CORE_ERR_INPUT) return SKS_ERR_INPUT;
  if (code == SKS_CORE_ERR_DIVERGED) return SKS_ERR_DIVERGED;
  if (code != SKS_CORE_OK) return SKS_ERR_STATE;
  fill_truth(plant, y, time_s, truth);
  return SKS_OK;
}

int32_t sks_plant_copy(SksPlant *dst, const SksPlant *src) {
  if (dst == NULL || src == NULL) return SKS_ERR_INPUT;
  if (dst == src) return SKS_OK;
  dst->origin_latitude_deg = src->origin_latitude_deg;
  dst->origin_longitude_deg = src->origin_longitude_deg;
  dst->ready = src->ready;
  dst->reserved = 0;
  return sks_core_copy(core_of(dst), (const SksCore *)src->core) == SKS_CORE_OK ? SKS_OK : SKS_ERR_STATE;
}
