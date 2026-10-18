#ifndef PLANT_SENSORS_H
#define PLANT_SENSORS_H
/*
 * C sensors: PlantTruth in -> IMU, magnetometer, barometer, differential pressure, GPS.
 *
 * Conventions
 *   - One PlantSensors per aircraft (allocate plant_sensors_size() bytes); no globals. The random
 *     generator (PCG32) lives in the instance, so the same seed and inputs give the same output.
 *   - Call plant_sensors_step() once per plant step with the truth of that step. IMU, barometer and
 *     differential pressure update every step; GPS every gps_decimation steps starting at step 0,
 *     and holds the last fix between updates.
 *   - Output units follow the HIL ABI canonical output (hitl/interface/hil_model_api.h):
 *     accel m/s^2, gyro rad/s, magnetic field uT (body FRD), pressures Pa, GPS deg / MSL m / NED m/s.
 *   - White noise; the IMU noise is given as a density and converted to a per-sample standard
 *     deviation sigma = density * sqrt(1 / (2 * dt)). No bias, no scale error, no latency.
 *   - Standard C99 only.
 */
#include <stddef.h>
#include <stdint.h>

#include "skysurfer_plant.h"
#ifdef __cplusplus
extern "C" {
#endif

#define PLANT_SENSORS_API_VERSION 0x00010000u

typedef struct {
  double dt_s;                       /* plant step (0.004) */
  uint32_t gps_decimation;           /* GPS every N steps (25 -> 10 Hz) */
  uint32_t noise_enabled;            /* 0: outputs equal the ideal values (testing only; PX4 rejects stuck sensors) */
  double accel_noise_density[3];     /* (m/s^2)/sqrt(Hz), body x y z */
  double gyro_noise_density[3];      /* (rad/s)/sqrt(Hz) */
  double mag_noise_ut[3];            /* uT per sample */
  double baro_noise_pa;              /* Pa per sample */
  double diff_pressure_noise_pa;     /* Pa per sample */
  double gps_horizontal_noise_m;     /* per fix, north and east */
  double gps_vertical_noise_m;       /* per fix */
  double gps_velocity_noise_m_s[3];  /* per fix, north east down */
  double wmm_decimal_year;           /* fixed date for the magnetic model */
  uint32_t vibration_enabled;        /* add vibration noise while throttle_actual > 0 */
  uint32_t reserved;
  double vibration_accel_m_s2[3];    /* per sample */
  double vibration_gyro_rad_s[3];    /* per sample */
} PlantSensorConfig;

typedef struct {
  double time_s;
  double accel_m_s2[3];
  double gyro_rad_s[3];
  double magnetic_ut[3];
  double absolute_pressure_pa;
  double differential_pressure_pa;
  double temperature_k;              /* ISA temperature (no noise) */
  double gps_lla_msl[3];             /* deg, deg, m above MSL */
  double gps_velocity_ned_m_s[3];
  double gps_ground_speed_m_s;
  double gps_course_deg;             /* [0, 360) */
  double gps_sample_time_s;
  uint32_t imu_updated;              /* always 1 */
  uint32_t gps_updated;              /* 1 on the steps where a new fix was produced */
} PlantSensorOutput;

typedef struct PlantSensors PlantSensors;

uint32_t plant_sensors_api_version(void);
size_t plant_sensors_size(void);

/* Defaults decided on 2026-10-15. */
void plant_sensors_default_config(PlantSensorConfig *config);

int32_t plant_sensors_init(PlantSensors *sensors, const PlantSensorConfig *config, uint32_t seed);
int32_t plant_sensors_step(PlantSensors *sensors, const PlantTruth *truth, PlantSensorOutput *output);
int32_t plant_sensors_copy(PlantSensors *dst, const PlantSensors *src);

/* Ideal magnetic field in NED (uT) used by the magnetometer, for checks. */
void plant_sensors_magnetic_field_ned(const PlantSensorConfig *config, double latitude_deg, double longitude_deg,
                                    double height_m, double field_ned_ut[3]);

#ifdef __cplusplus
}
#endif
#endif
