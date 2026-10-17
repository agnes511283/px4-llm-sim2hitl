#ifndef SKS_CORE_H
#define SKS_CORE_H
/*
 * SkySurfer plant core: the 6DOF generated from FW_SkySurfer_HIL.slx (plant/core/build_core.m,
 * ERT Reusable function) behind a small reentrant C API.
 *
 *   controls[16] in  ->  CoreSnapshot[72] out (states, kinematics, forces/moments, air data,
 *                        atmosphere, actuators; layout below and in docs/MODEL_INTERFACE.md)
 *
 * Conventions
 *   - One SksCore per aircraft. Allocate sks_core_size() bytes (malloc alignment) per instance.
 *     Instances are independent: initial conditions, states and inputs live in the instance.
 *     Aircraft parameters (mass, aero tables, ...) are generated constants shared by all instances.
 *   - Instances may run in one process, stepped one call at a time. Not for concurrent calls from
 *     several threads (the generated code also initialises shared non-finite constants).
 *   - sks_core_step() writes the snapshot sampled at t_k, then integrates to t_k + dt (ode4,
 *     dt = 0.004 s): the same output phase as the HIL ABI.
 *   - Units are the source model's: SI, except angles marked _deg.
 *   - Standard C99 only.
 */
#include <stddef.h>
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif

#define SKS_CORE_API_VERSION 0x00010100u /* 1.1: continuous state access and f(x, u) for trim */
#define SKS_CORE_DT_S 0.004
#define SKS_CORE_CONTROL_COUNT 16
#define SKS_CORE_SNAPSHOT_COUNT 72
#define SKS_CORE_STATE_COUNT 21

#define SKS_CORE_OK 0
#define SKS_CORE_ERR_STATE 2    /* not initialised, or diverged earlier: re-initialise */
#define SKS_CORE_ERR_DIVERGED 3 /* non-finite snapshot; the instance must be re-initialised */
#define SKS_CORE_ERR_INPUT 4    /* null pointer or non-finite input */

/* controls[] index (same as the HIL ABI controls[0..4]); 5..15 are accepted and unused. */
enum {
  SKS_CORE_CTRL_AILERON_LEFT = 0,
  SKS_CORE_CTRL_AILERON_RIGHT = 1,
  SKS_CORE_CTRL_ELEVATOR = 2,
  SKS_CORE_CTRL_RUDDER = 3,
  SKS_CORE_CTRL_THROTTLE = 4
};

/* CoreSnapshot layout: first index of each group (0-based). Frames: NED earth (origin at the
 * initial ground point), FRD body. Forces in N, moments in N*m, all in body axes. */
enum {
  SKS_CORE_POSITION_NED_M = 0,        /* [3] Xe */
  SKS_CORE_VELOCITY_BODY_M_S = 3,     /* [3] Vb */
  SKS_CORE_QUATERNION = 6,            /* [4] q0..q3, body -> NED */
  SKS_CORE_RATES_BODY_RAD_S = 10,     /* [3] p q r */
  SKS_CORE_VELOCITY_NED_M_S = 13,     /* [3] Ve */
  SKS_CORE_EULER_RAD = 16,            /* [3] roll pitch yaw; yaw is the atan2 principal value [-pi, pi] */
  SKS_CORE_ANGULAR_ACCEL_RAD_S2 = 19, /* [3] pdot qdot rdot */
  SKS_CORE_ACCEL_BODY_M_S2 = 22,      /* [3] Ab: dVb/dt */
  SKS_CORE_ACCEL_NED_M_S2 = 25,       /* [3] Abe */
  SKS_CORE_FORCE_AERO_N = 28,         /* [3] after the airspeed > 5 m/s switch (what enters the sum) */
  SKS_CORE_MOMENT_AERO_NM = 31,       /* [3] same */
  SKS_CORE_FORCE_THRUST_N = 34,       /* [3] */
  SKS_CORE_MOMENT_THRUST_NM = 37,     /* [3] */
  SKS_CORE_FORCE_GROUND_N = 40,       /* [3] */
  SKS_CORE_FORCE_GRAVITY_N = 43,      /* [3] */
  SKS_CORE_FORCE_TOTAL_N = 46,        /* [3] aero + thrust + ground + gravity */
  SKS_CORE_MOMENT_TOTAL_NM = 49,      /* [3] aero + thrust */
  SKS_CORE_AIRSPEED_M_S = 52,         /* true airspeed */
  SKS_CORE_ALPHA_DEG = 53,
  SKS_CORE_BETA_DEG = 54,
  SKS_CORE_MACH = 55,
  SKS_CORE_AIR_VELOCITY_BODY_M_S = 56, /* [3] UVWc: body velocity relative to the air */
  SKS_CORE_AIR_RATES_BODY_RAD_S = 59,  /* [3] PQRc: body rates relative to the air */
  SKS_CORE_AIR_TEMPERATURE_K = 62,     /* ISA */
  SKS_CORE_SPEED_OF_SOUND_M_S = 63,
  SKS_CORE_STATIC_PRESSURE_PA = 64,
  SKS_CORE_AIR_DENSITY_KG_M3 = 65,
  SKS_CORE_SURFACE_DEG = 66,           /* [4] aileron_left aileron_right elevator rudder, after servo dynamics */
  SKS_CORE_THROTTLE = 70,              /* after the throttle lag */
  SKS_CORE_AERO_ACTIVE = 71            /* 1 when airspeed > 5 m/s */
};

/* Continuous states x[SKS_CORE_STATE_COUNT], in the generated order (ode4 integrates these):
 * position NED m [3], body velocity m/s [3], quaternion body -> NED [4], body rates rad/s [3],
 * the five actuator transfer-function states of the source ACTUATOR subsystem, driven by (checked with
 * sks_core_eval) throttle, right aileron, left aileron, elevator, rudder, then three gust distances
 * (zero without gusts). */
enum {
  SKS_CORE_X_POSITION_NED = 0,
  SKS_CORE_X_VELOCITY_BODY = 3,
  SKS_CORE_X_QUATERNION = 6,
  SKS_CORE_X_RATES_BODY = 10,
  SKS_CORE_X_ACTUATORS = 13, /* [5] throttle, aileron right, aileron left, elevator, rudder */
  SKS_CORE_X_GUST = 18       /* [3] */
};

/* Initial conditions in source units (exactly what the source model takes). */
typedef struct {
  double velocity_body_m_s[3]; /* U0 V0 W0 */
  double height_m;             /* H0, above the ground datum */
  double euler_deg[3];         /* Phi0 Theta0 Psi0 */
} SksCoreInitial;

typedef struct SksCore SksCore;

uint32_t sks_core_api_version(void);
size_t sks_core_size(void);

/* Initialise (or re-initialise) an instance at t = 0. */
int32_t sks_core_init(SksCore *core, const SksCoreInitial *initial);

/* Write the snapshot at t_k into snapshot (may be NULL), then advance one step with controls held. */
int32_t sks_core_step(SksCore *core, const double controls[SKS_CORE_CONTROL_COUNT],
                      double snapshot[SKS_CORE_SNAPSHOT_COUNT]);

/* Copy the complete state of src into dst (save, restore, branch). dst needs sks_core_size() bytes. */
int32_t sks_core_copy(SksCore *dst, const SksCore *src);

/* Read the continuous states. */
int32_t sks_core_get_state(const SksCore *core, double x[SKS_CORE_STATE_COUNT]);

/* State derivative f(x, u) for trim and linearisation. Writes x into core, applies controls and runs one
 * normal step: the snapshot (may be NULL) is the output at x, and xdot is the first ode4 stage f(t_k, x),
 * the same code path as the simulation. The core is advanced one step afterwards, so call this on a copy
 * (sks_core_copy) when the instance must stay unchanged. Continuing to step the core afterwards with the
 * same controls is an ordinary simulation started from x. */
int32_t sks_core_eval(SksCore *core, const double x[SKS_CORE_STATE_COUNT],
                      const double controls[SKS_CORE_CONTROL_COUNT], double xdot[SKS_CORE_STATE_COUNT],
                      double snapshot[SKS_CORE_SNAPSHOT_COUNT]);

/* Time of the next snapshot, in steps and seconds. */
uint64_t sks_core_step_index(const SksCore *core);
double sks_core_time_s(const SksCore *core);

#ifdef __cplusplus
}
#endif
#endif
