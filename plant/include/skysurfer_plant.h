#ifndef SKYSURFER_PLANT_H
#define SKYSURFER_PLANT_H
/*
 * SkySurfer plant interface: actuator command in, truth out.
 *
 * STATUS: draft 0.2. Confirmed by the user: PlantActuatorCommand, PlantInput, PlantInitialConditions
 * and PlantTruth. The 6DOF is the core generated from FW_SkySurfer_HIL.slx (plant_core.h,
 * plant/core/); Plant wraps one PlantCore and computes PlantTruth in C. Aircraft parameters are
 * generated constants inside the core, so there is no parameter struct here. Implemented in
 * plant/truth/plant_truth.c (validated by plant/core/validate_plant.py); sensors in plant_sensors.h.
 * The HIL runtime reaches it through hil_runtime/interface/hil_model_api.h, implemented by
 * hil_runtime/aircraft/skysurfer/adapter.c.
 *
 * Conventions
 *   - Reentrant: every call takes its own Plant; one process may run any number of aircraft,
 *     stepped one call at a time (see plant_core.h).
 *   - Standard C99 only (no POSIX, no platform headers) so macOS and Windows build the same source.
 *   - SI units; angles in rad unless the name says _deg.
 *   - Earth frame NED (north, east, down) with its origin at the initial ground point;
 *     body frame FRD (forward, right, down).
 *   - Quaternion q = [w x y z] rotates body to NED: v_ned = R(q) * v_body.
 *   - Euler angles are [roll pitch yaw], ZYX order.
 *   - Fixed step PLANT_CORE_DT_S = 0.004 s, RK4 (ode4), as generated from the source model.
 *   - plant_step() reports truth sampled at t_k, BEFORE integrating to t_k + dt; this is the
 *     same output phase as the current HIL ABI.
 */
#include <stddef.h>
#include <stdint.h>

#include "plant_core.h"
#ifdef __cplusplus
extern "C" {
#endif

#define PLANT_API_VERSION 0x00000002u /* draft 0.2 */

/* Return codes. */
#define PLANT_OK 0
#define PLANT_ERR_STATE 2   /* called in the wrong order or on a diverged state */
#define PLANT_ERR_DIVERGED 3 /* non-finite or outside the validated envelope; re-initialise */
#define PLANT_ERR_INPUT 4   /* invalid argument */

/* Normalized actuator command. Same meaning as the PX4 HIL_ACTUATOR_CONTROLS channels after the
 * HIL_ACT_FUNC mapping (current ABI controls[0..4]). Sign and degrees per unit live in the
 * generated core (source ACTUATOR subsystem), not here. */
typedef struct {
  double aileron_left;  /* [-1, 1] */
  double aileron_right; /* [-1, 1] */
  double elevator;      /* [-1, 1] */
  double rudder;        /* [-1, 1] */
  double throttle;      /* [0, 1] */
} PlantActuatorCommand;

typedef struct {
  PlantActuatorCommand command;
  double wind_ned_m_s[3]; /* steady wind; the reference model supports only zero */
} PlantInput;

/* Same fields the current scene recipe accepts (hil_runtime/aircraft/skysurfer/scenario.py). */
typedef struct {
  double height_agl_m;
  double velocity_body_m_s[3];
  double euler_rad[3];
  double rates_body_rad_s[3]; /* reference supports only zero */
  double latitude_deg, longitude_deg;
  double site_msl_m; /* ground datum above MSL; reference supports only 0 */
  uint32_t seed;     /* reserved for components with noise; the plant itself is deterministic */
} PlantInitialConditions;

/* One aircraft: an PlantCore plus the Truth bookkeeping (origin latitude/longitude, step index).
 * Opaque; allocate plant_size() bytes. Copy with plant_copy() (trim, comparisons against
 * the reference, reinforcement-learning resets), never with a plain memcpy. */
typedef struct Plant Plant;

/* Everything the sensors and the SITL stubs may need. The plant always fills every field; what a
 * SITL tier publishes to PX4 is chosen outside the plant. */
typedef struct {
  double time_s;
  /* position */
  double position_ned_m[3];
  double latitude_deg, longitude_deg, altitude_msl_m, height_agl_m;
  /* velocity */
  double velocity_ned_m_s[3];
  double velocity_body_m_s[3];
  double ground_speed_m_s, course_rad; /* horizontal speed; course in [0, 2*pi) */
  /* attitude and rates */
  double quaternion_nb[4];
  double euler_rad[3];
  double rates_body_rad_s[3];
  double angular_accel_body_rad_s2[3];
  /* accelerations */
  double specific_force_body_m_s2[3]; /* ideal accelerometer: (total force - gravity) / mass = Ab - Vb x w - g_body */
  double accel_ned_m_s2[3];           /* kinematic acceleration */
  /* air data and atmosphere */
  double airspeed_true_m_s, alpha_rad, beta_rad, mach, dynamic_pressure_pa;
  double air_density_kg_m3, static_pressure_pa, air_temperature_k;
  double wind_ned_m_s[3];
  /* actuators after servo dynamics and sign: aileron_left, aileron_right, elevator, rudder */
  double surface_deflection_rad[4];
  double throttle_actual;
  /* force and moment breakdown, body frame */
  double force_aero_body_N[3], moment_aero_body_Nm[3];
  double force_thrust_body_N[3], moment_thrust_body_Nm[3];
  double force_ground_body_N[3];
  double force_gravity_body_N[3];
  uint32_t on_ground;   /* ground contact force active */
  uint32_t aero_active; /* airspeed above the aero cut-in */
  uint32_t flags;       /* while aero_active: bit 0 alpha or beta outside the aero table, bit 1 Mach outside it (the table extrapolates) */
  uint32_t reserved;
} PlantTruth;

uint32_t plant_api_version(void);
size_t plant_size(void);

/* Set the state from initial conditions (rates, site_msl and wind must be zero, as in the source). */
int32_t plant_init(Plant *plant, const PlantInitialConditions *initial);

/* Report truth at t_k into truth, then advance one fixed step with input held. */
int32_t plant_step(Plant *plant, const PlantInput *input, PlantTruth *truth);

/* Copy the complete state of src into dst. */
int32_t plant_copy(Plant *dst, const Plant *src);

#ifdef __cplusplus
}
#endif
#endif
