/* Reentrant wrapper around the generated SkySurfer_Core (ERT Reusable function). See sks_core.h. */
#include "sks_core.h"

#include <math.h>
#include <string.h>

#include "SkySurfer_Core_private.h" /* generated; also defines the rtm access macros */

struct SksCore {
  RT_MODEL_SkySurfer_Core_T model;
  DW_SkySurfer_Core_T dwork;
  X_SkySurfer_Core_T states;
  XDot_SkySurfer_Core_T derivatives;
  XDis_SkySurfer_Core_T disabled;
  ExtU_SkySurfer_Core_T input;
  ExtY_SkySurfer_Core_T output;
  SksCoreInitial initial;
  uint64_t step_index;
  uint32_t ready;
  uint32_t diverged;
};

/* Point the model at this instance's own data. Mirrors the pointer setup of the generated
 * SkySurfer_Core_initialize(), so that a byte copy of an instance can be made self-consistent. */
static void bind(SksCore *core) {
  RT_MODEL_SkySurfer_Core_T *m = &core->model;
  m->dwork = &core->dwork;
  m->contStates = &core->states;
  m->derivs = (double *)&core->derivatives;
  m->contStateDisabled = &core->disabled;
  rtsiSetSimTimeStepPtr(&m->solverInfo, &m->Timing.simTimeStep);
  rtsiSetTPtr(&m->solverInfo, &rtmGetTPtr(m));
  rtsiSetStepSizePtr(&m->solverInfo, &m->Timing.stepSize0);
  rtsiSetdXPtr(&m->solverInfo, &m->derivs);
  rtsiSetContStatesPtr(&m->solverInfo, (double **)&m->contStates);
  rtsiSetNumContStatesPtr(&m->solverInfo, &m->Sizes.numContStates);
  rtsiSetNumPeriodicContStatesPtr(&m->solverInfo, &m->Sizes.numPeriodicContStates);
  rtsiSetPeriodicContStateIndicesPtr(&m->solverInfo, &m->periodicContStateIndices);
  rtsiSetPeriodicContStateRangesPtr(&m->solverInfo, &m->periodicContStateRanges);
  rtsiSetContStateDisabledPtr(&m->solverInfo, (bool **)&m->contStateDisabled);
  rtsiSetErrorStatusPtr(&m->solverInfo, (&rtmGetErrorStatus(m)));
  rtsiSetRTModelPtr(&m->solverInfo, m);
  m->intgData.y = m->odeY;
  m->intgData.f[0] = m->odeF[0];
  m->intgData.f[1] = m->odeF[1];
  m->intgData.f[2] = m->odeF[2];
  m->intgData.f[3] = m->odeF[3];
  rtsiSetSolverData(&m->solverInfo, (void *)&m->intgData);
  rtmSetTPtr(m, &m->Timing.tArray[0]);
}

static void set_initial(SksCore *core) {
  const SksCoreInitial *ic = &core->initial;
  double *u = core->input.InitialConditions; /* [U0 V0 W0 H0 Phi0 Theta0 Psi0] */
  u[0] = ic->velocity_body_m_s[0];
  u[1] = ic->velocity_body_m_s[1];
  u[2] = ic->velocity_body_m_s[2];
  u[3] = ic->height_m;
  u[4] = ic->euler_deg[0];
  u[5] = ic->euler_deg[1];
  u[6] = ic->euler_deg[2];
}

uint32_t sks_core_api_version(void) { return SKS_CORE_API_VERSION; }

size_t sks_core_size(void) { return sizeof(SksCore); }

int32_t sks_core_init(SksCore *core, const SksCoreInitial *initial) {
  if (core == NULL || initial == NULL) return SKS_CORE_ERR_INPUT;
  const double *values = (const double *)initial;
  for (size_t k = 0; k < sizeof(SksCoreInitial) / sizeof(double); k++) {
    if (!isfinite(values[k])) return SKS_CORE_ERR_INPUT;
  }
  memset(core, 0, sizeof(*core));
  core->initial = *initial;
  bind(core);
  SkySurfer_Core_initialize(&core->model, &core->input, &core->output);
  set_initial(core); /* initialize() clears the inputs */
  core->ready = 1;
  return SKS_CORE_OK;
}

int32_t sks_core_step(SksCore *core, const double controls[SKS_CORE_CONTROL_COUNT],
                      double snapshot[SKS_CORE_SNAPSHOT_COUNT]) {
  if (core == NULL || controls == NULL) return SKS_CORE_ERR_INPUT;
  if (!core->ready || core->diverged) return SKS_CORE_ERR_STATE;
  for (int k = 0; k < SKS_CORE_CONTROL_COUNT; k++) {
    if (!isfinite(controls[k])) return SKS_CORE_ERR_INPUT;
  }
  memcpy(core->input.Controls, controls, sizeof(core->input.Controls));
  SkySurfer_Core_step(&core->model, &core->input, &core->output);
  core->step_index++;
  for (int k = 0; k < SKS_CORE_SNAPSHOT_COUNT; k++) {
    if (!isfinite(core->output.CoreSnapshot[k])) {
      core->diverged = 1;
      return SKS_CORE_ERR_DIVERGED;
    }
  }
  if (snapshot != NULL) memcpy(snapshot, core->output.CoreSnapshot, sizeof(core->output.CoreSnapshot));
  return SKS_CORE_OK;
}

int32_t sks_core_copy(SksCore *dst, const SksCore *src) {
  if (dst == NULL || src == NULL) return SKS_CORE_ERR_INPUT;
  if (dst == src) return SKS_CORE_OK;
  memcpy(dst, src, sizeof(*dst));
  bind(dst);
  return SKS_CORE_OK;
}

_Static_assert(sizeof(X_SkySurfer_Core_T) == SKS_CORE_STATE_COUNT * sizeof(double), "continuous state count changed");

int32_t sks_core_get_state(const SksCore *core, double x[SKS_CORE_STATE_COUNT]) {
  if (core == NULL || x == NULL) return SKS_CORE_ERR_INPUT;
  if (!core->ready) return SKS_CORE_ERR_STATE;
  memcpy(x, &core->states, sizeof(core->states));
  return SKS_CORE_OK;
}

int32_t sks_core_eval(SksCore *core, const double x[SKS_CORE_STATE_COUNT],
                      const double controls[SKS_CORE_CONTROL_COUNT], double xdot[SKS_CORE_STATE_COUNT],
                      double snapshot[SKS_CORE_SNAPSHOT_COUNT]) {
  if (core == NULL || x == NULL || xdot == NULL) return SKS_CORE_ERR_INPUT;
  if (!core->ready) return SKS_CORE_ERR_STATE;
  for (int k = 0; k < SKS_CORE_STATE_COUNT; k++) {
    if (!isfinite(x[k])) return SKS_CORE_ERR_INPUT;
  }
  memcpy(&core->states, x, sizeof(core->states));
  core->diverged = 0;
  int32_t code = sks_core_step(core, controls, snapshot);
  /* The generated ode4 stores f(t_k, x) in its first stage buffer before integrating. */
  memcpy(xdot, core->model.odeF[0], sizeof(double) * SKS_CORE_STATE_COUNT);
  if (code != SKS_CORE_OK) return code;
  for (int k = 0; k < SKS_CORE_STATE_COUNT; k++) {
    if (!isfinite(xdot[k])) return SKS_CORE_ERR_DIVERGED;
  }
  return SKS_CORE_OK;
}

uint64_t sks_core_step_index(const SksCore *core) { return core == NULL ? 0 : core->step_index; }

double sks_core_time_s(const SksCore *core) {
  return core == NULL ? 0.0 : (double)core->step_index * SKS_CORE_DT_S;
}
