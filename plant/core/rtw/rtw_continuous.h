/* Minimal stand-in for MATLAB's rtw_continuous.h, used only when no MATLAB installation is found
 * (plant/core/toolchain.py rtw_include_dirs). Written for this project from what the generated
 * SkySurfer_Core (ERT, fixed-step ode4) uses; it is not a MathWorks file. The plant gates of
 * `./runbridge update-model` decide whether a build with it is right. See plant/README.md. */
#ifndef PLANT_RTW_CONTINUOUS_H
#define PLANT_RTW_CONTINUOUS_H

/* Major step: outputs, modes and states advance; minor step: the solver's intermediate evaluations. */
typedef enum { MINOR_TIME_STEP, MAJOR_TIME_STEP } SimTimeStep;

#endif
