#ifndef HIL_MODEL_API_H
#define HIL_MODEL_API_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define HIL_ABI_VERSION 0x00010001u
#define HIL_RAW_COUNT 58u
#if defined(_WIN32)
#if defined(HIL_BUILD_DLL)
#define HIL_EXPORT __declspec(dllexport)
#else
#define HIL_EXPORT __declspec(dllimport)
#endif
#else
#define HIL_EXPORT __attribute__((visibility("default")))
#endif
/* Capability bits are stable across recipes; raw truth remains optional. */
#define HIL_CAP_IMU 1u
#define HIL_CAP_GPS 2u
#define HIL_CAP_PRESSURE 4u
#define HIL_CAP_TRUTH 8u
#define HIL_CAP_RESET 16u
#define HIL_CAP_RUNTIME_INITIAL 32u
/* initialize/reset/step/terminate require serialized calls. Reset after worker stop. */
/* Natural C alignment. No packing. All arrays have fixed dimensions. */
typedef struct {
  uint32_t abi_version, struct_size;
  double height_m, body_velocity_m_s[3], euler_deg[3], latitude_deg, longitude_deg;
  /* Explicit GPS datum conversion: MSL = WGS84 ellipsoid height - separation. */
  double geoid_separation_m;
  uint32_t seed_policy; /* 0: the fixed default sensor seed. Other values unsupported. */
  uint32_t reserved[7];
} HilInitialConditions;
typedef struct {
  uint32_t abi_version, struct_size;
  double controls[16];
  uint64_t step_index, actuator_age_ns, input_sequence;
  uint32_t actuator_valid, actuator_new, fc_armed, reserved;
} HilModelInput;
typedef struct {
  uint32_t abi_version, struct_size;
  uint64_t model_time_ns, imu_sample_time_ns, gps_sample_time_ns;
  double accel_m_s2[3], gyro_rad_s[3], magnetic_uT[3];
  double absolute_pressure_pa, differential_pressure_pa;
  double gps_lla_msl[3], velocity_ned_m_s[3], ground_speed_m_s, course_deg;
  double raw_source[HIL_RAW_COUNT];
  uint32_t imu_valid, imu_updated, gps_valid, gps_updated;
  uint32_t pressure_height_valid, temperature_valid, fields_updated, reserved;
} HilModelOutput;
typedef struct {
  uint32_t abi_version, struct_size;
  uint32_t initial_size, input_size, output_size, output_phase;
  uint64_t fixed_step_ns, imu_period_ns, gps_period_ns;
  char aircraft_id[32], build_id[64], source_sha256[65], platform[32];
  uint32_t raw_count, seed_policy, instance_count, reserved;
  uint64_t capabilities, initial_supported;
} HilModelInfo;
HIL_EXPORT uint32_t hil_model_get_abi_version(void);
HIL_EXPORT int32_t hil_model_get_info(HilModelInfo *out);
HIL_EXPORT int32_t hil_model_initialize(const HilInitialConditions *initial);
HIL_EXPORT int32_t hil_model_step(const HilModelInput *input,HilModelOutput *output);
HIL_EXPORT int32_t hil_model_reset(const HilInitialConditions *initial);
HIL_EXPORT int32_t hil_model_terminate(void);
HIL_EXPORT int32_t hil_model_get_last_error(char *buffer,uint32_t capacity);
#ifdef __cplusplus
}
#endif
#endif
