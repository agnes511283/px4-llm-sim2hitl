/* Minimal stand-in for MATLAB's rtw_solver.h, used only when no MATLAB installation is found
 * (plant/core/toolchain.py rtw_include_dirs). Written for this project from what the generated
 * SkySurfer_Core (ERT, fixed-step ode4) and plant/core/plant_core.c use: the solver object only
 * points at fields of the model (time, step size, states, derivatives) and carries two flags that
 * the model sets false at initialization. It is not a MathWorks file. The plant gates of
 * `./runbridge update-model` decide whether a build with it is right. See plant/README.md. */
#ifndef PLANT_RTW_SOLVER_H
#define PLANT_RTW_SOLVER_H

#include <stdbool.h>

#include "rtw_continuous.h"

typedef struct {
  SimTimeStep *simTimeStepPtr;
  double **tPtr;
  double *stepSizePtr;
  double **dXPtr;
  double **contStatesPtr;
  int *numContStatesPtr;
  int *numPeriodicContStatesPtr;
  int **periodicContStateIndicesPtr;
  double **periodicContStateRangesPtr;
  bool **contStateDisabledPtr;
  const char **errStatusPtr;
  void *rtModelPtr;
  void *solverData;
  const char *solverName;
  double solverStopTime;
  bool isMinorTimeStepWithModeChange;
  bool isContModeFrozen;
  bool blockStateForSolverChangedAtMajorStep;
} RTWSolverInfo;

/* Wiring (model initialization and plant_core.c bind()) */
#define rtsiSetSimTimeStepPtr(S, p) ((S)->simTimeStepPtr = (p))
#define rtsiSetTPtr(S, p) ((S)->tPtr = (p))
#define rtsiSetStepSizePtr(S, p) ((S)->stepSizePtr = (p))
#define rtsiSetdXPtr(S, p) ((S)->dXPtr = (p))
#define rtsiSetContStatesPtr(S, p) ((S)->contStatesPtr = (p))
#define rtsiSetNumContStatesPtr(S, p) ((S)->numContStatesPtr = (p))
#define rtsiSetNumPeriodicContStatesPtr(S, p) ((S)->numPeriodicContStatesPtr = (p))
#define rtsiSetPeriodicContStateIndicesPtr(S, p) ((S)->periodicContStateIndicesPtr = (p))
#define rtsiSetPeriodicContStateRangesPtr(S, p) ((S)->periodicContStateRangesPtr = (p))
#define rtsiSetContStateDisabledPtr(S, p) ((S)->contStateDisabledPtr = (p))
#define rtsiSetErrorStatusPtr(S, p) ((S)->errStatusPtr = (p))
#define rtsiSetRTModelPtr(S, p) ((S)->rtModelPtr = (void *)(p))
#define rtsiSetSolverData(S, p) ((S)->solverData = (p))
#define rtsiGetSolverData(S) ((S)->solverData)
#define rtsiSetSolverName(S, n) ((S)->solverName = (n))

/* Time, step size, states and derivatives seen through the model's own fields */
#define rtsiSetSimTimeStep(S, v) (*((S)->simTimeStepPtr) = (v))
#define rtsiGetSimTimeStep(S) (*((S)->simTimeStepPtr))
#define rtsiGetT(S) ((*((S)->tPtr))[0])
#define rtsiSetT(S, t) ((*((S)->tPtr))[0] = (t))
#define rtsiGetStepSize(S) (*((S)->stepSizePtr))
#define rtsiSetdX(S, dx) (*((S)->dXPtr) = (dx))
#define rtsiGetContStates(S) (*((S)->contStatesPtr))
#define rtsiSetSolverStopTime(S, t) ((S)->solverStopTime = (t))
#define rtsiGetSolverStopTime(S) ((S)->solverStopTime)

/* Modes (If/Enable subsystems) change only on a major step; the two flags stay false for ode4. */
#define rtsiSetIsMinorTimeStepWithModeChange(S, v) ((S)->isMinorTimeStepWithModeChange = (v))
#define rtsiSetIsContModeFrozen(S, v) ((S)->isContModeFrozen = (v))
#define rtsiIsModeUpdateTimeStep(S) \
  ((rtsiGetSimTimeStep(S) == MAJOR_TIME_STEP && !(S)->isContModeFrozen) || (S)->isMinorTimeStepWithModeChange)
/* Read only by variable-step solvers; recorded for completeness. */
#define rtsiSetBlockStateForSolverChangedAtMajorStep(S, v) ((S)->blockStateForSolverChangedAtMajorStep = (v))

#endif
