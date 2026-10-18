/*
 * Academic License - for use in teaching, academic research, and meeting
 * course requirements at degree granting institutions only.  Not for
 * government, commercial, or other organizational use.
 *
 * File: SkySurfer_Core.c
 *
 * Code generated for Simulink model 'SkySurfer_Core'.
 *
 * Model version                  : 14.9
 * Simulink Coder version         : 26.2 (R2026b) 22-May-2026
 * C/C++ source code generated on : Sun Oct 18 16:10:01 2026
 *
 * Target selection: ert.tlc
 * Embedded hardware selection: Intel->x86-64 (Linux 64)
 * Code generation objectives: Unspecified
 * Validation result: Not run
 */

#include "SkySurfer_Core.h"
#include <stdbool.h>
#include "SkySurfer_Core_private.h"
#include <emmintrin.h>
#include <math.h>
#include <string.h>
#include "rt_assert.h"
#include <stdint.h>
#include "rt_nonfinite.h"
#include "rt_defines.h"

double look1_binlcpw(double u0, const double bp0[], const double table[],
                     uint32_t maxIndex)
{
  double frac;
  double yL_0d0;
  uint32_t bpIdx;
  uint32_t iLeft;
  uint32_t iRght;

  /* Column-major Lookup 1-D
     Search method: 'binary'
     Use previous index: 'off'
     Interpolation method: 'Linear point-slope'
     Extrapolation method: 'Clip'
     Use last breakpoint for index at or above upper limit: 'off'
     Remove protection against out-of-range input in generated code: 'off'
   */
  /* Prelookup - Index and Fraction
     Index Search method: 'binary'
     Extrapolation method: 'Clip'
     Use previous index: 'off'
     Use last breakpoint for index at or above upper limit: 'off'
     Remove protection against out-of-range input in generated code: 'off'
   */
  if (u0 <= bp0[0U]) {
    iLeft = 0U;
    frac = 0.0;
  } else if (u0 < bp0[maxIndex]) {
    /* Binary Search */
    bpIdx = maxIndex >> 1U;
    iLeft = 0U;
    iRght = maxIndex;
    while (iRght - iLeft > 1U) {
      if (u0 < bp0[bpIdx]) {
        iRght = bpIdx;
      } else {
        iLeft = bpIdx;
      }

      bpIdx = (iRght + iLeft) >> 1U;
    }

    frac = (u0 - bp0[iLeft]) / (bp0[iLeft + 1U] - bp0[iLeft]);
  } else {
    iLeft = maxIndex - 1U;
    frac = 1.0;
  }

  /* Column-major Interpolation 1-D
     Interpolation method: 'Linear point-slope'
     Use last breakpoint for index at or above upper limit: 'off'
     Overflow mode: 'portable wrapping'
   */
  yL_0d0 = table[iLeft];
  return (table[iLeft + 1U] - yL_0d0) * frac + yL_0d0;
}

uint32_t plook_binx(double u, const double bp[], uint32_t maxIndex, double
                    *fraction)
{
  uint32_t bpIndex;

  /* Prelookup - Index and Fraction
     Index Search method: 'binary'
     Extrapolation method: 'Linear'
     Use previous index: 'off'
     Use last breakpoint for index at or above upper limit: 'off'
     Remove protection against out-of-range input in generated code: 'off'
   */
  if (u <= bp[0U]) {
    bpIndex = 0U;
    *fraction = (u - bp[0U]) / (bp[1U] - bp[0U]);
  } else if (u < bp[maxIndex]) {
    bpIndex = binsearch_u32d(u, bp, maxIndex >> 1U, maxIndex);
    *fraction = (u - bp[bpIndex]) / (bp[bpIndex + 1U] - bp[bpIndex]);
  } else {
    bpIndex = maxIndex - 1U;
    *fraction = (u - bp[maxIndex - 1U]) / (bp[maxIndex] - bp[maxIndex - 1U]);
  }

  return bpIndex;
}

double intrp3d_l_pw(const uint32_t bpIndex[], const double frac[], const double
                    table[], const uint32_t stride[])
{
  double yL_0d0;
  double yL_1d;
  double yL_2d;
  uint32_t offset_0d;
  uint32_t offset_2d;

  /* Column-major Interpolation 3-D
     Interpolation method: 'Linear point-slope'
     Use last breakpoint for index at or above upper limit: 'off'
     Overflow mode: 'portable wrapping'
   */
  offset_2d = (bpIndex[2U] * stride[2U] + bpIndex[1U] * stride[1U]) + bpIndex[0U];
  yL_0d0 = table[offset_2d];
  yL_1d = (table[offset_2d + 1U] - yL_0d0) * frac[0U] + yL_0d0;
  offset_0d = offset_2d + stride[1U];
  yL_0d0 = table[offset_0d];
  yL_2d = (((table[offset_0d + 1U] - yL_0d0) * frac[0U] + yL_0d0) - yL_1d) *
    frac[1U] + yL_1d;
  offset_2d += stride[2U];
  yL_0d0 = table[offset_2d];
  yL_1d = (table[offset_2d + 1U] - yL_0d0) * frac[0U] + yL_0d0;
  offset_0d = offset_2d + stride[1U];
  yL_0d0 = table[offset_0d];
  return (((((table[offset_0d + 1U] - yL_0d0) * frac[0U] + yL_0d0) - yL_1d) *
           frac[1U] + yL_1d) - yL_2d) * frac[2U] + yL_2d;
}

uint32_t plook_binc(double u, const double bp[], uint32_t maxIndex, double
                    *fraction)
{
  uint32_t bpIndex;

  /* Prelookup - Index and Fraction
     Index Search method: 'binary'
     Extrapolation method: 'Clip'
     Use previous index: 'off'
     Use last breakpoint for index at or above upper limit: 'off'
     Remove protection against out-of-range input in generated code: 'off'
   */
  if (u <= bp[0U]) {
    bpIndex = 0U;
    *fraction = 0.0;
  } else if (u < bp[maxIndex]) {
    bpIndex = binsearch_u32d(u, bp, maxIndex >> 1U, maxIndex);
    *fraction = (u - bp[bpIndex]) / (bp[bpIndex + 1U] - bp[bpIndex]);
  } else {
    bpIndex = maxIndex - 1U;
    *fraction = 1.0;
  }

  return bpIndex;
}

uint32_t binsearch_u32d(double u, const double bp[], uint32_t startIndex,
  uint32_t maxIndex)
{
  uint32_t bpIdx;
  uint32_t bpIndex;
  uint32_t iRght;

  /* Binary Search */
  bpIdx = startIndex;
  bpIndex = 0U;
  iRght = maxIndex;
  while (iRght - bpIndex > 1U) {
    if (u < bp[bpIdx]) {
      iRght = bpIdx;
    } else {
      bpIndex = bpIdx;
    }

    bpIdx = (iRght + bpIndex) >> 1U;
  }

  return bpIndex;
}

/*
 * This function updates continuous states using the ODE4 fixed-step
 * solver algorithm
 */
static void rt_ertODEUpdateContinuousStates(RTWSolverInfo *si ,
  RT_MODEL_SkySurfer_Core_T *const SkySurfer_Core_M, ExtU_SkySurfer_Core_T
  *SkySurfer_Core_U, ExtY_SkySurfer_Core_T *SkySurfer_Core_Y)
{
  double t = rtsiGetT(si);
  double tnew = rtsiGetSolverStopTime(si);
  double h = rtsiGetStepSize(si);
  double *x = rtsiGetContStates(si);
  ODE4_IntgData *id = (ODE4_IntgData *)rtsiGetSolverData(si);
  double *y = id->y;
  double *f0 = id->f[0];
  double *f1 = id->f[1];
  double *f2 = id->f[2];
  double *f3 = id->f[3];
  double temp;
  int i;
  int nXc = 21;
  rtsiSetSimTimeStep(si,MINOR_TIME_STEP);

  /* Save the state values at time t in y, we'll use x as ynew. */
  (void) memcpy(y, x,
                (unsigned int)nXc*sizeof(double));

  /* Assumes that rtsiSetT and ModelOutputs are up-to-date */
  /* f0 = f(t,y) */
  rtsiSetdX(si, f0);
  SkySurfer_Core_derivatives(SkySurfer_Core_M);

  /* f1 = f(t + (h/2), y + (h/2)*f0) */
  temp = 0.5 * h;
  for (i = 0; i < nXc; i++) {
    x[i] = y[i] + (temp*f0[i]);
  }

  rtsiSetT(si, t + temp);
  rtsiSetdX(si, f1);
  SkySurfer_Core_step(SkySurfer_Core_M, SkySurfer_Core_U, SkySurfer_Core_Y);
  SkySurfer_Core_derivatives(SkySurfer_Core_M);

  /* f2 = f(t + (h/2), y + (h/2)*f1) */
  for (i = 0; i < nXc; i++) {
    x[i] = y[i] + (temp*f1[i]);
  }

  rtsiSetdX(si, f2);
  SkySurfer_Core_step(SkySurfer_Core_M, SkySurfer_Core_U, SkySurfer_Core_Y);
  SkySurfer_Core_derivatives(SkySurfer_Core_M);

  /* f3 = f(t + h, y + h*f2) */
  for (i = 0; i < nXc; i++) {
    x[i] = y[i] + (h*f2[i]);
  }

  rtsiSetT(si, tnew);
  rtsiSetdX(si, f3);
  SkySurfer_Core_step(SkySurfer_Core_M, SkySurfer_Core_U, SkySurfer_Core_Y);
  SkySurfer_Core_derivatives(SkySurfer_Core_M);

  /* tnew = t + h
     ynew = y + (h/6)*(f0 + 2*f1 + 2*f2 + 2*f3) */
  temp = h / 6.0;
  for (i = 0; i < nXc; i++) {
    x[i] = y[i] + temp*(f0[i] + 2.0*f1[i] + 2.0*f2[i] + f3[i]);
  }

  rtsiSetSimTimeStep(si,MAJOR_TIME_STEP);
}

/*
 * System initialize for enable system:
 *    '<S140>/Distance into gust (y)'
 *    '<S140>/Distance into gust (z)'
 */
void SkySurfer_Core_Distanceintogusty_Init(double *rty_x,
  P_Distanceintogusty_SkySurfer_Core_T *localP,
  X_Distanceintogusty_SkySurfer_Core_T *localX)
{
  /* InitializeConditions for Integrator: '<S145>/Distance into Gust (x) (Limited to gust length d) ' */
  localX->DistanceintoGustxLimitedtogustlengthd_CSTATE =
    localP->DistanceintoGustxLimitedtogustlengthd_IC;

  /* SystemInitialize for Outport: '<S145>/x' */
  *rty_x = localP->x_Y0;
}

/*
 * System reset for enable system:
 *    '<S140>/Distance into gust (y)'
 *    '<S140>/Distance into gust (z)'
 */
void SkySurfer_Core_Distanceintogusty_Reset(P_Distanceintogusty_SkySurfer_Core_T
  *localP, X_Distanceintogusty_SkySurfer_Core_T *localX)
{
  /* InitializeConditions for Integrator: '<S145>/Distance into Gust (x) (Limited to gust length d) ' */
  localX->DistanceintoGustxLimitedtogustlengthd_CSTATE =
    localP->DistanceintoGustxLimitedtogustlengthd_IC;
}

/*
 * Disable for enable system:
 *    '<S140>/Distance into gust (y)'
 *    '<S140>/Distance into gust (z)'
 */
void SkySurfer_Core_Distanceintogusty_Disable
  (DW_Distanceintogusty_SkySurfer_Core_T *localDW)
{
  localDW->Distanceintogusty_MODE = false;
}

/*
 * Outputs for enable system:
 *    '<S140>/Distance into gust (y)'
 *    '<S140>/Distance into gust (z)'
 */
void SkySurfer_Core_Distanceintogusty(RT_MODEL_SkySurfer_Core_T * const
  SkySurfer_Core_M, bool rtu_Enable, double *rty_x, double rtp_d_m,
  DW_Distanceintogusty_SkySurfer_Core_T *localDW,
  P_Distanceintogusty_SkySurfer_Core_T *localP,
  X_Distanceintogusty_SkySurfer_Core_T *localX,
  XDis_Distanceintogusty_SkySurfer_Core_T *localXdis)
{
  /* Outputs for Enabled SubSystem: '<S140>/Distance into gust (y)' incorporates:
   *  EnablePort: '<S145>/Enable'
   */
  if (rtmIsMajorTimeStep(SkySurfer_Core_M) && rtsiIsModeUpdateTimeStep
      (&SkySurfer_Core_M->solverInfo)) {
    if (rtu_Enable) {
      if (!localDW->Distanceintogusty_MODE) {
        (void) memset(&(localXdis->DistanceintoGustxLimitedtogustlengthd_CSTATE),
                      0,
                      1*sizeof(bool));
        SkySurfer_Core_Distanceintogusty_Reset(localP, localX);
        localDW->Distanceintogusty_MODE = true;
      }
    } else {
      /* Outputs for Enabled SubSystem: '<S140>/Distance into gust (x)' incorporates:
       *  EnablePort: '<S144>/Enable'
       */
      if (((SkySurfer_Core_M->Timing.clockTick1) * 0.004) == rtmGetTStart
          (SkySurfer_Core_M)) {
        (void) memset(&(localXdis->DistanceintoGustxLimitedtogustlengthd_CSTATE),
                      1,
                      1*sizeof(bool));
      }

      /* End of Outputs for SubSystem: '<S140>/Distance into gust (x)' */
      if (localDW->Distanceintogusty_MODE) {
        (void) memset(&(localXdis->DistanceintoGustxLimitedtogustlengthd_CSTATE),
                      1,
                      1*sizeof(bool));
        SkySurfer_Core_Distanceintogusty_Disable(localDW);
      }
    }
  }

  if (localDW->Distanceintogusty_MODE) {
    /* Integrator: '<S145>/Distance into Gust (x) (Limited to gust length d) ' */
    /* Limited  Integrator  */
    if (localX->DistanceintoGustxLimitedtogustlengthd_CSTATE >= rtp_d_m) {
      localX->DistanceintoGustxLimitedtogustlengthd_CSTATE = rtp_d_m;
    } else if (localX->DistanceintoGustxLimitedtogustlengthd_CSTATE <=
               localP->DistanceintoGustxLimitedtogustlengthd_LowerSat) {
      localX->DistanceintoGustxLimitedtogustlengthd_CSTATE =
        localP->DistanceintoGustxLimitedtogustlengthd_LowerSat;
    }

    *rty_x = localX->DistanceintoGustxLimitedtogustlengthd_CSTATE;

    /* End of Integrator: '<S145>/Distance into Gust (x) (Limited to gust length d) ' */
  }

  /* End of Outputs for SubSystem: '<S140>/Distance into gust (y)' */
}

/*
 * Derivatives for enable system:
 *    '<S140>/Distance into gust (y)'
 *    '<S140>/Distance into gust (z)'
 */
void SkySurfer_Core_Distanceintogusty_Deriv(double rtu_V, double rtp_d_m,
  DW_Distanceintogusty_SkySurfer_Core_T *localDW,
  P_Distanceintogusty_SkySurfer_Core_T *localP,
  X_Distanceintogusty_SkySurfer_Core_T *localX,
  XDot_Distanceintogusty_SkySurfer_Core_T *localXdot)
{
  bool lsat;
  bool usat;
  if (localDW->Distanceintogusty_MODE) {
    /* Derivatives for Integrator: '<S145>/Distance into Gust (x) (Limited to gust length d) ' */
    lsat = (localX->DistanceintoGustxLimitedtogustlengthd_CSTATE <=
            localP->DistanceintoGustxLimitedtogustlengthd_LowerSat);
    usat = (localX->DistanceintoGustxLimitedtogustlengthd_CSTATE >= rtp_d_m);
    if ((!lsat && !usat) || (lsat && (rtu_V > 0.0)) || (usat && (rtu_V < 0.0)))
    {
      localXdot->DistanceintoGustxLimitedtogustlengthd_CSTATE = rtu_V;
    } else {
      /* in saturation */
      localXdot->DistanceintoGustxLimitedtogustlengthd_CSTATE = 0.0;
    }

    /* End of Derivatives for Integrator: '<S145>/Distance into Gust (x) (Limited to gust length d) ' */
  } else {
    localXdot->DistanceintoGustxLimitedtogustlengthd_CSTATE = 0.0;
  }
}

double rt_atan2d_snf(double u0, double u1)
{
  double y;
  int32_t tmp;
  int32_t tmp_0;
  if (rtIsNaN(u0) || rtIsNaN(u1)) {
    y = (rtNaN);
  } else if (rtIsInf(u0) && rtIsInf(u1)) {
    if (u0 > 0.0) {
      tmp = 1;
    } else {
      tmp = -1;
    }

    if (u1 > 0.0) {
      tmp_0 = 1;
    } else {
      tmp_0 = -1;
    }

    y = atan2(tmp, tmp_0);
  } else if (u1 == 0.0) {
    if (u0 > 0.0) {
      y = RT_PI / 2.0;
    } else if (u0 < 0.0) {
      y = -(RT_PI / 2.0);
    } else {
      y = 0.0;
    }
  } else {
    y = atan2(u0, u1);
  }

  return y;
}

double rt_powd_snf(double u0, double u1)
{
  double tmp;
  double tmp_0;
  double y;
  if (rtIsNaN(u0) || rtIsNaN(u1)) {
    y = (rtNaN);
  } else {
    tmp = fabs(u0);
    tmp_0 = fabs(u1);
    if (rtIsInf(u1)) {
      if (tmp == 1.0) {
        y = 1.0;
      } else if (tmp > 1.0) {
        if (u1 > 0.0) {
          y = (rtInf);
        } else {
          y = 0.0;
        }
      } else if (u1 > 0.0) {
        y = 0.0;
      } else {
        y = (rtInf);
      }
    } else if (tmp_0 == 0.0) {
      y = 1.0;
    } else if (tmp_0 == 1.0) {
      if (u1 > 0.0) {
        y = u0;
      } else {
        y = 1.0 / u0;
      }
    } else if (u1 == 2.0) {
      y = u0 * u0;
    } else if ((u1 == 0.5) && (u0 >= 0.0)) {
      y = sqrt(u0);
    } else if ((u0 < 0.0) && (u1 > floor(u1))) {
      y = (rtNaN);
    } else {
      y = pow(u0, u1);
    }
  }

  return y;
}

void rt_mrdivide_U1d1x3_U2d3x3_Yd1x3_snf(const double u0[3], const double u1[9],
  double y[3])
{
  double A[9];
  double a21;
  double maxval;
  int32_t r1;
  int32_t r2;
  int32_t r3;
  int32_t rtemp;
  memcpy(&A[0], &u1[0], 9U * sizeof(double));
  r1 = 0;
  r2 = 1;
  r3 = 2;
  maxval = fabs(u1[0]);
  a21 = fabs(u1[1]);
  if (a21 > maxval) {
    maxval = a21;
    r1 = 1;
    r2 = 0;
  }

  if (fabs(u1[2]) > maxval) {
    r1 = 2;
    r2 = 1;
    r3 = 0;
  }

  A[r2] = u1[r2] / u1[r1];
  A[r3] /= A[r1];
  A[r2 + 3] -= A[r1 + 3] * A[r2];
  A[r3 + 3] -= A[r1 + 3] * A[r3];
  A[r2 + 6] -= A[r1 + 6] * A[r2];
  A[r3 + 6] -= A[r1 + 6] * A[r3];
  if (fabs(A[r3 + 3]) > fabs(A[r2 + 3])) {
    rtemp = r2 + 1;
    r2 = r3;
    r3 = rtemp - 1;
  }

  A[r3 + 3] /= A[r2 + 3];
  A[r3 + 6] -= A[r3 + 3] * A[r2 + 6];
  y[r1] = u0[0] / A[r1];
  y[r2] = u0[1] - A[r1 + 3] * y[r1];
  y[r3] = u0[2] - A[r1 + 6] * y[r1];
  y[r2] /= A[r2 + 3];
  y[r3] -= A[r2 + 6] * y[r2];
  y[r3] /= A[r3 + 6];
  y[r2] -= A[r3 + 3] * y[r3];
  y[r1] -= y[r3] * A[r3];
  y[r1] -= y[r2] * A[r2];
}

/* Model step function */
void SkySurfer_Core_step(RT_MODEL_SkySurfer_Core_T *const SkySurfer_Core_M,
  ExtU_SkySurfer_Core_T *SkySurfer_Core_U, ExtY_SkySurfer_Core_T
  *SkySurfer_Core_Y)
{
  DW_SkySurfer_Core_T *SkySurfer_Core_DW = SkySurfer_Core_M->dwork;
  X_SkySurfer_Core_T *SkySurfer_Core_X = SkySurfer_Core_M->contStates;
  XDis_SkySurfer_Core_T *SkySurfer_Core_XDis = ((XDis_SkySurfer_Core_T *)
    SkySurfer_Core_M->contStateDisabled);
  __m128d tmp_1;
  XDis_SkySurfer_Core_T *_rtXdis;
  double CoreSnapshot_Concat[72];
  double rtb_MatrixConcatenation[18];
  double rtb_Reshape9to3x3columnmajor[9];
  double rtb_VectorConcatenate_k[9];
  double fractions[3];
  double fractions_0[3];
  double fractions_1[3];
  double fractions_10[3];
  double fractions_11[3];
  double fractions_12[3];
  double fractions_13[3];
  double fractions_14[3];
  double fractions_15[3];
  double fractions_16[3];
  double fractions_17[3];
  double fractions_18[3];
  double fractions_19[3];
  double fractions_1a[3];
  double fractions_1b[3];
  double fractions_1c[3];
  double fractions_1d[3];
  double fractions_1e[3];
  double fractions_1f[3];
  double fractions_1g[3];
  double fractions_1h[3];
  double fractions_1i[3];
  double fractions_1j[3];
  double fractions_1k[3];
  double fractions_1l[3];
  double fractions_1m[3];
  double fractions_1n[3];
  double fractions_1o[3];
  double fractions_1p[3];
  double fractions_1q[3];
  double fractions_1r[3];
  double fractions_1s[3];
  double fractions_1t[3];
  double fractions_1u[3];
  double fractions_1v[3];
  double fractions_1w[3];
  double fractions_1x[3];
  double fractions_1y[3];
  double fractions_1z[3];
  double fractions_2[3];
  double fractions_20[3];
  double fractions_21[3];
  double fractions_22[3];
  double fractions_23[3];
  double fractions_24[3];
  double fractions_25[3];
  double fractions_26[3];
  double fractions_27[3];
  double fractions_28[3];
  double fractions_29[3];
  double fractions_2a[3];
  double fractions_2b[3];
  double fractions_2c[3];
  double fractions_2d[3];
  double fractions_2e[3];
  double fractions_2f[3];
  double fractions_2g[3];
  double fractions_2h[3];
  double fractions_2i[3];
  double fractions_2j[3];
  double fractions_2k[3];
  double fractions_3[3];
  double fractions_4[3];
  double fractions_5[3];
  double fractions_6[3];
  double fractions_7[3];
  double fractions_8[3];
  double fractions_9[3];
  double fractions_a[3];
  double fractions_b[3];
  double fractions_c[3];
  double fractions_d[3];
  double fractions_e[3];
  double fractions_f[3];
  double fractions_g[3];
  double fractions_h[3];
  double fractions_i[3];
  double fractions_j[3];
  double fractions_k[3];
  double fractions_l[3];
  double fractions_m[3];
  double fractions_n[3];
  double fractions_o[3];
  double fractions_p[3];
  double fractions_q[3];
  double fractions_r[3];
  double fractions_s[3];
  double fractions_t[3];
  double fractions_u[3];
  double fractions_v[3];
  double fractions_w[3];
  double fractions_x[3];
  double fractions_y[3];
  double fractions_z[3];
  double rtb_Add1_m[3];
  double rtb_MatrixMultiply[3];
  double rtb_u[3];
  double tmp_0[2];
  double frac;
  double pData_idx_0;
  double pData_idx_0_tmp;
  double pData_idx_1;
  double rtb_Add4_idx_1;
  double rtb_Add4_idx_2;
  double rtb_Add_h_idx_2;
  double rtb_Airspeed;
  double rtb_Airspeed_tmp;
  double rtb_DotProduct;
  double rtb_Gain;
  double rtb_Gain3;
  double rtb_Gain4;
  double rtb_Gain5;
  double rtb_Gain8;
  double rtb_Gain_az;
  double rtb_Gain_h;
  double rtb_Merge_idx_0;
  double rtb_Merge_idx_1;
  double rtb_Merge_idx_2;
  double rtb_Multiply2;
  double rtb_Multiply5_o;
  double rtb_Product14;
  double rtb_Product14_d;
  double rtb_Product14_hm;
  double rtb_Product14_k;
  double rtb_Product16;
  double rtb_Product16_a;
  double rtb_Product16_j;
  double rtb_Product16_on;
  double rtb_Product1_e;
  double rtb_Product1_ex;
  double rtb_Product1_ow;
  double rtb_Product1_p4;
  double rtb_Product1_pw;
  double rtb_Product2_aw;
  double rtb_Product2_g5;
  double rtb_Product2_hi;
  double rtb_Product2_my;
  double rtb_Product2_ox;
  double rtb_Product2_pw;
  double rtb_Product5;
  double rtb_Product7;
  double rtb_Product_op;
  double rtb_Q0123_idx_0;
  double rtb_Q0123_idx_1;
  double rtb_Q0123_idx_2;
  double rtb_Q0123_idx_3;
  double rtb_Sum4_h1;
  double rtb_Sum_mi_idx_0;
  double rtb_Sum_mi_idx_1;
  double rtb_Sum_mi_idx_2;
  double rtb_SumofControls_g;
  double rtb_SumofControls_o;
  double rtb_SumofDatum_ax;
  double rtb_SumofDatum_g;
  double rtb_SumofDatum_k;
  double rtb_TT0gLR;
  double rtb_Thr;
  double rtb_VectorConcatenate_idx_1;
  double rtb_VectorConcatenate_idx_6;
  double rtb_jxi;
  double rtb_q0dot;
  double rtb_q1dot;
  double rtb_q2dot;
  double rtb_q3dot;
  double rtb_rho0;
  double rtb_sincos_o1_idx_1;
  double rtb_sincos_o1_idx_2;
  double rtb_u2rhoV2;
  double rtb_u2rhoV2_e;
  double rtb_u2rhoV2_i;
  double rtb_u2rhoV2_m;
  double rtb_u2rhoV2_n;
  int32_t i;
  int32_t rtb_MatrixConcatenation_tmp;
  int32_t rtb_VectorConcatenate_j_tmp;
  uint32_t bpIndices[3];
  uint32_t bpIndices_0[3];
  uint32_t bpIndices_1[3];
  uint32_t bpIndices_10[3];
  uint32_t bpIndices_11[3];
  uint32_t bpIndices_12[3];
  uint32_t bpIndices_13[3];
  uint32_t bpIndices_14[3];
  uint32_t bpIndices_15[3];
  uint32_t bpIndices_16[3];
  uint32_t bpIndices_17[3];
  uint32_t bpIndices_18[3];
  uint32_t bpIndices_19[3];
  uint32_t bpIndices_1a[3];
  uint32_t bpIndices_1b[3];
  uint32_t bpIndices_1c[3];
  uint32_t bpIndices_1d[3];
  uint32_t bpIndices_1e[3];
  uint32_t bpIndices_1f[3];
  uint32_t bpIndices_1g[3];
  uint32_t bpIndices_1h[3];
  uint32_t bpIndices_1i[3];
  uint32_t bpIndices_1j[3];
  uint32_t bpIndices_1k[3];
  uint32_t bpIndices_1l[3];
  uint32_t bpIndices_1m[3];
  uint32_t bpIndices_1n[3];
  uint32_t bpIndices_1o[3];
  uint32_t bpIndices_1p[3];
  uint32_t bpIndices_1q[3];
  uint32_t bpIndices_1r[3];
  uint32_t bpIndices_1s[3];
  uint32_t bpIndices_1t[3];
  uint32_t bpIndices_1u[3];
  uint32_t bpIndices_1v[3];
  uint32_t bpIndices_1w[3];
  uint32_t bpIndices_1x[3];
  uint32_t bpIndices_1y[3];
  uint32_t bpIndices_1z[3];
  uint32_t bpIndices_2[3];
  uint32_t bpIndices_20[3];
  uint32_t bpIndices_21[3];
  uint32_t bpIndices_22[3];
  uint32_t bpIndices_23[3];
  uint32_t bpIndices_24[3];
  uint32_t bpIndices_25[3];
  uint32_t bpIndices_26[3];
  uint32_t bpIndices_27[3];
  uint32_t bpIndices_28[3];
  uint32_t bpIndices_29[3];
  uint32_t bpIndices_2a[3];
  uint32_t bpIndices_2b[3];
  uint32_t bpIndices_2c[3];
  uint32_t bpIndices_2d[3];
  uint32_t bpIndices_2e[3];
  uint32_t bpIndices_2f[3];
  uint32_t bpIndices_2g[3];
  uint32_t bpIndices_2h[3];
  uint32_t bpIndices_2i[3];
  uint32_t bpIndices_2j[3];
  uint32_t bpIndices_2k[3];
  uint32_t bpIndices_2l[3];
  uint32_t bpIndices_2m[3];
  uint32_t bpIndices_3[3];
  uint32_t bpIndices_4[3];
  uint32_t bpIndices_5[3];
  uint32_t bpIndices_6[3];
  uint32_t bpIndices_7[3];
  uint32_t bpIndices_8[3];
  uint32_t bpIndices_9[3];
  uint32_t bpIndices_a[3];
  uint32_t bpIndices_b[3];
  uint32_t bpIndices_c[3];
  uint32_t bpIndices_d[3];
  uint32_t bpIndices_e[3];
  uint32_t bpIndices_f[3];
  uint32_t bpIndices_g[3];
  uint32_t bpIndices_h[3];
  uint32_t bpIndices_i[3];
  uint32_t bpIndices_j[3];
  uint32_t bpIndices_k[3];
  uint32_t bpIndices_l[3];
  uint32_t bpIndices_m[3];
  uint32_t bpIndices_n[3];
  uint32_t bpIndices_o[3];
  uint32_t bpIndices_p[3];
  uint32_t bpIndices_q[3];
  uint32_t bpIndices_r[3];
  uint32_t bpIndices_s[3];
  uint32_t bpIndices_t[3];
  uint32_t bpIndices_u[3];
  uint32_t bpIndices_v[3];
  uint32_t bpIndices_w[3];
  uint32_t bpIndices_x[3];
  uint32_t bpIndices_y[3];
  uint32_t bpIndices_z[3];
  int8_t rtAction;
  int8_t rtPrevAction;
  bool rtb_Reshape_b[9];
  bool Compare;
  bool tmp;
  if (rtmIsMajorTimeStep(SkySurfer_Core_M)) {
    /* set solver stop time */
    rtsiSetSolverStopTime(&SkySurfer_Core_M->solverInfo,
                          ((SkySurfer_Core_M->Timing.clockTick0+1)*
      SkySurfer_Core_M->Timing.stepSize0));
  }                                    /* end MajorTimeStep */

  /* Update absolute time of base rate at minor time step */
  if (rtmIsMinorTimeStep(SkySurfer_Core_M)) {
    SkySurfer_Core_M->Timing.t[0] = rtsiGetT(&SkySurfer_Core_M->solverInfo);
  }

  _rtXdis = ((XDis_SkySurfer_Core_T *) SkySurfer_Core_M->contStateDisabled);
  tmp = rtmIsMajorTimeStep(SkySurfer_Core_M);
  if (tmp) {
    /* Gain: '<S13>/Gain' incorporates:
     *  Inport: '<Root>/InitialConditions'
     */
    SkySurfer_Core_DW->Gain = SkySurfer_Core_P.Gain_Gain_f *
      SkySurfer_Core_U->InitialConditions[3];
  }

  /* Integrator: '<S6>/XYZe' incorporates:
   *  Constant: '<S13>/rho_sealevel (slug//ft^3)2'
   *  SignalConversion generated from: '<S6>/XYZe'
   */
  if (SkySurfer_Core_DW->XYZe_DWORK1) {
    SkySurfer_Core_X->XYZe_CSTATE[0] =
      SkySurfer_Core_P.rho_sealevelslugft32_Value;
    SkySurfer_Core_X->XYZe_CSTATE[1] =
      SkySurfer_Core_P.rho_sealevelslugft32_Value;
    SkySurfer_Core_X->XYZe_CSTATE[2] = SkySurfer_Core_DW->Gain;
  }

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   *  Integrator: '<S6>/XYZe'
   */
  CoreSnapshot_Concat[0] = SkySurfer_Core_X->XYZe_CSTATE[0];
  CoreSnapshot_Concat[1] = SkySurfer_Core_X->XYZe_CSTATE[1];

  /* Integrator: '<S6>/XYZe' */
  rtb_Add_h_idx_2 = SkySurfer_Core_X->XYZe_CSTATE[2];

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   *  Integrator: '<S6>/XYZe'
   */
  CoreSnapshot_Concat[2] = SkySurfer_Core_X->XYZe_CSTATE[2];

  /* Integrator: '<S6>/UVWb' incorporates:
   *  Inport: '<Root>/InitialConditions'
   */
  if (SkySurfer_Core_DW->UVWb_DWORK1) {
    SkySurfer_Core_X->UVWb_CSTATE[0] = SkySurfer_Core_U->InitialConditions[0];
    SkySurfer_Core_X->UVWb_CSTATE[1] = SkySurfer_Core_U->InitialConditions[1];
    SkySurfer_Core_X->UVWb_CSTATE[2] = SkySurfer_Core_U->InitialConditions[2];
  }

  rtb_Sum_mi_idx_0 = SkySurfer_Core_X->UVWb_CSTATE[0];

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   *  Integrator: '<S6>/UVWb'
   */
  CoreSnapshot_Concat[3] = SkySurfer_Core_X->UVWb_CSTATE[0];

  /* Integrator: '<S6>/UVWb' */
  rtb_Sum_mi_idx_1 = SkySurfer_Core_X->UVWb_CSTATE[1];

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   *  Integrator: '<S6>/UVWb'
   */
  CoreSnapshot_Concat[4] = SkySurfer_Core_X->UVWb_CSTATE[1];

  /* Integrator: '<S6>/UVWb' */
  rtb_Sum_mi_idx_2 = SkySurfer_Core_X->UVWb_CSTATE[2];

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   *  Integrator: '<S6>/UVWb'
   */
  CoreSnapshot_Concat[5] = SkySurfer_Core_X->UVWb_CSTATE[2];
  if (tmp) {
    /* Gain: '<S162>/Gain1' incorporates:
     *  Gain: '<S21>/1//2'
     *  Inport: '<Root>/InitialConditions'
     */
    _mm_storeu_pd(&tmp_0[0], _mm_mul_pd(_mm_mul_pd(_mm_set1_pd
      (SkySurfer_Core_P.Gain1_Gain_m), _mm_set_pd
      (SkySurfer_Core_U->InitialConditions[5],
       SkySurfer_Core_U->InitialConditions[6])), _mm_set1_pd
      (SkySurfer_Core_P.u2_Gain)));

    /* Gain: '<S21>/1//2' incorporates:
     *  Gain: '<S162>/Gain1'
     *  Inport: '<Root>/InitialConditions'
     */
    rtb_sincos_o1_idx_2 = SkySurfer_Core_P.Gain1_Gain_m *
      SkySurfer_Core_U->InitialConditions[4] * SkySurfer_Core_P.u2_Gain;

    /* Trigonometry: '<S21>/sincos' */
    rtb_u[0] = cos(tmp_0[0]);
    rtb_Q0123_idx_0 = sin(tmp_0[0]);
    rtb_u[1] = cos(tmp_0[1]);
    rtb_Q0123_idx_1 = sin(tmp_0[1]);
    rtb_u[2] = cos(rtb_sincos_o1_idx_2);
    rtb_Q0123_idx_2 = sin(rtb_sincos_o1_idx_2);
    tmp_1 = _mm_set_pd(-1.0, 1.0);

    /* Fcn: '<S21>/q0' incorporates:
     *  Fcn: '<S21>/q1'
     *  Trigonometry: '<S21>/sincos'
     */
    _mm_storeu_pd(&tmp_0[0], _mm_add_pd(_mm_mul_pd(_mm_mul_pd(_mm_set1_pd(rtb_u
      [0]), _mm_set1_pd(rtb_u[1])), _mm_set_pd(rtb_Q0123_idx_2, rtb_u[2])),
      _mm_mul_pd(_mm_mul_pd(_mm_mul_pd(_mm_set1_pd(rtb_Q0123_idx_0), _mm_set1_pd
      (rtb_Q0123_idx_1)), _mm_set_pd(rtb_u[2], rtb_Q0123_idx_2)), tmp_1)));

    /* Fcn: '<S21>/q0' */
    SkySurfer_Core_DW->q0 = tmp_0[0];

    /* Fcn: '<S21>/q1' */
    SkySurfer_Core_DW->q1 = tmp_0[1];

    /* Trigonometry: '<S21>/sincos' incorporates:
     *  Fcn: '<S21>/q2'
     *  Fcn: '<S21>/q3'
     */
    _mm_storeu_pd(&tmp_0[0], _mm_add_pd(_mm_mul_pd(_mm_mul_pd(_mm_set_pd
      (rtb_Q0123_idx_0, rtb_u[0]), _mm_set_pd(rtb_u[1], rtb_Q0123_idx_1)),
      _mm_set1_pd(rtb_u[2])), _mm_mul_pd(_mm_mul_pd(_mm_mul_pd(_mm_set_pd(rtb_u
      [0], rtb_Q0123_idx_0), _mm_set_pd(rtb_Q0123_idx_1, rtb_u[1])), _mm_set1_pd
      (rtb_Q0123_idx_2)), tmp_1)));

    /* Fcn: '<S21>/q2' */
    SkySurfer_Core_DW->q2 = tmp_0[0];

    /* Fcn: '<S21>/q3' */
    SkySurfer_Core_DW->q3 = tmp_0[1];
  }

  /* Integrator: '<S14>/Q0123' incorporates:
   *  SignalConversion generated from: '<S14>/Q0123'
   */
  if (SkySurfer_Core_DW->Q0123_DWORK1) {
    SkySurfer_Core_X->Q0123_CSTATE[0] = SkySurfer_Core_DW->q0;
    SkySurfer_Core_X->Q0123_CSTATE[1] = SkySurfer_Core_DW->q1;
    SkySurfer_Core_X->Q0123_CSTATE[2] = SkySurfer_Core_DW->q2;
    SkySurfer_Core_X->Q0123_CSTATE[3] = SkySurfer_Core_DW->q3;
  }

  rtb_Q0123_idx_0 = SkySurfer_Core_X->Q0123_CSTATE[0];

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   *  Integrator: '<S14>/Q0123'
   */
  CoreSnapshot_Concat[6] = SkySurfer_Core_X->Q0123_CSTATE[0];

  /* Integrator: '<S14>/Q0123' */
  rtb_Q0123_idx_1 = SkySurfer_Core_X->Q0123_CSTATE[1];

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   *  Integrator: '<S14>/Q0123'
   */
  CoreSnapshot_Concat[7] = SkySurfer_Core_X->Q0123_CSTATE[1];

  /* Integrator: '<S14>/Q0123' */
  rtb_Q0123_idx_2 = SkySurfer_Core_X->Q0123_CSTATE[2];

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   *  Integrator: '<S14>/Q0123'
   */
  CoreSnapshot_Concat[8] = SkySurfer_Core_X->Q0123_CSTATE[2];

  /* Integrator: '<S14>/Q0123' */
  rtb_Q0123_idx_3 = SkySurfer_Core_X->Q0123_CSTATE[3];

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   *  Integrator: '<S14>/Q0123'
   */
  CoreSnapshot_Concat[9] = SkySurfer_Core_X->Q0123_CSTATE[3];

  /* Integrator: '<S6>/PQR' */
  rtb_u[0] = SkySurfer_Core_X->PQR_CSTATE[0];

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   *  Integrator: '<S6>/PQR'
   */
  CoreSnapshot_Concat[10] = SkySurfer_Core_X->PQR_CSTATE[0];

  /* Integrator: '<S6>/PQR' */
  rtb_u[1] = SkySurfer_Core_X->PQR_CSTATE[1];

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   *  Integrator: '<S6>/PQR'
   */
  CoreSnapshot_Concat[11] = SkySurfer_Core_X->PQR_CSTATE[1];

  /* Integrator: '<S6>/PQR' */
  rtb_u[2] = SkySurfer_Core_X->PQR_CSTATE[2];

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   *  Integrator: '<S6>/PQR'
   */
  CoreSnapshot_Concat[12] = SkySurfer_Core_X->PQR_CSTATE[2];

  /* Sqrt: '<S34>/sqrt' incorporates:
   *  Integrator: '<S14>/Q0123'
   *  Product: '<S35>/Product'
   *  Product: '<S35>/Product1'
   *  Product: '<S35>/Product2'
   *  Product: '<S35>/Product3'
   *  Sum: '<S35>/Sum'
   */
  rtb_jxi = sqrt(((SkySurfer_Core_X->Q0123_CSTATE[0] *
                   SkySurfer_Core_X->Q0123_CSTATE[0] +
                   SkySurfer_Core_X->Q0123_CSTATE[1] *
                   SkySurfer_Core_X->Q0123_CSTATE[1]) +
                  SkySurfer_Core_X->Q0123_CSTATE[2] *
                  SkySurfer_Core_X->Q0123_CSTATE[2]) +
                 SkySurfer_Core_X->Q0123_CSTATE[3] *
                 SkySurfer_Core_X->Q0123_CSTATE[3]);

  /* Integrator: '<S14>/Q0123' incorporates:
   *  Product: '<S33>/Product'
   */
  _mm_storeu_pd(&tmp_0[0], _mm_div_pd(_mm_loadu_pd
    (&SkySurfer_Core_X->Q0123_CSTATE[0]), _mm_set1_pd(rtb_jxi)));

  /* Product: '<S33>/Product2' incorporates:
   *  Integrator: '<S14>/Q0123'
   */
  rtb_Gain_az = SkySurfer_Core_X->Q0123_CSTATE[2] / rtb_jxi;

  /* Product: '<S33>/Product3' incorporates:
   *  Integrator: '<S14>/Q0123'
   */
  rtb_jxi = SkySurfer_Core_X->Q0123_CSTATE[3] / rtb_jxi;

  /* Product: '<S23>/Product3' incorporates:
   *  Product: '<S27>/Product3'
   */
  rtb_VectorConcatenate_idx_1 = tmp_0[0] * tmp_0[0];

  /* Product: '<S23>/Product2' incorporates:
   *  Product: '<S27>/Product2'
   */
  rtb_sincos_o1_idx_2 = tmp_0[1] * tmp_0[1];

  /* Product: '<S23>/Product1' incorporates:
   *  Product: '<S27>/Product1'
   *  Product: '<S31>/Product1'
   */
  rtb_VectorConcatenate_idx_6 = rtb_Gain_az * rtb_Gain_az;

  /* Product: '<S23>/Product' incorporates:
   *  Product: '<S27>/Product'
   *  Product: '<S31>/Product'
   */
  rtb_sincos_o1_idx_1 = rtb_jxi * rtb_jxi;

  /* Sum: '<S23>/Sum' incorporates:
   *  Product: '<S23>/Product'
   *  Product: '<S23>/Product1'
   *  Product: '<S23>/Product2'
   *  Product: '<S23>/Product3'
   */
  rtb_VectorConcatenate_k[0] = ((rtb_VectorConcatenate_idx_1 +
    rtb_sincos_o1_idx_2) - rtb_VectorConcatenate_idx_6) - rtb_sincos_o1_idx_1;

  /* Product: '<S26>/Product3' incorporates:
   *  Product: '<S24>/Product3'
   */
  rtb_Airspeed = rtb_jxi * tmp_0[0];

  /* Product: '<S26>/Product2' incorporates:
   *  Product: '<S24>/Product2'
   */
  rtb_q2dot = tmp_0[1] * rtb_Gain_az;

  /* Gain: '<S26>/Gain' incorporates:
   *  Product: '<S26>/Product2'
   *  Product: '<S26>/Product3'
   *  Sum: '<S26>/Sum'
   */
  rtb_VectorConcatenate_k[1] = (rtb_q2dot - rtb_Airspeed) *
    SkySurfer_Core_P.Gain_Gain_e;

  /* Product: '<S29>/Product2' incorporates:
   *  Product: '<S25>/Product2'
   */
  rtb_q3dot = tmp_0[1] * rtb_jxi;

  /* Product: '<S29>/Product1' incorporates:
   *  Product: '<S25>/Product1'
   */
  rtb_TT0gLR = tmp_0[0] * rtb_Gain_az;

  /* Gain: '<S29>/Gain' incorporates:
   *  Product: '<S29>/Product1'
   *  Product: '<S29>/Product2'
   *  Sum: '<S29>/Sum'
   */
  rtb_VectorConcatenate_k[2] = (rtb_TT0gLR + rtb_q3dot) *
    SkySurfer_Core_P.Gain_Gain_l;

  /* Gain: '<S24>/Gain' incorporates:
   *  Sum: '<S24>/Sum'
   */
  rtb_VectorConcatenate_k[3] = (rtb_Airspeed + rtb_q2dot) *
    SkySurfer_Core_P.Gain_Gain_c;

  /* Sum: '<S27>/Sum' incorporates:
   *  Sum: '<S31>/Sum'
   */
  rtb_VectorConcatenate_idx_1 -= rtb_sincos_o1_idx_2;
  rtb_VectorConcatenate_k[4] = (rtb_VectorConcatenate_idx_1 +
    rtb_VectorConcatenate_idx_6) - rtb_sincos_o1_idx_1;

  /* Product: '<S30>/Product1' incorporates:
   *  Product: '<S28>/Product1'
   */
  rtb_sincos_o1_idx_2 = tmp_0[0] * tmp_0[1];

  /* Product: '<S30>/Product2' incorporates:
   *  Product: '<S28>/Product2'
   */
  rtb_Airspeed = rtb_Gain_az * rtb_jxi;

  /* Gain: '<S30>/Gain' incorporates:
   *  Product: '<S30>/Product1'
   *  Product: '<S30>/Product2'
   *  Sum: '<S30>/Sum'
   */
  rtb_VectorConcatenate_k[5] = (rtb_Airspeed - rtb_sincos_o1_idx_2) *
    SkySurfer_Core_P.Gain_Gain_g;

  /* Gain: '<S25>/Gain' incorporates:
   *  Sum: '<S25>/Sum'
   */
  rtb_VectorConcatenate_k[6] = (rtb_q3dot - rtb_TT0gLR) *
    SkySurfer_Core_P.Gain_Gain_j;

  /* Gain: '<S28>/Gain' incorporates:
   *  Sum: '<S28>/Sum'
   */
  rtb_VectorConcatenate_k[7] = (rtb_sincos_o1_idx_2 + rtb_Airspeed) *
    SkySurfer_Core_P.Gain_Gain_n;

  /* Sum: '<S31>/Sum' */
  rtb_VectorConcatenate_k[8] = (rtb_VectorConcatenate_idx_1 -
    rtb_VectorConcatenate_idx_6) + rtb_sincos_o1_idx_1;

  /* Reshape: '<S32>/Reshape (9) to [3x3] column-major' */
  memcpy(&rtb_Reshape9to3x3columnmajor[0], &rtb_VectorConcatenate_k[0], 9U *
         sizeof(double));

  /* Product: '<S18>/Product' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   *  Integrator: '<S6>/UVWb'
   *  Math: '<S6>/Transpose'
   *  Reshape: '<S18>/Reshape2'
   *  Reshape: '<S32>/Reshape (9) to [3x3] column-major'
   *  SignalConversion generated from: '<S5>/CoreSnapshot_Concat'
   */
  rtb_Gain_az = SkySurfer_Core_X->UVWb_CSTATE[1];
  rtb_Thr = SkySurfer_Core_X->UVWb_CSTATE[0];
  rtb_VectorConcatenate_idx_1 = SkySurfer_Core_X->UVWb_CSTATE[2];
  for (i = 0; i < 3; i++) {
    _mm_storeu_pd(&tmp_0[0], _mm_add_pd(_mm_add_pd(_mm_mul_pd(_mm_set1_pd
      (rtb_VectorConcatenate_k[3 * i + 1]), _mm_set1_pd(rtb_Gain_az)),
      _mm_mul_pd(_mm_set1_pd(rtb_VectorConcatenate_k[3 * i]), _mm_set1_pd
                 (rtb_Thr))), _mm_mul_pd(_mm_set1_pd(rtb_VectorConcatenate_k[3 *
      i + 2]), _mm_set1_pd(rtb_VectorConcatenate_idx_1))));
    SkySurfer_Core_DW->Reshape2[i] = tmp_0[0];
    CoreSnapshot_Concat[i + 13] = tmp_0[1];
  }

  /* End of Product: '<S18>/Product' */

  /* Sqrt: '<S76>/sqrt' incorporates:
   *  Integrator: '<S14>/Q0123'
   *  Product: '<S77>/Product'
   *  Product: '<S77>/Product1'
   *  Product: '<S77>/Product2'
   *  Product: '<S77>/Product3'
   *  Sum: '<S77>/Sum'
   */
  rtb_Thr = sqrt(((SkySurfer_Core_X->Q0123_CSTATE[0] *
                   SkySurfer_Core_X->Q0123_CSTATE[0] +
                   SkySurfer_Core_X->Q0123_CSTATE[1] *
                   SkySurfer_Core_X->Q0123_CSTATE[1]) +
                  SkySurfer_Core_X->Q0123_CSTATE[2] *
                  SkySurfer_Core_X->Q0123_CSTATE[2]) +
                 SkySurfer_Core_X->Q0123_CSTATE[3] *
                 SkySurfer_Core_X->Q0123_CSTATE[3]);

  /* Integrator: '<S14>/Q0123' incorporates:
   *  Product: '<S75>/Product'
   */
  _mm_storeu_pd(&tmp_0[0], _mm_div_pd(_mm_loadu_pd
    (&SkySurfer_Core_X->Q0123_CSTATE[0]), _mm_set1_pd(rtb_Thr)));

  /* Product: '<S75>/Product2' incorporates:
   *  Integrator: '<S14>/Q0123'
   */
  rtb_jxi = SkySurfer_Core_X->Q0123_CSTATE[2] / rtb_Thr;

  /* Product: '<S75>/Product3' incorporates:
   *  Integrator: '<S14>/Q0123'
   */
  rtb_Thr = SkySurfer_Core_X->Q0123_CSTATE[3] / rtb_Thr;

  /* Product: '<S65>/Product3' incorporates:
   *  Product: '<S69>/Product3'
   */
  rtb_VectorConcatenate_idx_1 = tmp_0[0] * tmp_0[0];

  /* Product: '<S65>/Product2' incorporates:
   *  Product: '<S69>/Product2'
   */
  rtb_sincos_o1_idx_2 = tmp_0[1] * tmp_0[1];

  /* Product: '<S65>/Product1' incorporates:
   *  Product: '<S69>/Product1'
   *  Product: '<S73>/Product1'
   */
  rtb_VectorConcatenate_idx_6 = rtb_jxi * rtb_jxi;

  /* Product: '<S65>/Product' incorporates:
   *  Product: '<S69>/Product'
   *  Product: '<S73>/Product'
   */
  rtb_sincos_o1_idx_1 = rtb_Thr * rtb_Thr;

  /* Sum: '<S65>/Sum' incorporates:
   *  Product: '<S65>/Product'
   *  Product: '<S65>/Product1'
   *  Product: '<S65>/Product2'
   *  Product: '<S65>/Product3'
   */
  rtb_VectorConcatenate_k[0] = ((rtb_VectorConcatenate_idx_1 +
    rtb_sincos_o1_idx_2) - rtb_VectorConcatenate_idx_6) - rtb_sincos_o1_idx_1;

  /* Product: '<S68>/Product3' incorporates:
   *  Product: '<S66>/Product3'
   */
  rtb_Airspeed = rtb_Thr * tmp_0[0];

  /* Product: '<S68>/Product2' incorporates:
   *  Product: '<S66>/Product2'
   */
  rtb_q2dot = tmp_0[1] * rtb_jxi;

  /* Gain: '<S68>/Gain' incorporates:
   *  Product: '<S68>/Product2'
   *  Product: '<S68>/Product3'
   *  Sum: '<S68>/Sum'
   */
  rtb_VectorConcatenate_k[1] = (rtb_q2dot - rtb_Airspeed) *
    SkySurfer_Core_P.Gain_Gain_js;

  /* Product: '<S71>/Product2' incorporates:
   *  Product: '<S67>/Product2'
   */
  rtb_q3dot = tmp_0[1] * rtb_Thr;

  /* Product: '<S71>/Product1' incorporates:
   *  Product: '<S67>/Product1'
   */
  rtb_TT0gLR = tmp_0[0] * rtb_jxi;

  /* Gain: '<S71>/Gain' incorporates:
   *  Product: '<S71>/Product1'
   *  Product: '<S71>/Product2'
   *  Sum: '<S71>/Sum'
   */
  rtb_VectorConcatenate_k[2] = (rtb_TT0gLR + rtb_q3dot) *
    SkySurfer_Core_P.Gain_Gain_b;

  /* Gain: '<S66>/Gain' incorporates:
   *  Sum: '<S66>/Sum'
   */
  rtb_VectorConcatenate_k[3] = (rtb_Airspeed + rtb_q2dot) *
    SkySurfer_Core_P.Gain_Gain_la;

  /* Sum: '<S69>/Sum' incorporates:
   *  Sum: '<S73>/Sum'
   */
  rtb_VectorConcatenate_idx_1 -= rtb_sincos_o1_idx_2;
  rtb_VectorConcatenate_k[4] = (rtb_VectorConcatenate_idx_1 +
    rtb_VectorConcatenate_idx_6) - rtb_sincos_o1_idx_1;

  /* Product: '<S72>/Product1' incorporates:
   *  Product: '<S70>/Product1'
   */
  rtb_sincos_o1_idx_2 = tmp_0[0] * tmp_0[1];

  /* Product: '<S72>/Product2' incorporates:
   *  Product: '<S70>/Product2'
   */
  rtb_Airspeed = rtb_jxi * rtb_Thr;

  /* Gain: '<S72>/Gain' incorporates:
   *  Product: '<S72>/Product1'
   *  Product: '<S72>/Product2'
   *  Sum: '<S72>/Sum'
   */
  rtb_VectorConcatenate_k[5] = (rtb_Airspeed - rtb_sincos_o1_idx_2) *
    SkySurfer_Core_P.Gain_Gain_a;

  /* Gain: '<S67>/Gain' incorporates:
   *  Sum: '<S67>/Sum'
   */
  rtb_VectorConcatenate_k[6] = (rtb_q3dot - rtb_TT0gLR) *
    SkySurfer_Core_P.Gain_Gain_eu;

  /* Gain: '<S70>/Gain' incorporates:
   *  Sum: '<S70>/Sum'
   */
  rtb_VectorConcatenate_k[7] = (rtb_sincos_o1_idx_2 + rtb_Airspeed) *
    SkySurfer_Core_P.Gain_Gain_k;

  /* Sum: '<S73>/Sum' */
  rtb_VectorConcatenate_k[8] = (rtb_VectorConcatenate_idx_1 -
    rtb_VectorConcatenate_idx_6) + rtb_sincos_o1_idx_1;

  /* Selector: '<S40>/Selector1' incorporates:
   *  Gain: '<S40>/Gain1'
   *  Reshape: '<S74>/Reshape (9) to [3x3] column-major'
   */
  _mm_storeu_pd(&tmp_0[0], _mm_mul_pd(_mm_set_pd(rtb_VectorConcatenate_k[0],
    SkySurfer_Core_P.Gain1_Gain_cp[0]), _mm_set_pd
    (SkySurfer_Core_P.Gain1_Gain_cp[1], rtb_VectorConcatenate_k[3])));

  /* Gain: '<S40>/Gain1' */
  rtb_Thr = tmp_0[0];
  rtb_VectorConcatenate_idx_1 = tmp_0[1];

  /* Gain: '<S40>/Gain2' incorporates:
   *  Gain: '<S40>/Gain1'
   *  Reshape: '<S74>/Reshape (9) to [3x3] column-major'
   *  Selector: '<S40>/Selector1'
   */
  _mm_storeu_pd(&tmp_0[0], _mm_mul_pd(_mm_set_pd(SkySurfer_Core_P.Gain2_Gain[0],
    SkySurfer_Core_P.Gain1_Gain_cp[2]), _mm_loadu_pd(&rtb_VectorConcatenate_k[6])));

  /* Gain: '<S40>/Gain1' */
  rtb_sincos_o1_idx_2 = tmp_0[0];

  /* Gain: '<S40>/Gain2' incorporates:
   *  Gain: '<S40>/Gain3'
   *  Reshape: '<S74>/Reshape (9) to [3x3] column-major'
   *  Selector: '<S40>/Selector2'
   *  Selector: '<S40>/Selector3'
   */
  rtb_Gain_az = tmp_0[1];
  _mm_storeu_pd(&tmp_0[0], _mm_mul_pd(_mm_set_pd(SkySurfer_Core_P.Gain2_Gain[1],
    SkySurfer_Core_P.Gain3_Gain[0]), _mm_set_pd(rtb_VectorConcatenate_k[8],
    rtb_VectorConcatenate_k[1])));

  /* Gain: '<S40>/Gain3' incorporates:
   *  Reshape: '<S74>/Reshape (9) to [3x3] column-major'
   *  Selector: '<S40>/Selector3'
   */
  rtb_VectorConcatenate_idx_6 = SkySurfer_Core_P.Gain3_Gain[1] *
    rtb_VectorConcatenate_k[4];

  /* If: '<S36>/If' */
  rtPrevAction = SkySurfer_Core_DW->If_ActiveSubsystem;
  if (rtsiIsModeUpdateTimeStep(&SkySurfer_Core_M->solverInfo)) {
    rtAction = (int8_t)(!(rtb_sincos_o1_idx_2 >= 1.0) && !(rtb_sincos_o1_idx_2 <=
      -1.0));
    SkySurfer_Core_DW->If_ActiveSubsystem = rtAction;
  } else {
    rtAction = SkySurfer_Core_DW->If_ActiveSubsystem;
  }

  if (rtPrevAction != rtAction) {
    rtsiSetBlockStateForSolverChangedAtMajorStep(&SkySurfer_Core_M->solverInfo,
      true);
  }

  if (rtAction == 0) {
    /* Outputs for IfAction SubSystem: '<S36>/AxisRotZeroR3' incorporates:
     *  ActionPort: '<S39>/Action Port'
     */
    /* Concatenate: '<S5>/CoreSnapshot_Concat' incorporates:
     *  Fcn: '<S39>/Fcn1'
     *  SignalConversion generated from: '<S5>/CoreSnapshot_Concat'
     */
    CoreSnapshot_Concat[18] = rt_atan2d_snf(tmp_0[0],
      rtb_VectorConcatenate_idx_6);

    /* If: '<S46>/If' */
    rtPrevAction = SkySurfer_Core_DW->If_ActiveSubsystem_a;
    if (rtsiIsModeUpdateTimeStep(&SkySurfer_Core_M->solverInfo)) {
      if (rtb_sincos_o1_idx_2 > 1.0) {
        rtAction = 0;
      } else if (rtb_sincos_o1_idx_2 < -1.0) {
        rtAction = 1;
      } else {
        rtAction = 2;
      }

      SkySurfer_Core_DW->If_ActiveSubsystem_a = rtAction;
    } else {
      rtAction = SkySurfer_Core_DW->If_ActiveSubsystem_a;
    }

    if (rtPrevAction != rtAction) {
      rtsiSetBlockStateForSolverChangedAtMajorStep(&SkySurfer_Core_M->solverInfo,
        true);
    }

    switch (rtAction) {
     case 0:
      /* Outputs for IfAction SubSystem: '<S46>/If Action Subsystem' incorporates:
       *  ActionPort: '<S47>/Action Port'
       */
      if (rtmIsMajorTimeStep(SkySurfer_Core_M)) {
        /* Merge: '<S46>/Merge' incorporates:
         *  Constant: '<S47>/Constant'
         */
        SkySurfer_Core_DW->Merge_i = SkySurfer_Core_P.Constant_Value;
      }

      /* End of Outputs for SubSystem: '<S46>/If Action Subsystem' */
      break;

     case 1:
      /* Outputs for IfAction SubSystem: '<S46>/If Action Subsystem1' incorporates:
       *  ActionPort: '<S48>/Action Port'
       */
      if (rtmIsMajorTimeStep(SkySurfer_Core_M)) {
        /* Merge: '<S46>/Merge' incorporates:
         *  Constant: '<S48>/Constant'
         */
        SkySurfer_Core_DW->Merge_i = SkySurfer_Core_P.Constant_Value_i;
      }

      /* End of Outputs for SubSystem: '<S46>/If Action Subsystem1' */
      break;

     default:
      /* Outputs for IfAction SubSystem: '<S46>/If Action Subsystem2' incorporates:
       *  ActionPort: '<S49>/Action Port'
       */
      /* Merge: '<S46>/Merge' incorporates:
       *  SignalConversion generated from: '<S49>/In'
       */
      SkySurfer_Core_DW->Merge_i = rtb_sincos_o1_idx_2;

      /* End of Outputs for SubSystem: '<S46>/If Action Subsystem2' */
      break;
    }

    /* End of If: '<S46>/If' */

    /* Fcn: '<S39>/Fcn2' */
    if (SkySurfer_Core_DW->Merge_i > 1.0) {
      rtb_Product16 = 1.0;
    } else if (SkySurfer_Core_DW->Merge_i < -1.0) {
      rtb_Product16 = -1.0;
    } else {
      rtb_Product16 = SkySurfer_Core_DW->Merge_i;
    }

    /* Concatenate: '<S5>/CoreSnapshot_Concat' incorporates:
     *  Fcn: '<S39>/Fcn2'
     *  Fcn: '<S39>/Fcn3'
     *  SignalConversion generated from: '<S5>/CoreSnapshot_Concat'
     */
    CoreSnapshot_Concat[17] = asin(rtb_Product16);
    CoreSnapshot_Concat[16] = 0.0;

    /* End of Outputs for SubSystem: '<S36>/AxisRotZeroR3' */
  } else {
    /* Outputs for IfAction SubSystem: '<S36>/AxisRotDefault' incorporates:
     *  ActionPort: '<S38>/Action Port'
     */
    /* Concatenate: '<S5>/CoreSnapshot_Concat' incorporates:
     *  Fcn: '<S38>/Fcn1'
     *  SignalConversion generated from: '<S5>/CoreSnapshot_Concat'
     */
    CoreSnapshot_Concat[18] = rt_atan2d_snf(rtb_Thr, rtb_VectorConcatenate_idx_1);

    /* If: '<S42>/If' */
    rtPrevAction = SkySurfer_Core_DW->If_ActiveSubsystem_i;
    if (rtsiIsModeUpdateTimeStep(&SkySurfer_Core_M->solverInfo)) {
      if (rtb_sincos_o1_idx_2 > 1.0) {
        rtAction = 0;
      } else if (rtb_sincos_o1_idx_2 < -1.0) {
        rtAction = 1;
      } else {
        rtAction = 2;
      }

      SkySurfer_Core_DW->If_ActiveSubsystem_i = rtAction;
    } else {
      rtAction = SkySurfer_Core_DW->If_ActiveSubsystem_i;
    }

    if (rtPrevAction != rtAction) {
      rtsiSetBlockStateForSolverChangedAtMajorStep(&SkySurfer_Core_M->solverInfo,
        true);
    }

    switch (rtAction) {
     case 0:
      /* Outputs for IfAction SubSystem: '<S42>/If Action Subsystem' incorporates:
       *  ActionPort: '<S43>/Action Port'
       */
      if (rtmIsMajorTimeStep(SkySurfer_Core_M)) {
        /* Merge: '<S42>/Merge' incorporates:
         *  Constant: '<S43>/Constant'
         */
        SkySurfer_Core_DW->Merge = SkySurfer_Core_P.Constant_Value_f;
      }

      /* End of Outputs for SubSystem: '<S42>/If Action Subsystem' */
      break;

     case 1:
      /* Outputs for IfAction SubSystem: '<S42>/If Action Subsystem1' incorporates:
       *  ActionPort: '<S44>/Action Port'
       */
      if (rtmIsMajorTimeStep(SkySurfer_Core_M)) {
        /* Merge: '<S42>/Merge' incorporates:
         *  Constant: '<S44>/Constant'
         */
        SkySurfer_Core_DW->Merge = SkySurfer_Core_P.Constant_Value_k;
      }

      /* End of Outputs for SubSystem: '<S42>/If Action Subsystem1' */
      break;

     default:
      /* Outputs for IfAction SubSystem: '<S42>/If Action Subsystem2' incorporates:
       *  ActionPort: '<S45>/Action Port'
       */
      /* Merge: '<S42>/Merge' incorporates:
       *  SignalConversion generated from: '<S45>/In'
       */
      SkySurfer_Core_DW->Merge = rtb_sincos_o1_idx_2;

      /* End of Outputs for SubSystem: '<S42>/If Action Subsystem2' */
      break;
    }

    /* End of If: '<S42>/If' */

    /* Fcn: '<S38>/Fcn2' */
    if (SkySurfer_Core_DW->Merge > 1.0) {
      rtb_Product16 = 1.0;
    } else if (SkySurfer_Core_DW->Merge < -1.0) {
      rtb_Product16 = -1.0;
    } else {
      rtb_Product16 = SkySurfer_Core_DW->Merge;
    }

    /* Concatenate: '<S5>/CoreSnapshot_Concat' incorporates:
     *  Fcn: '<S38>/Fcn2'
     *  Fcn: '<S38>/Fcn3'
     *  SignalConversion generated from: '<S5>/CoreSnapshot_Concat'
     */
    CoreSnapshot_Concat[17] = asin(rtb_Product16);
    CoreSnapshot_Concat[16] = rt_atan2d_snf(rtb_Gain_az, tmp_0[1]);

    /* End of Outputs for SubSystem: '<S36>/AxisRotDefault' */
  }

  /* End of If: '<S36>/If' */
  if (tmp) {
    for (i = 0; i < 3; i++) {
      /* Concatenate: '<S15>/Matrix Concatenation' incorporates:
       *  Constant: '<S13>/Constant2'
       *  Constant: '<S4>/const2'
       */
      rtb_Gain_az = SkySurfer_Core_P.Inertia0[3 * i];
      rtb_MatrixConcatenation[6 * i] = rtb_Gain_az;
      rtb_MatrixConcatenation[6 * i + 3] = SkySurfer_Core_P.Constant2_Value_k[3 *
        i];

      /* Selector: '<S16>/Selector2' */
      SkySurfer_Core_DW->Selector2[3 * i] = rtb_Gain_az;

      /* Concatenate: '<S15>/Matrix Concatenation' incorporates:
       *  Constant: '<S13>/Constant2'
       *  Constant: '<S4>/const2'
       *  Selector: '<S16>/Selector2'
       */
      rtb_MatrixConcatenation_tmp = 3 * i + 1;
      rtb_Gain_az = SkySurfer_Core_P.Inertia0[rtb_MatrixConcatenation_tmp];
      rtb_MatrixConcatenation[6 * i + 1] = rtb_Gain_az;
      rtb_MatrixConcatenation[6 * i + 4] =
        SkySurfer_Core_P.Constant2_Value_k[rtb_MatrixConcatenation_tmp];

      /* Selector: '<S16>/Selector2' */
      SkySurfer_Core_DW->Selector2[rtb_MatrixConcatenation_tmp] = rtb_Gain_az;

      /* Concatenate: '<S15>/Matrix Concatenation' incorporates:
       *  Constant: '<S13>/Constant2'
       *  Constant: '<S4>/const2'
       *  Selector: '<S16>/Selector2'
       */
      rtb_MatrixConcatenation_tmp = 3 * i + 2;
      rtb_Gain_az = SkySurfer_Core_P.Inertia0[rtb_MatrixConcatenation_tmp];
      rtb_MatrixConcatenation[6 * i + 2] = rtb_Gain_az;
      rtb_MatrixConcatenation[6 * i + 5] =
        SkySurfer_Core_P.Constant2_Value_k[rtb_MatrixConcatenation_tmp];

      /* Selector: '<S16>/Selector2' */
      SkySurfer_Core_DW->Selector2[rtb_MatrixConcatenation_tmp] = rtb_Gain_az;
    }

    /* UnitConversion: '<S142>/Unit Conversion' incorporates:
     *  Constant: '<S4>/const15'
     */
    /* Unit Conversion - from: kn to: m/s
       Expression: output = (0.514444*input) + (0) */
    rtb_sincos_o1_idx_2 = 0.5144444444444445 * SkySurfer_Core_P.Vel_w;

    /* UnitConversion: '<S148>/Unit Conversion' incorporates:
     *  Constant: '<S4>/const16'
     */
    /* Unit Conversion - from: deg to: rad
       Expression: output = (0.0174533*input) + (0) */
    rtb_VectorConcatenate_idx_6 = 0.017453292519943295 * SkySurfer_Core_P.Psi_w;

    /* Product: '<S141>/Product1' incorporates:
     *  Constant: '<S141>/Wdeg1'
     *  Gain: '<S141>/ '
     *  Trigonometry: '<S141>/SinCos'
     */
    SkySurfer_Core_DW->Product1[0] = SkySurfer_Core_P._Gain * cos
      (rtb_VectorConcatenate_idx_6) * rtb_sincos_o1_idx_2;
    SkySurfer_Core_DW->Product1[1] = SkySurfer_Core_P._Gain * sin
      (rtb_VectorConcatenate_idx_6) * rtb_sincos_o1_idx_2;
    SkySurfer_Core_DW->Product1[2] = SkySurfer_Core_P._Gain *
      SkySurfer_Core_P.Wdeg1_Value * rtb_sincos_o1_idx_2;
  }

  /* TransferFcn: '<S3>/Transfer Fcn3' */
  rtb_Thr = SkySurfer_Core_P.TransferFcn3_C *
    SkySurfer_Core_X->TransferFcn3_CSTATE;

  /* Gain: '<S12>/Gain1' incorporates:
   *  Gain: '<S12>/kgf'
   */
  rtb_VectorConcatenate_idx_1 = SkySurfer_Core_P.kgf_Gain * rtb_Thr *
    SkySurfer_Core_P.g;

  /* Gain: '<S12>/Gain' incorporates:
   *  Constant: '<S12>/Constant1'
   *  Product: '<S12>/Product'
   */
  rtb_Gain_az = rtb_VectorConcatenate_idx_1 * SkySurfer_Core_P.del_z *
    SkySurfer_Core_P.Gain_Gain_lj;

  /* RelationalOperator: '<S140>/Gust Start' incorporates:
   *  Clock: '<S140>/Time'
   *  Constant: '<S140>/Gust start time'
   */
  rtb_jxi = (SkySurfer_Core_M->Timing.t[0] >=
             SkySurfer_Core_P.DiscreteWindGustModelOn_t_0);
  if (tmp) {
    /* Outputs for Enabled SubSystem: '<S140>/Distance into gust (x)' incorporates:
     *  EnablePort: '<S144>/Enable'
     */
    if (rtsiIsModeUpdateTimeStep(&SkySurfer_Core_M->solverInfo)) {
      /* Logic: '<S140>/Logical Operator2' incorporates:
       *  Constant: '<S140>/Constant'
       */
      if ((rtb_jxi != 0.0) && SkySurfer_Core_P.DiscreteWindGustModelOn_Gx) {
        if (!SkySurfer_Core_DW->Distanceintogustx_MODE) {
          (void) memset
            (&(SkySurfer_Core_XDis->DistanceintoGustxLimitedtogustlengthd_CSTATE_p),
             0,
             1*sizeof(bool));

          /* InitializeConditions for Integrator: '<S144>/Distance into Gust (x) (Limited to gust length d)' */
          SkySurfer_Core_X->DistanceintoGustxLimitedtogustlengthd_CSTATE_p =
            SkySurfer_Core_P.DistanceintoGustxLimitedtogustlengthd_IC;
          SkySurfer_Core_DW->Distanceintogustx_MODE = true;
        }
      } else {
        if (((SkySurfer_Core_M->Timing.clockTick1) * 0.004) == rtmGetTStart
            (SkySurfer_Core_M)) {
          (void) memset
            (&(SkySurfer_Core_XDis->DistanceintoGustxLimitedtogustlengthd_CSTATE_p),
             1,
             1*sizeof(bool));
        }

        if (SkySurfer_Core_DW->Distanceintogustx_MODE) {
          (void) memset
            (&(SkySurfer_Core_XDis->DistanceintoGustxLimitedtogustlengthd_CSTATE_p),
             1,
             1*sizeof(bool));
          SkySurfer_Core_DW->Distanceintogustx_MODE = false;
        }
      }

      /* End of Logic: '<S140>/Logical Operator2' */
    }

    /* End of Outputs for SubSystem: '<S140>/Distance into gust (x)' */

    /* SignalConversion generated from: '<S145>/Enable' incorporates:
     *  Constant: '<S140>/Constant1'
     *  Logic: '<S140>/Logical Operator1'
     */
    SkySurfer_Core_DW->HiddenBuf_InsertedFor_Distanceintogusty_at_inport_1 =
      ((rtb_jxi != 0.0) && SkySurfer_Core_P.DiscreteWindGustModelOn_Gy);
  }

  /* Outputs for Enabled SubSystem: '<S140>/Distance into gust (x)' incorporates:
   *  EnablePort: '<S144>/Enable'
   */
  if (SkySurfer_Core_DW->Distanceintogustx_MODE) {
    /* Outputs for Enabled SubSystem: '<S140>/Distance into gust (x)' */
    /* Integrator: '<S144>/Distance into Gust (x) (Limited to gust length d)' */
    /* Limited  Integrator  */
    if (SkySurfer_Core_X->DistanceintoGustxLimitedtogustlengthd_CSTATE_p >=
        SkySurfer_Core_P.Distanceintogustx_d_m) {
      SkySurfer_Core_X->DistanceintoGustxLimitedtogustlengthd_CSTATE_p =
        SkySurfer_Core_P.Distanceintogustx_d_m;
    } else if (SkySurfer_Core_X->DistanceintoGustxLimitedtogustlengthd_CSTATE_p <=
               SkySurfer_Core_P.DistanceintoGustxLimitedtogustlengthd_LowerSat)
    {
      SkySurfer_Core_X->DistanceintoGustxLimitedtogustlengthd_CSTATE_p =
        SkySurfer_Core_P.DistanceintoGustxLimitedtogustlengthd_LowerSat;
    }

    /* End of Outputs for SubSystem: '<S140>/Distance into gust (x)' */

    /* Integrator: '<S144>/Distance into Gust (x) (Limited to gust length d)' */
    SkySurfer_Core_DW->DistanceintoGustxLimitedtogustlengthd_l =
      SkySurfer_Core_X->DistanceintoGustxLimitedtogustlengthd_CSTATE_p;
  }

  /* End of Outputs for SubSystem: '<S140>/Distance into gust (x)' */

  /* Outputs for Enabled SubSystem: '<S140>/Distance into gust (y)' */
  /* Outputs for Enabled SubSystem: '<S140>/Distance into gust (y)' */
  SkySurfer_Core_Distanceintogusty(SkySurfer_Core_M,
    SkySurfer_Core_DW->HiddenBuf_InsertedFor_Distanceintogusty_at_inport_1,
    &SkySurfer_Core_DW->DistanceintoGustxLimitedtogustlengthd_k,
    SkySurfer_Core_P.Distanceintogusty_d_m,
    &SkySurfer_Core_DW->Distanceintogusty, &SkySurfer_Core_P.Distanceintogusty,
    &SkySurfer_Core_X->Distanceintogusty, &_rtXdis->Distanceintogusty);

  /* End of Outputs for SubSystem: '<S140>/Distance into gust (y)' */
  /* End of Outputs for SubSystem: '<S140>/Distance into gust (y)' */
  if (tmp) {
    /* SignalConversion generated from: '<S146>/Enable' incorporates:
     *  Constant: '<S140>/Constant2'
     *  Logic: '<S140>/Logical Operator3'
     */
    SkySurfer_Core_DW->HiddenBuf_InsertedFor_Distanceintogustz_at_inport_1 =
      ((rtb_jxi != 0.0) && SkySurfer_Core_P.DiscreteWindGustModelOn_Gz);
  }

  /* Outputs for Enabled SubSystem: '<S140>/Distance into gust (z)' */
  /* Outputs for Enabled SubSystem: '<S140>/Distance into gust (z)' */
  SkySurfer_Core_Distanceintogusty(SkySurfer_Core_M,
    SkySurfer_Core_DW->HiddenBuf_InsertedFor_Distanceintogustz_at_inport_1,
    &SkySurfer_Core_DW->DistanceintoGustxLimitedtogustlengthd,
    SkySurfer_Core_P.Distanceintogustz_d_m,
    &SkySurfer_Core_DW->Distanceintogustz, &SkySurfer_Core_P.Distanceintogustz,
    &SkySurfer_Core_X->Distanceintogustz, &_rtXdis->Distanceintogustz);

  /* End of Outputs for SubSystem: '<S140>/Distance into gust (z)' */
  /* End of Outputs for SubSystem: '<S140>/Distance into gust (z)' */

  /* Gain: '<S11>/Negate_D_to_Alt' */
  rtb_jxi = SkySurfer_Core_P.Negate_D_to_Alt_Gain * rtb_Add_h_idx_2;

  /* Unit Conversion - from: m to: ft
     Expression: output = (3.28084*input) + (0) */
  if (tmp) {
    /* Math: '<S143>/ln(ref_height//z0)' incorporates:
     *  Constant: '<S143>/ref_height//z0'
     *
     * About '<S143>/ln(ref_height//z0)':
     *  Operator: log
     */
    SkySurfer_Core_DW->lnref_heightz0 = log(SkySurfer_Core_P.ref_heightz0_Value);

    /* UnitConversion: '<S149>/Unit Conversion' incorporates:
     *  Constant: '<S143>/Wind Direction'
     */
    /* Unit Conversion - from: deg to: rad
       Expression: output = (0.0174533*input) + (0) */
    rtb_sincos_o1_idx_2 = 0.017453292519943295 *
      SkySurfer_Core_P.WindShearModel_Wdeg;

    /* Gain: '<S143>/Wind speed at reference height' incorporates:
     *  Constant: '<S143>/Wdeg1'
     *  Trigonometry: '<S143>/SinCos'
     */
    SkySurfer_Core_DW->Windspeedatreferenceheight[0] =
      -SkySurfer_Core_P.WindShearModel_W_20 * cos(rtb_sincos_o1_idx_2);
    SkySurfer_Core_DW->Windspeedatreferenceheight[1] =
      -SkySurfer_Core_P.WindShearModel_W_20 * sin(rtb_sincos_o1_idx_2);
    SkySurfer_Core_DW->Windspeedatreferenceheight[2] =
      -SkySurfer_Core_P.WindShearModel_W_20 * SkySurfer_Core_P.Wdeg1_Value_m;
  }

  /* MultiPortSwitch: '<S131>/VB' incorporates:
   *  Constant: '<S140>/2'
   *  Constant: '<S4>/const17'
   *  Gain: '<S140>/Gust magnitude//2.0'
   *  Gain: '<S140>/pi//Gust length'
   *  Product: '<S143>/Transform from Inertial to Body axes'
   *  Sum: '<S131>/Sum'
   *  Sum: '<S140>/Sum1'
   *  Trigonometry: '<S140>/cos(pi*x//dm)'
   */
  if ((int32_t)SkySurfer_Core_P.const17_Value == 1) {
    /* Product: '<S141>/Transform from Inertial to Body axes' incorporates:
     *  Reshape: '<S32>/Reshape (9) to [3x3] column-major'
     */
    rtb_Merge_idx_0 = 0.0;
    rtb_Merge_idx_1 = 0.0;
    rtb_Merge_idx_2 = 0.0;
    for (i = 0; i < 3; i++) {
      _mm_storeu_pd(&tmp_0[0], _mm_add_pd(_mm_mul_pd(_mm_loadu_pd
        (&rtb_Reshape9to3x3columnmajor[3 * i]), _mm_set1_pd
        (SkySurfer_Core_DW->Product1[i])), _mm_set_pd(rtb_Merge_idx_1,
        rtb_Merge_idx_0)));
      rtb_Merge_idx_0 = tmp_0[0];
      rtb_Merge_idx_1 = tmp_0[1];
      rtb_Merge_idx_2 += rtb_Reshape9to3x3columnmajor[3 * i + 2] *
        SkySurfer_Core_DW->Product1[i];
    }

    /* End of Product: '<S141>/Transform from Inertial to Body axes' */
  } else {
    /* UnitConversion: '<S150>/Unit Conversion' */
    rtb_Gain_h = 3.280839895013123 * rtb_jxi;

    /* Saturate: '<S143>/3ft-->inf' */
    if (rtb_Gain_h > SkySurfer_Core_P.uftinf_UpperSat) {
      rtb_Gain_h = SkySurfer_Core_P.uftinf_UpperSat;
    } else if (rtb_Gain_h < SkySurfer_Core_P.uftinf_LowerSat) {
      rtb_Gain_h = SkySurfer_Core_P.uftinf_LowerSat;
    }

    /* Product: '<S143>/Product' incorporates:
     *  Gain: '<S143>/h//z0'
     *  Math: '<S143>/ln(h//z0)'
     *  Saturate: '<S143>/3ft-->inf'
     *
     * About '<S143>/ln(h//z0)':
     *  Operator: log
     */
    rtb_sincos_o1_idx_2 = log(SkySurfer_Core_P.hz0_Gain * rtb_Gain_h) /
      SkySurfer_Core_DW->lnref_heightz0;

    /* Product: '<S143>/Transform from Inertial to Body axes' incorporates:
     *  Product: '<S143>/Product1'
     *  Reshape: '<S32>/Reshape (9) to [3x3] column-major'
     */
    rtb_Product14 = 0.0;
    rtb_Product16 = 0.0;
    rtb_DotProduct = 0.0;
    for (i = 0; i < 3; i++) {
      _mm_storeu_pd(&tmp_0[0], _mm_add_pd(_mm_mul_pd(_mm_loadu_pd
        (&rtb_Reshape9to3x3columnmajor[3 * i]), _mm_mul_pd(_mm_set1_pd
        (rtb_sincos_o1_idx_2), _mm_set1_pd
        (SkySurfer_Core_DW->Windspeedatreferenceheight[i]))), _mm_set_pd
        (rtb_Product16, rtb_Product14)));
      rtb_Product14 = tmp_0[0];
      rtb_Product16 = tmp_0[1];
      rtb_DotProduct += rtb_Reshape9to3x3columnmajor[3 * i + 2] *
        (rtb_sincos_o1_idx_2 * SkySurfer_Core_DW->Windspeedatreferenceheight[i]);
    }

    _mm_storeu_pd(&tmp_0[0], _mm_add_pd(_mm_mul_pd(_mm_sub_pd(_mm_set1_pd
      (SkySurfer_Core_P.u_Value), _mm_set_pd(cos(3.141592653589793 /
      SkySurfer_Core_P.DiscreteWindGustModelOn_d_m[1] *
      SkySurfer_Core_DW->DistanceintoGustxLimitedtogustlengthd_k), cos
      (3.141592653589793 / SkySurfer_Core_P.DiscreteWindGustModelOn_d_m[0] *
       SkySurfer_Core_DW->DistanceintoGustxLimitedtogustlengthd_l))), _mm_div_pd
      (_mm_loadu_pd(&SkySurfer_Core_P.DiscreteWindGustModelOn_v_m[0]),
       _mm_set1_pd(2.0))), _mm_set_pd(rtb_Product16, rtb_Product14)));
    rtb_Merge_idx_0 = tmp_0[0];
    rtb_Merge_idx_1 = tmp_0[1];
    rtb_Merge_idx_2 = (SkySurfer_Core_P.u_Value - cos(3.141592653589793 /
      SkySurfer_Core_P.DiscreteWindGustModelOn_d_m[2] *
      SkySurfer_Core_DW->DistanceintoGustxLimitedtogustlengthd)) *
      (SkySurfer_Core_P.DiscreteWindGustModelOn_v_m[2] / 2.0) + rtb_DotProduct;
  }

  /* End of MultiPortSwitch: '<S131>/VB' */

  /* Sum: '<S11>/Add1' */
  rtb_VectorConcatenate_idx_6 = rtb_Sum_mi_idx_0 - rtb_Merge_idx_0;
  rtb_sincos_o1_idx_1 = rtb_Sum_mi_idx_1 - rtb_Merge_idx_1;
  rtb_sincos_o1_idx_2 = rtb_Sum_mi_idx_2 - rtb_Merge_idx_2;

  /* Outputs for Enabled SubSystem: '<S5>/Aerodynamic' incorporates:
   *  EnablePort: '<S7>/Enable'
   */
  /* Product: '<S161>/Product' incorporates:
   *  AerodynamicForcesAndMoments: '<S7>/Aerodynamic Forces and Moments '
   */
  rtb_Merge_idx_0 = rtb_VectorConcatenate_idx_6 * rtb_VectorConcatenate_idx_6;

  /* Product: '<S161>/Product2' incorporates:
   *  AerodynamicForcesAndMoments: '<S7>/Aerodynamic Forces and Moments '
   */
  rtb_Merge_idx_1 = rtb_sincos_o1_idx_2 * rtb_sincos_o1_idx_2;

  /* Sum: '<S161>/Sum' incorporates:
   *  Product: '<S161>/Product'
   *  Product: '<S161>/Product1'
   *  Product: '<S161>/Product2'
   *  Sum: '<S128>/Sum'
   */
  rtb_Airspeed_tmp = (rtb_sincos_o1_idx_1 * rtb_sincos_o1_idx_1 +
                      rtb_Merge_idx_0) + rtb_Merge_idx_1;

  /* End of Outputs for SubSystem: '<S5>/Aerodynamic' */

  /* Sqrt: '<S157>/Airspeed' incorporates:
   *  Sum: '<S161>/Sum'
   */
  rtb_Airspeed = sqrt(rtb_Airspeed_tmp);

  /* Saturate: '<S136>/Limit  altitude  to troposhere' */
  if (rtb_jxi > SkySurfer_Core_P.Limitaltitudetotroposhere_UpperSat) {
    rtb_Product16 = SkySurfer_Core_P.Limitaltitudetotroposhere_UpperSat;
  } else if (rtb_jxi < SkySurfer_Core_P.Limitaltitudetotroposhere_LowerSat) {
    rtb_Product16 = SkySurfer_Core_P.Limitaltitudetotroposhere_LowerSat;
  } else {
    rtb_Product16 = rtb_jxi;
  }

  /* Sum: '<S136>/Sum1' incorporates:
   *  Constant: '<S136>/Sea Level  Temperature'
   *  Gain: '<S136>/Lapse Rate'
   *  Saturate: '<S136>/Limit  altitude  to troposhere'
   */
  rtb_q2dot = SkySurfer_Core_P.SeaLevelTemperature_Value -
    SkySurfer_Core_P.LapseRate_Gain * rtb_Product16;

  /* Gain: '<S136>/1//T0' */
  rtb_q3dot = SkySurfer_Core_P.uT0_Gain * rtb_q2dot;

  /* Math: '<S136>/(T//T0)^(g//LR) ' incorporates:
   *  Constant: '<S136>/Constant'
   */
  if ((rtb_q3dot < 0.0) && (SkySurfer_Core_P.Constant_Value_c > floor
       (SkySurfer_Core_P.Constant_Value_c))) {
    rtb_TT0gLR = -rt_powd_snf(-rtb_q3dot, SkySurfer_Core_P.Constant_Value_c);
  } else {
    rtb_TT0gLR = rt_powd_snf(rtb_q3dot, SkySurfer_Core_P.Constant_Value_c);
  }

  /* End of Math: '<S136>/(T//T0)^(g//LR) ' */

  /* Gain: '<S136>/rho0' incorporates:
   *  Product: '<S136>/Product'
   */
  rtb_rho0 = rtb_TT0gLR / rtb_q3dot * SkySurfer_Core_P.rho0_Gain;

  /* Sum: '<S136>/Sum' incorporates:
   *  Constant: '<S136>/Altitude of Troposphere'
   */
  rtb_Gain_h = SkySurfer_Core_P.AltitudeofTroposphere_Value - rtb_jxi;

  /* Saturate: '<S136>/Limit  altitude  to Stratosphere' */
  if (rtb_Gain_h > SkySurfer_Core_P.LimitaltitudetoStratosphere_UpperSat) {
    rtb_Gain_h = SkySurfer_Core_P.LimitaltitudetoStratosphere_UpperSat;
  } else if (rtb_Gain_h < SkySurfer_Core_P.LimitaltitudetoStratosphere_LowerSat)
  {
    rtb_Gain_h = SkySurfer_Core_P.LimitaltitudetoStratosphere_LowerSat;
  }

  /* Math: '<S136>/Stratosphere Model' incorporates:
   *  Gain: '<S136>/g//R'
   *  Product: '<S136>/Product1'
   *  Saturate: '<S136>/Limit  altitude  to Stratosphere'
   *
   * About '<S136>/Stratosphere Model':
   *  Operator: exp
   */
  rtb_q3dot = exp(1.0 / rtb_q2dot * (SkySurfer_Core_P.gR_Gain * rtb_Gain_h));

  /* UnitConversion: '<S132>/Density Conversion' incorporates:
   *  Product: '<S136>/Product3'
   */
  /* Unit Conversion - from: kg/m^3 to: kg/m^3
     Expression: output = (1*input) + (0) */
  rtb_rho0 *= rtb_q3dot;

  /* Sqrt: '<S136>/a' incorporates:
   *  Gain: '<S136>/gamma*R'
   */
  rtb_q0dot = sqrt(SkySurfer_Core_P.gammaR_Gain * rtb_q2dot);

  /* Product: '<S154>/Product1' incorporates:
   *  Sqrt: '<S154>/vt'
   */
  /* Unit Conversion - from: m/s to: m/s
     Expression: output = (1*input) + (0) */
  rtb_Product1_ow = rtb_Airspeed / rtb_q0dot;

  /* Trigonometry: '<S157>/Incidence' */
  rtb_q1dot = rt_atan2d_snf(rtb_sincos_o1_idx_2, rtb_VectorConcatenate_idx_6);

  /* Gain: '<S155>/Gain' */
  rtb_Gain = SkySurfer_Core_P.Gain_Gain_k3 * rtb_q1dot;

  /* Switch: '<S157>/Switch' incorporates:
   *  Constant: '<S157>/Constant2'
   *  Trigonometry: '<S157>/Sideslip'
   */
  if (rtb_Airspeed > SkySurfer_Core_P.Switch_Threshold_j) {
    /* Product: '<S157>/Product' */
    rtb_Gain_h = rtb_sincos_o1_idx_1 / rtb_Airspeed;

    /* Trigonometry: '<S157>/Sideslip' */
    if (rtb_Gain_h > 1.0) {
      rtb_Gain_h = 1.0;
    } else if (rtb_Gain_h < -1.0) {
      rtb_Gain_h = -1.0;
    }

    rtb_q1dot = asin(rtb_Gain_h);
  } else {
    rtb_q1dot = SkySurfer_Core_P.Constant2_Value_h;
  }

  /* End of Switch: '<S157>/Switch' */

  /* Gain: '<S156>/Gain' */
  rtb_Gain_h = SkySurfer_Core_P.Gain_Gain_d * rtb_q1dot;
  if (tmp) {
    /* MultiPortSwitch: '<S131>/AR' incorporates:
     *  Constant: '<S4>/const17'
     */
    if ((int32_t)SkySurfer_Core_P.const17_Value == 1) {
      /* MultiPortSwitch: '<S131>/AR' incorporates:
       *  Constant: '<S131>/Constant2'
       */
      SkySurfer_Core_DW->AR[0] = SkySurfer_Core_P.Constant2_Value[0];
      SkySurfer_Core_DW->AR[1] = SkySurfer_Core_P.Constant2_Value[1];
      SkySurfer_Core_DW->AR[2] = SkySurfer_Core_P.Constant2_Value[2];
    } else {
      /* MultiPortSwitch: '<S131>/AR' */
      SkySurfer_Core_DW->AR[0] = 0.0;
      SkySurfer_Core_DW->AR[1] = 0.0;
      SkySurfer_Core_DW->AR[2] = 0.0;
    }

    /* End of MultiPortSwitch: '<S131>/AR' */
  }

  /* Sum: '<S11>/Add4' incorporates:
   *  MultiPortSwitch: '<S131>/AR'
   */
  _mm_storeu_pd(&tmp_0[0], _mm_add_pd(_mm_loadu_pd(&SkySurfer_Core_DW->AR[0]),
    _mm_loadu_pd(&rtb_u[0])));

  /* Concatenate: '<S5>/CoreSnapshot_Concat' incorporates:
   *  SignalConversion generated from: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[59] = tmp_0[0];

  /* Sum: '<S11>/Add4' incorporates:
   *  MultiPortSwitch: '<S131>/AR'
   */
  rtb_Add4_idx_1 = tmp_0[1];
  rtb_Add4_idx_2 = SkySurfer_Core_DW->AR[2] + rtb_u[2];

  /* TransferFcn: '<S3>/Transfer Fcn' */
  SkySurfer_Core_DW->RateLimiter = SkySurfer_Core_P.TransferFcn_C *
    SkySurfer_Core_X->TransferFcn_CSTATE;

  /* RateLimiter: '<S3>/Rate Limiter' */
  if (!(SkySurfer_Core_DW->LastMajorTime == (rtMinusInf))) {
    rtb_Merge_idx_2 = SkySurfer_Core_M->Timing.t[0];
    rtb_Gain8 = rtb_Merge_idx_2 - SkySurfer_Core_DW->LastMajorTime;
    if (SkySurfer_Core_DW->LastMajorTime == rtb_Merge_idx_2) {
      if (SkySurfer_Core_DW->PrevLimited) {
        /* TransferFcn: '<S3>/Transfer Fcn' incorporates:
         *  RateLimiter: '<S3>/Rate Limiter'
         */
        SkySurfer_Core_DW->RateLimiter = SkySurfer_Core_DW->PrevY;
      }
    } else {
      rtb_DotProduct = rtb_Gain8 * SkySurfer_Core_P.RateLimiter_RisingLim;
      rtb_Merge_idx_2 = SkySurfer_Core_DW->RateLimiter -
        SkySurfer_Core_DW->PrevY;
      if (rtb_Merge_idx_2 > rtb_DotProduct) {
        /* TransferFcn: '<S3>/Transfer Fcn' incorporates:
         *  RateLimiter: '<S3>/Rate Limiter'
         */
        SkySurfer_Core_DW->RateLimiter = SkySurfer_Core_DW->PrevY +
          rtb_DotProduct;
        Compare = true;
      } else {
        rtb_Gain8 *= SkySurfer_Core_P.RateLimiter_FallingLim;
        if (rtb_Merge_idx_2 < rtb_Gain8) {
          /* TransferFcn: '<S3>/Transfer Fcn' incorporates:
           *  RateLimiter: '<S3>/Rate Limiter'
           */
          SkySurfer_Core_DW->RateLimiter = SkySurfer_Core_DW->PrevY + rtb_Gain8;
          Compare = true;
        } else {
          Compare = false;
        }
      }

      if (rtsiIsModeUpdateTimeStep(&SkySurfer_Core_M->solverInfo)) {
        SkySurfer_Core_DW->PrevLimited = Compare;
      }
    }
  }

  /* End of RateLimiter: '<S3>/Rate Limiter' */

  /* Gain: '<S3>/Gain5' */
  rtb_Gain5 = SkySurfer_Core_P.Gain5_Gain * SkySurfer_Core_DW->RateLimiter;

  /* TransferFcn: '<S3>/Transfer Fcn4' */
  SkySurfer_Core_DW->RateLimiter3 = SkySurfer_Core_P.TransferFcn4_C *
    SkySurfer_Core_X->TransferFcn4_CSTATE;

  /* RateLimiter: '<S3>/Rate Limiter3' */
  if (!(SkySurfer_Core_DW->LastMajorTime_e == (rtMinusInf))) {
    rtb_Merge_idx_2 = SkySurfer_Core_M->Timing.t[0];
    rtb_Gain8 = rtb_Merge_idx_2 - SkySurfer_Core_DW->LastMajorTime_e;
    if (SkySurfer_Core_DW->LastMajorTime_e == rtb_Merge_idx_2) {
      if (SkySurfer_Core_DW->PrevLimited_j) {
        /* TransferFcn: '<S3>/Transfer Fcn4' incorporates:
         *  RateLimiter: '<S3>/Rate Limiter3'
         */
        SkySurfer_Core_DW->RateLimiter3 = SkySurfer_Core_DW->PrevY_p;
      }
    } else {
      rtb_DotProduct = rtb_Gain8 * SkySurfer_Core_P.RateLimiter3_RisingLim;
      rtb_Merge_idx_2 = SkySurfer_Core_DW->RateLimiter3 -
        SkySurfer_Core_DW->PrevY_p;
      if (rtb_Merge_idx_2 > rtb_DotProduct) {
        /* TransferFcn: '<S3>/Transfer Fcn4' incorporates:
         *  RateLimiter: '<S3>/Rate Limiter3'
         */
        SkySurfer_Core_DW->RateLimiter3 = SkySurfer_Core_DW->PrevY_p +
          rtb_DotProduct;
        Compare = true;
      } else {
        rtb_Gain8 *= SkySurfer_Core_P.RateLimiter3_FallingLim;
        if (rtb_Merge_idx_2 < rtb_Gain8) {
          /* TransferFcn: '<S3>/Transfer Fcn4' incorporates:
           *  RateLimiter: '<S3>/Rate Limiter3'
           */
          SkySurfer_Core_DW->RateLimiter3 = SkySurfer_Core_DW->PrevY_p +
            rtb_Gain8;
          Compare = true;
        } else {
          Compare = false;
        }
      }

      if (rtsiIsModeUpdateTimeStep(&SkySurfer_Core_M->solverInfo)) {
        SkySurfer_Core_DW->PrevLimited_j = Compare;
      }
    }
  }

  /* End of RateLimiter: '<S3>/Rate Limiter3' */

  /* Gain: '<S3>/Gain3' */
  rtb_Gain3 = SkySurfer_Core_P.Gain3_Gain_m * SkySurfer_Core_DW->RateLimiter3;

  /* TransferFcn: '<S3>/Transfer Fcn1' */
  SkySurfer_Core_DW->RateLimiter1 = SkySurfer_Core_P.TransferFcn1_C *
    SkySurfer_Core_X->TransferFcn1_CSTATE;

  /* RateLimiter: '<S3>/Rate Limiter1' */
  if (!(SkySurfer_Core_DW->LastMajorTime_p == (rtMinusInf))) {
    rtb_Merge_idx_2 = SkySurfer_Core_M->Timing.t[0];
    rtb_Gain8 = rtb_Merge_idx_2 - SkySurfer_Core_DW->LastMajorTime_p;
    if (SkySurfer_Core_DW->LastMajorTime_p == rtb_Merge_idx_2) {
      if (SkySurfer_Core_DW->PrevLimited_j4) {
        /* TransferFcn: '<S3>/Transfer Fcn1' incorporates:
         *  RateLimiter: '<S3>/Rate Limiter1'
         */
        SkySurfer_Core_DW->RateLimiter1 = SkySurfer_Core_DW->PrevY_d;
      }
    } else {
      rtb_DotProduct = rtb_Gain8 * SkySurfer_Core_P.RateLimiter1_RisingLim;
      rtb_Merge_idx_2 = SkySurfer_Core_DW->RateLimiter1 -
        SkySurfer_Core_DW->PrevY_d;
      if (rtb_Merge_idx_2 > rtb_DotProduct) {
        /* TransferFcn: '<S3>/Transfer Fcn1' incorporates:
         *  RateLimiter: '<S3>/Rate Limiter1'
         */
        SkySurfer_Core_DW->RateLimiter1 = SkySurfer_Core_DW->PrevY_d +
          rtb_DotProduct;
        Compare = true;
      } else {
        rtb_Gain8 *= SkySurfer_Core_P.RateLimiter1_FallingLim;
        if (rtb_Merge_idx_2 < rtb_Gain8) {
          /* TransferFcn: '<S3>/Transfer Fcn1' incorporates:
           *  RateLimiter: '<S3>/Rate Limiter1'
           */
          SkySurfer_Core_DW->RateLimiter1 = SkySurfer_Core_DW->PrevY_d +
            rtb_Gain8;
          Compare = true;
        } else {
          Compare = false;
        }
      }

      if (rtsiIsModeUpdateTimeStep(&SkySurfer_Core_M->solverInfo)) {
        SkySurfer_Core_DW->PrevLimited_j4 = Compare;
      }
    }
  }

  /* End of RateLimiter: '<S3>/Rate Limiter1' */

  /* Gain: '<S3>/Gain4' */
  rtb_Gain4 = SkySurfer_Core_P.Gain4_Gain_a * SkySurfer_Core_DW->RateLimiter1;

  /* TransferFcn: '<S3>/Transfer Fcn2' */
  SkySurfer_Core_DW->RateLimiter2 = SkySurfer_Core_P.TransferFcn2_C *
    SkySurfer_Core_X->TransferFcn2_CSTATE;

  /* RateLimiter: '<S3>/Rate Limiter2' */
  if (!(SkySurfer_Core_DW->LastMajorTime_d == (rtMinusInf))) {
    rtb_Merge_idx_2 = SkySurfer_Core_M->Timing.t[0];
    rtb_Gain8 = rtb_Merge_idx_2 - SkySurfer_Core_DW->LastMajorTime_d;
    if (SkySurfer_Core_DW->LastMajorTime_d == rtb_Merge_idx_2) {
      if (SkySurfer_Core_DW->PrevLimited_n) {
        /* TransferFcn: '<S3>/Transfer Fcn2' incorporates:
         *  RateLimiter: '<S3>/Rate Limiter2'
         */
        SkySurfer_Core_DW->RateLimiter2 = SkySurfer_Core_DW->PrevY_m;
      }
    } else {
      rtb_DotProduct = rtb_Gain8 * SkySurfer_Core_P.RateLimiter2_RisingLim;
      rtb_Merge_idx_2 = SkySurfer_Core_DW->RateLimiter2 -
        SkySurfer_Core_DW->PrevY_m;
      if (rtb_Merge_idx_2 > rtb_DotProduct) {
        /* TransferFcn: '<S3>/Transfer Fcn2' incorporates:
         *  RateLimiter: '<S3>/Rate Limiter2'
         */
        SkySurfer_Core_DW->RateLimiter2 = SkySurfer_Core_DW->PrevY_m +
          rtb_DotProduct;
        Compare = true;
      } else {
        rtb_Gain8 *= SkySurfer_Core_P.RateLimiter2_FallingLim;
        if (rtb_Merge_idx_2 < rtb_Gain8) {
          /* TransferFcn: '<S3>/Transfer Fcn2' incorporates:
           *  RateLimiter: '<S3>/Rate Limiter2'
           */
          SkySurfer_Core_DW->RateLimiter2 = SkySurfer_Core_DW->PrevY_m +
            rtb_Gain8;
          Compare = true;
        } else {
          Compare = false;
        }
      }

      if (rtsiIsModeUpdateTimeStep(&SkySurfer_Core_M->solverInfo)) {
        SkySurfer_Core_DW->PrevLimited_n = Compare;
      }
    }
  }

  /* End of RateLimiter: '<S3>/Rate Limiter2' */

  /* Gain: '<S3>/Gain8' */
  rtb_Gain8 = SkySurfer_Core_P.Gain8_Gain * SkySurfer_Core_DW->RateLimiter2;

  /* RelationalOperator: '<S8>/Compare' incorporates:
   *  Constant: '<S8>/Constant'
   */
  Compare = (rtb_Airspeed > SkySurfer_Core_P.CompareToConstant_const);
  if (tmp) {
    /* Outputs for Enabled SubSystem: '<S5>/Aerodynamic' incorporates:
     *  EnablePort: '<S7>/Enable'
     */
    if (rtsiIsModeUpdateTimeStep(&SkySurfer_Core_M->solverInfo)) {
      /* SignalConversion generated from: '<S7>/Enable' */
      SkySurfer_Core_DW->Aerodynamic_MODE = Compare;
    }

    /* End of Outputs for SubSystem: '<S5>/Aerodynamic' */
  }

  /* Outputs for Enabled SubSystem: '<S5>/Aerodynamic' incorporates:
   *  EnablePort: '<S7>/Enable'
   */
  if (SkySurfer_Core_DW->Aerodynamic_MODE) {
    /* Lookup_n-D: '<S91>/CD_base' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U, &frac);
    rtb_Add1_m[0U] = frac;
    bpIndices[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    rtb_Add1_m[1U] = frac;
    bpIndices[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    rtb_Add1_m[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices, rtb_Add1_m,
      SkySurfer_Core_P.CD_base_tableData, SkySurfer_Core_P.CD_base_dimSizes);

    /* Lookup_n-D: '<S91>/CD_dp' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_0[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    rtb_MatrixMultiply[0U] = frac;
    bpIndices_0[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    rtb_MatrixMultiply[1U] = frac;
    bpIndices_0[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    rtb_MatrixMultiply[2U] = frac;
    rtb_Product_op = intrp3d_l_pw(bpIndices_0, rtb_MatrixMultiply,
      SkySurfer_Core_P.CD_dp_tableData, SkySurfer_Core_P.CD_dp_dimSizes);

    /* Gain: '<S91>/Multiply' incorporates:
     *  Product: '<S91>/Product1'
     */
    rtb_Merge_idx_2 = SkySurfer_Core_P.b / 2.0 * (rtb_Product_op * tmp_0[0]);

    /* Lookup_n-D: '<S91>/CD_dq' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_1[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions[0U] = frac;
    bpIndices_1[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions[1U] = frac;
    bpIndices_1[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions[2U] = frac;
    rtb_Product_op = intrp3d_l_pw(bpIndices_1, fractions,
      SkySurfer_Core_P.CD_dq_tableData, SkySurfer_Core_P.CD_dq_dimSizes);

    /* Gain: '<S91>/Multiply2' incorporates:
     *  Product: '<S91>/Product2'
     */
    rtb_Multiply2 = SkySurfer_Core_P.cbar / 2.0 * (rtb_Product_op * tmp_0[1]);

    /* Lookup_n-D: '<S91>/CD_dr' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_2[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_0[0U] = frac;
    bpIndices_2[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_0[1U] = frac;
    bpIndices_2[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_0[2U] = frac;
    rtb_Product_op = intrp3d_l_pw(bpIndices_2, fractions_0,
      SkySurfer_Core_P.CD_dr_tableData, SkySurfer_Core_P.CD_dr_dimSizes);

    /* Sum: '<S91>/Sum of Datum' incorporates:
     *  Gain: '<S91>/Multiply1'
     *  Product: '<S91>/Product10'
     *  Product: '<S91>/Product3'
     *  Sum: '<S91>/Sum1'
     */
    rtb_Merge_idx_2 = (SkySurfer_Core_P.b / 2.0 * (rtb_Product_op *
      rtb_Add4_idx_2) + (rtb_Merge_idx_2 + rtb_Multiply2)) / rtb_Airspeed +
      rtb_DotProduct;

    /* Lookup_n-D: '<S91>/CD_dailR' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_3[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_1[0U] = frac;
    bpIndices_3[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_1[1U] = frac;
    bpIndices_3[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_1[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_3, fractions_1,
      SkySurfer_Core_P.CD_dailR_tableData, SkySurfer_Core_P.CD_dailR_dimSizes);

    /* Product: '<S7>/Product' incorporates:
     *  Abs: '<S7>/Abs'
     *  Lookup_n-D: '<S7>/Aeroelasticity_AIL'
     */
    rtb_Product_op = look1_binlcpw(fabs(rtb_Gain5),
      SkySurfer_Core_P.Aeroelasticity_AIL,
      SkySurfer_Core_P.Aeroelasticity_Gain_AIL, 1U) * rtb_Gain5;

    /* Product: '<S91>/Product4' incorporates:
     *  Gain: '<S104>/Gain1'
     */
    rtb_Multiply2 = SkySurfer_Core_P.Gain1_Gain * rtb_Product_op *
      rtb_DotProduct;

    /* Lookup_n-D: '<S91>/CD_dailL' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_4[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_2[0U] = frac;
    bpIndices_4[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_2[1U] = frac;
    bpIndices_4[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_2[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_4, fractions_2,
      SkySurfer_Core_P.CD_dailL_tableData, SkySurfer_Core_P.CD_dailL_dimSizes);

    /* Product: '<S7>/Product1' incorporates:
     *  Abs: '<S7>/Abs1'
     *  Lookup_n-D: '<S7>/Aeroelasticity_AIL1'
     */
    rtb_Product1_p4 = look1_binlcpw(fabs(rtb_Gain3),
      SkySurfer_Core_P.Aeroelasticity_AIL,
      SkySurfer_Core_P.Aeroelasticity_Gain_AIL, 1U) * rtb_Gain3;

    /* Product: '<S91>/Product7' incorporates:
     *  Gain: '<S107>/Gain1'
     */
    rtb_Product7 = SkySurfer_Core_P.Gain1_Gain_h * rtb_Product1_p4 *
      rtb_DotProduct;

    /* Lookup_n-D: '<S91>/CD_dele' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_5[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_3[0U] = frac;
    bpIndices_5[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_3[1U] = frac;
    bpIndices_5[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_3[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_5, fractions_3,
      SkySurfer_Core_P.CD_dele_tableData, SkySurfer_Core_P.CD_dele_dimSizes);

    /* Product: '<S7>/Product2' incorporates:
     *  Abs: '<S7>/Abs2'
     *  Lookup_n-D: '<S7>/Aeroelasticity_ELE'
     */
    rtb_Product2_my = look1_binlcpw(fabs(rtb_Gain4),
      SkySurfer_Core_P.Aeroelasticity_ELE,
      SkySurfer_Core_P.Aeroelasticity_Gain_ELE, 1U) * rtb_Gain4;

    /* Product: '<S91>/Product5' incorporates:
     *  Gain: '<S105>/Gain1'
     */
    rtb_Product5 = SkySurfer_Core_P.Gain1_Gain_d * rtb_Product2_my *
      rtb_DotProduct;

    /* Lookup_n-D: '<S91>/CD_drud' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_6[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_4[0U] = frac;
    bpIndices_6[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_4[1U] = frac;
    bpIndices_6[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_4[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_6, fractions_4,
      SkySurfer_Core_P.CD_drud_tableData, SkySurfer_Core_P.CD_drud_dimSizes);

    /* Product: '<S7>/Product3' incorporates:
     *  Abs: '<S7>/Abs3'
     *  Lookup_n-D: '<S7>/Aeroelasticity_RUD'
     */
    rtb_q1dot = look1_binlcpw(fabs(rtb_Gain8),
      SkySurfer_Core_P.Aeroelasticity_RUD,
      SkySurfer_Core_P.Aeroelasticity_Gain_RUD, 1U) * rtb_Gain8;

    /* Sum: '<S91>/Sum of Controls' incorporates:
     *  Gain: '<S106>/Gain1'
     *  Gain: '<S7>/Gain15'
     *  Product: '<S91>/Product6'
     */
    rtb_Multiply2 = SkySurfer_Core_P.Gain15_Gain * rtb_q1dot *
      SkySurfer_Core_P.Gain1_Gain_dv * rtb_DotProduct + ((rtb_Multiply2 +
      rtb_Product7) + rtb_Product5);

    /* Lookup_n-D: '<S97>/CS_base' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_7[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_5[0U] = frac;
    bpIndices_7[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_5[1U] = frac;
    bpIndices_7[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_5[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_7, fractions_5,
      SkySurfer_Core_P.CS_base_tableData, SkySurfer_Core_P.CS_base_dimSizes);

    /* Lookup_n-D: '<S97>/CS_dp' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_8[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_6[0U] = frac;
    bpIndices_8[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_6[1U] = frac;
    bpIndices_8[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_6[2U] = frac;
    rtb_jxi = intrp3d_l_pw(bpIndices_8, fractions_6,
      SkySurfer_Core_P.CS_dp_tableData, SkySurfer_Core_P.CS_dp_dimSizes);

    /* Gain: '<S97>/Multiply3' incorporates:
     *  Product: '<S97>/Product8'
     */
    rtb_Product7 = SkySurfer_Core_P.b / 2.0 * (rtb_jxi * tmp_0[0]);

    /* Lookup_n-D: '<S97>/CS_dq' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_9[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_7[0U] = frac;
    bpIndices_9[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_7[1U] = frac;
    bpIndices_9[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_7[2U] = frac;
    rtb_jxi = intrp3d_l_pw(bpIndices_9, fractions_7,
      SkySurfer_Core_P.CS_dq_tableData, SkySurfer_Core_P.CS_dq_dimSizes);

    /* Gain: '<S97>/Multiply5' incorporates:
     *  Product: '<S97>/Product11'
     */
    rtb_Product5 = SkySurfer_Core_P.cbar / 2.0 * (rtb_jxi * tmp_0[1]);

    /* Lookup_n-D: '<S97>/CS_dr' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_a[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_8[0U] = frac;
    bpIndices_a[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_8[1U] = frac;
    bpIndices_a[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_8[2U] = frac;
    rtb_jxi = intrp3d_l_pw(bpIndices_a, fractions_8,
      SkySurfer_Core_P.CS_dr_tableData, SkySurfer_Core_P.CS_dr_dimSizes);

    /* Sum: '<S97>/Sum of Datum1' incorporates:
     *  Gain: '<S97>/Multiply4'
     *  Product: '<S97>/Product12'
     *  Product: '<S97>/Product9'
     *  Sum: '<S97>/Sum3'
     */
    rtb_Product7 = (SkySurfer_Core_P.b / 2.0 * (rtb_jxi * rtb_Add4_idx_2) +
                    (rtb_Product7 + rtb_Product5)) / rtb_Airspeed +
      rtb_DotProduct;

    /* Lookup_n-D: '<S97>/CS_dailR' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_b[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_9[0U] = frac;
    bpIndices_b[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_9[1U] = frac;
    bpIndices_b[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_9[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_b, fractions_9,
      SkySurfer_Core_P.CS_dailR_tableData, SkySurfer_Core_P.CS_dailR_dimSizes);

    /* Product: '<S97>/Product13' incorporates:
     *  Gain: '<S124>/Gain1'
     */
    rtb_Product5 = SkySurfer_Core_P.Gain1_Gain_o * rtb_Product_op *
      rtb_DotProduct;

    /* Lookup_n-D: '<S97>/CS_dailL' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_c[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_a[0U] = frac;
    bpIndices_c[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_a[1U] = frac;
    bpIndices_c[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_a[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_c, fractions_a,
      SkySurfer_Core_P.CS_dailL_tableData, SkySurfer_Core_P.CS_dailL_dimSizes);

    /* Product: '<S97>/Product16' incorporates:
     *  Gain: '<S127>/Gain1'
     */
    rtb_Product16 = SkySurfer_Core_P.Gain1_Gain_b * rtb_Product1_p4 *
      rtb_DotProduct;

    /* Lookup_n-D: '<S97>/CS_dele' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_d[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_b[0U] = frac;
    bpIndices_d[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_b[1U] = frac;
    bpIndices_d[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_b[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_d, fractions_b,
      SkySurfer_Core_P.CS_dele_tableData, SkySurfer_Core_P.CS_dele_dimSizes);

    /* Product: '<S97>/Product14' incorporates:
     *  Gain: '<S125>/Gain1'
     */
    rtb_Product14 = SkySurfer_Core_P.Gain1_Gain_j * rtb_Product2_my *
      rtb_DotProduct;

    /* Lookup_n-D: '<S97>/CS_drud' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_e[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_c[0U] = frac;
    bpIndices_e[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_c[1U] = frac;
    bpIndices_e[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_c[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_e, fractions_c,
      SkySurfer_Core_P.CS_drud_tableData, SkySurfer_Core_P.CS_drud_dimSizes);

    /* Sum: '<S97>/Sum of Controls1' incorporates:
     *  Gain: '<S126>/Gain1'
     *  Gain: '<S7>/Gain10'
     *  Product: '<S97>/Product15'
     */
    rtb_Product5 = SkySurfer_Core_P.Gain10_Gain * rtb_q1dot *
      SkySurfer_Core_P.Gain1_Gain_ju * rtb_DotProduct + ((rtb_Product5 +
      rtb_Product16) + rtb_Product14);

    /* Lookup_n-D: '<S93>/CL_base' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_f[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_d[0U] = frac;
    bpIndices_f[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_d[1U] = frac;
    bpIndices_f[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_d[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_f, fractions_d,
      SkySurfer_Core_P.CL_base_tableData, SkySurfer_Core_P.CL_base_dimSizes);

    /* Lookup_n-D: '<S93>/CL_dp' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_g[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_e[0U] = frac;
    bpIndices_g[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_e[1U] = frac;
    bpIndices_g[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_e[2U] = frac;
    rtb_jxi = intrp3d_l_pw(bpIndices_g, fractions_e,
      SkySurfer_Core_P.CL_dp_tableData, SkySurfer_Core_P.CL_dp_dimSizes);

    /* Gain: '<S93>/Multiply3' incorporates:
     *  Product: '<S93>/Product8'
     */
    rtb_Product16 = SkySurfer_Core_P.b / 2.0 * (rtb_jxi * tmp_0[0]);

    /* Lookup_n-D: '<S93>/CL_dq' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_h[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_f[0U] = frac;
    bpIndices_h[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_f[1U] = frac;
    bpIndices_h[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_f[2U] = frac;
    rtb_jxi = intrp3d_l_pw(bpIndices_h, fractions_f,
      SkySurfer_Core_P.CL_dq_tableData, SkySurfer_Core_P.CL_dq_dimSizes);

    /* Gain: '<S93>/Multiply5' incorporates:
     *  Product: '<S93>/Product11'
     */
    rtb_Product14 = SkySurfer_Core_P.cbar / 2.0 * (rtb_jxi * tmp_0[1]);

    /* Lookup_n-D: '<S93>/CL_dr' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_i[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_g[0U] = frac;
    bpIndices_i[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_g[1U] = frac;
    bpIndices_i[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_g[2U] = frac;
    rtb_jxi = intrp3d_l_pw(bpIndices_i, fractions_g,
      SkySurfer_Core_P.CL_dr_tableData, SkySurfer_Core_P.CL_dr_dimSizes);

    /* Sum: '<S93>/Sum of Datum1' incorporates:
     *  Gain: '<S93>/Multiply4'
     *  Product: '<S93>/Product12'
     *  Product: '<S93>/Product9'
     *  Sum: '<S93>/Sum3'
     */
    rtb_Product14 = (SkySurfer_Core_P.b / 2.0 * (rtb_jxi * rtb_Add4_idx_2) +
                     (rtb_Product16 + rtb_Product14)) / rtb_Airspeed +
      rtb_DotProduct;

    /* Lookup_n-D: '<S93>/CL_dailR' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_j[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_h[0U] = frac;
    bpIndices_j[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_h[1U] = frac;
    bpIndices_j[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_h[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_j, fractions_h,
      SkySurfer_Core_P.CL_dailR_tableData, SkySurfer_Core_P.CL_dailR_dimSizes);

    /* Product: '<S93>/Product13' incorporates:
     *  Gain: '<S108>/Gain1'
     */
    rtb_Product16 = SkySurfer_Core_P.Gain1_Gain_bf * rtb_Product_op *
      rtb_DotProduct;

    /* Lookup_n-D: '<S93>/CL_dailL' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_k[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_i[0U] = frac;
    bpIndices_k[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_i[1U] = frac;
    bpIndices_k[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_i[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_k, fractions_i,
      SkySurfer_Core_P.CL_dailL_tableData, SkySurfer_Core_P.CL_dailL_dimSizes);

    /* Product: '<S93>/Product16' incorporates:
     *  Gain: '<S111>/Gain1'
     */
    rtb_Product16_j = SkySurfer_Core_P.Gain1_Gain_g * rtb_Product1_p4 *
      rtb_DotProduct;

    /* Lookup_n-D: '<S93>/CL_dele' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_l[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_j[0U] = frac;
    bpIndices_l[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_j[1U] = frac;
    bpIndices_l[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_j[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_l, fractions_j,
      SkySurfer_Core_P.CL_dele_tableData, SkySurfer_Core_P.CL_dele_dimSizes);

    /* Product: '<S93>/Product14' incorporates:
     *  Gain: '<S109>/Gain1'
     */
    rtb_Product14_d = SkySurfer_Core_P.Gain1_Gain_n * rtb_Product2_my *
      rtb_DotProduct;

    /* Lookup_n-D: '<S93>/CL_drud' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_m[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_k[0U] = frac;
    bpIndices_m[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_k[1U] = frac;
    bpIndices_m[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_k[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_m, fractions_k,
      SkySurfer_Core_P.CL_drud_tableData, SkySurfer_Core_P.CL_drud_dimSizes);

    /* Sum: '<S93>/Sum of Controls1' incorporates:
     *  Gain: '<S110>/Gain1'
     *  Gain: '<S7>/Gain11'
     *  Product: '<S93>/Product15'
     */
    rtb_Product14_d = SkySurfer_Core_P.Gain11_Gain * rtb_q1dot *
      SkySurfer_Core_P.Gain1_Gain_p * rtb_DotProduct + ((rtb_Product16 +
      rtb_Product16_j) + rtb_Product14_d);

    /* Lookup_n-D: '<S94>/CMl_base' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_n[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_l[0U] = frac;
    bpIndices_n[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_l[1U] = frac;
    bpIndices_n[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_l[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_n, fractions_l,
      SkySurfer_Core_P.CMl_base_tableData, SkySurfer_Core_P.CMl_base_dimSizes);

    /* Lookup_n-D: '<S94>/CMl_dp' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_o[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_m[0U] = frac;
    bpIndices_o[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_m[1U] = frac;
    bpIndices_o[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_m[2U] = frac;
    rtb_jxi = intrp3d_l_pw(bpIndices_o, fractions_m,
      SkySurfer_Core_P.CMl_dp_tableData, SkySurfer_Core_P.CMl_dp_dimSizes);

    /* Gain: '<S94>/Multiply3' incorporates:
     *  Product: '<S94>/Product8'
     */
    rtb_Product16 = SkySurfer_Core_P.b / 2.0 * (rtb_jxi * tmp_0[0]);

    /* Lookup_n-D: '<S94>/CMl_dq' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_p[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_n[0U] = frac;
    bpIndices_p[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_n[1U] = frac;
    bpIndices_p[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_n[2U] = frac;
    rtb_jxi = intrp3d_l_pw(bpIndices_p, fractions_n,
      SkySurfer_Core_P.CMl_dq_tableData, SkySurfer_Core_P.CMl_dq_dimSizes);

    /* Gain: '<S94>/Multiply5' incorporates:
     *  Product: '<S94>/Product11'
     */
    rtb_Product16_j = SkySurfer_Core_P.cbar / 2.0 * (rtb_jxi * tmp_0[1]);

    /* Lookup_n-D: '<S94>/CMl_dr' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_q[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_o[0U] = frac;
    bpIndices_q[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_o[1U] = frac;
    bpIndices_q[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_o[2U] = frac;
    rtb_jxi = intrp3d_l_pw(bpIndices_q, fractions_o,
      SkySurfer_Core_P.CMl_dr_tableData, SkySurfer_Core_P.CMl_dr_dimSizes);

    /* Sum: '<S94>/Sum of Datum1' incorporates:
     *  Gain: '<S94>/Multiply4'
     *  Product: '<S94>/Product12'
     *  Product: '<S94>/Product9'
     *  Sum: '<S94>/Sum3'
     */
    rtb_Product16 = (SkySurfer_Core_P.b / 2.0 * (rtb_jxi * rtb_Add4_idx_2) +
                     (rtb_Product16 + rtb_Product16_j)) / rtb_Airspeed +
      rtb_DotProduct;

    /* Lookup_n-D: '<S94>/CMl_dailR' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_r[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_p[0U] = frac;
    bpIndices_r[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_p[1U] = frac;
    bpIndices_r[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_p[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_r, fractions_p,
      SkySurfer_Core_P.CMl_dailR_tableData, SkySurfer_Core_P.CMl_dailR_dimSizes);

    /* Product: '<S94>/Product13' incorporates:
     *  Gain: '<S112>/Gain1'
     */
    rtb_Product16_j = SkySurfer_Core_P.Gain1_Gain_ox * rtb_Product_op *
      rtb_DotProduct;

    /* Lookup_n-D: '<S94>/CMl_dailL' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_s[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_q[0U] = frac;
    bpIndices_s[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_q[1U] = frac;
    bpIndices_s[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_q[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_s, fractions_q,
      SkySurfer_Core_P.CMl_dailL_tableData, SkySurfer_Core_P.CMl_dailL_dimSizes);

    /* Product: '<S94>/Product16' incorporates:
     *  Gain: '<S115>/Gain1'
     */
    rtb_Product16_a = SkySurfer_Core_P.Gain1_Gain_l * rtb_Product1_p4 *
      rtb_DotProduct;

    /* Lookup_n-D: '<S94>/CMl_dele' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_t[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_r[0U] = frac;
    bpIndices_t[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_r[1U] = frac;
    bpIndices_t[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_r[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_t, fractions_r,
      SkySurfer_Core_P.CMl_dele_tableData, SkySurfer_Core_P.CMl_dele_dimSizes);

    /* Product: '<S94>/Product14' incorporates:
     *  Gain: '<S113>/Gain1'
     */
    rtb_Product14_k = SkySurfer_Core_P.Gain1_Gain_pp * rtb_Product2_my *
      rtb_DotProduct;

    /* Lookup_n-D: '<S94>/CMl_drud' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_u[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_s[0U] = frac;
    bpIndices_u[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_s[1U] = frac;
    bpIndices_u[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_s[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_u, fractions_s,
      SkySurfer_Core_P.CMl_drud_tableData, SkySurfer_Core_P.CMl_drud_dimSizes);

    /* Sum: '<S94>/Sum of Controls1' incorporates:
     *  Gain: '<S114>/Gain1'
     *  Gain: '<S7>/Gain4'
     *  Product: '<S94>/Product15'
     */
    rtb_Product16_j = SkySurfer_Core_P.Gain4_Gain * rtb_q1dot *
      SkySurfer_Core_P.Gain1_Gain_dh * rtb_DotProduct + ((rtb_Product16_j +
      rtb_Product16_a) + rtb_Product14_k);

    /* Lookup_n-D: '<S95>/CMm_base' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_v[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_t[0U] = frac;
    bpIndices_v[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_t[1U] = frac;
    bpIndices_v[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_t[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_v, fractions_t,
      SkySurfer_Core_P.CMm_base_tableData, SkySurfer_Core_P.CMm_base_dimSizes);

    /* Lookup_n-D: '<S95>/CMm_dp' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_w[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_u[0U] = frac;
    bpIndices_w[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_u[1U] = frac;
    bpIndices_w[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_u[2U] = frac;
    rtb_jxi = intrp3d_l_pw(bpIndices_w, fractions_u,
      SkySurfer_Core_P.CMm_dp_tableData, SkySurfer_Core_P.CMm_dp_dimSizes);

    /* Gain: '<S95>/Multiply3' incorporates:
     *  Product: '<S95>/Product8'
     */
    rtb_Product16_a = SkySurfer_Core_P.b / 2.0 * (rtb_jxi * tmp_0[0]);

    /* Lookup_n-D: '<S95>/CMm_dq' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_x[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_v[0U] = frac;
    bpIndices_x[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_v[1U] = frac;
    bpIndices_x[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_v[2U] = frac;
    rtb_jxi = intrp3d_l_pw(bpIndices_x, fractions_v,
      SkySurfer_Core_P.CMm_dq_tableData, SkySurfer_Core_P.CMm_dq_dimSizes);

    /* Gain: '<S95>/Multiply5' incorporates:
     *  Product: '<S95>/Product11'
     */
    rtb_Product14_k = SkySurfer_Core_P.cbar / 2.0 * (rtb_jxi * tmp_0[1]);

    /* Lookup_n-D: '<S95>/CMm_dr' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_y[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_w[0U] = frac;
    bpIndices_y[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_w[1U] = frac;
    bpIndices_y[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_w[2U] = frac;
    rtb_jxi = intrp3d_l_pw(bpIndices_y, fractions_w,
      SkySurfer_Core_P.CMm_dr_tableData, SkySurfer_Core_P.CMm_dr_dimSizes);

    /* Sum: '<S95>/Sum of Datum1' incorporates:
     *  Gain: '<S95>/Multiply4'
     *  Product: '<S95>/Product12'
     *  Product: '<S95>/Product9'
     *  Sum: '<S95>/Sum3'
     */
    rtb_Product16_a = (SkySurfer_Core_P.b / 2.0 * (rtb_jxi * rtb_Add4_idx_2) +
                       (rtb_Product16_a + rtb_Product14_k)) / rtb_Airspeed +
      rtb_DotProduct;

    /* Lookup_n-D: '<S95>/CMm_dailR' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_z[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_x[0U] = frac;
    bpIndices_z[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_x[1U] = frac;
    bpIndices_z[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_x[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_z, fractions_x,
      SkySurfer_Core_P.CMm_dailR_tableData, SkySurfer_Core_P.CMm_dailR_dimSizes);

    /* Product: '<S95>/Product13' incorporates:
     *  Gain: '<S116>/Gain1'
     */
    rtb_Product14_k = SkySurfer_Core_P.Gain1_Gain_db * rtb_Product_op *
      rtb_DotProduct;

    /* Lookup_n-D: '<S95>/CMm_dailL' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_10[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_y[0U] = frac;
    bpIndices_10[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_y[1U] = frac;
    bpIndices_10[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_y[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_10, fractions_y,
      SkySurfer_Core_P.CMm_dailL_tableData, SkySurfer_Core_P.CMm_dailL_dimSizes);

    /* Product: '<S95>/Product16' incorporates:
     *  Gain: '<S119>/Gain1'
     */
    rtb_Product16_on = SkySurfer_Core_P.Gain1_Gain_ba * rtb_Product1_p4 *
      rtb_DotProduct;

    /* Lookup_n-D: '<S95>/CMm_dele' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_11[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_z[0U] = frac;
    bpIndices_11[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_z[1U] = frac;
    bpIndices_11[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_z[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_11, fractions_z,
      SkySurfer_Core_P.CMm_dele_tableData, SkySurfer_Core_P.CMm_dele_dimSizes);

    /* Product: '<S95>/Product14' incorporates:
     *  Gain: '<S117>/Gain1'
     */
    rtb_jxi = SkySurfer_Core_P.Gain1_Gain_c * rtb_Product2_my * rtb_DotProduct;

    /* Lookup_n-D: '<S95>/CMm_drud' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_12[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_10[0U] = frac;
    bpIndices_12[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_10[1U] = frac;
    bpIndices_12[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_10[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_12, fractions_10,
      SkySurfer_Core_P.CMm_drud_tableData, SkySurfer_Core_P.CMm_drud_dimSizes);

    /* Sum: '<S95>/Sum of Controls1' incorporates:
     *  Gain: '<S118>/Gain1'
     *  Gain: '<S7>/Gain9'
     *  Product: '<S95>/Product15'
     */
    rtb_Product14_k = SkySurfer_Core_P.Gain9_Gain * rtb_q1dot *
      SkySurfer_Core_P.Gain1_Gain_f * rtb_DotProduct + ((rtb_Product14_k +
      rtb_Product16_on) + rtb_jxi);

    /* Lookup_n-D: '<S96>/CMn_base' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_13[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_11[0U] = frac;
    bpIndices_13[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_11[1U] = frac;
    bpIndices_13[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_11[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_13, fractions_11,
      SkySurfer_Core_P.CMn_base_tableData, SkySurfer_Core_P.CMn_base_dimSizes);

    /* Lookup_n-D: '<S96>/CMn_dp' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_14[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_12[0U] = frac;
    bpIndices_14[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_12[1U] = frac;
    bpIndices_14[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_12[2U] = frac;
    rtb_jxi = intrp3d_l_pw(bpIndices_14, fractions_12,
      SkySurfer_Core_P.CMn_dp_tableData, SkySurfer_Core_P.CMn_dp_dimSizes);

    /* Gain: '<S96>/Multiply3' incorporates:
     *  Product: '<S96>/Product8'
     */
    rtb_Product16_on = SkySurfer_Core_P.b / 2.0 * (rtb_jxi * tmp_0[0]);

    /* Lookup_n-D: '<S96>/CMn_dq' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_15[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_13[0U] = frac;
    bpIndices_15[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_13[1U] = frac;
    bpIndices_15[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_13[2U] = frac;
    rtb_jxi = intrp3d_l_pw(bpIndices_15, fractions_13,
      SkySurfer_Core_P.CMn_dq_tableData, SkySurfer_Core_P.CMn_dq_dimSizes);

    /* Gain: '<S96>/Multiply5' incorporates:
     *  Product: '<S96>/Product11'
     */
    rtb_Multiply5_o = SkySurfer_Core_P.cbar / 2.0 * (rtb_jxi * tmp_0[1]);

    /* Lookup_n-D: '<S96>/CMn_dr' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_16[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_14[0U] = frac;
    bpIndices_16[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_14[1U] = frac;
    bpIndices_16[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_14[2U] = frac;
    rtb_jxi = intrp3d_l_pw(bpIndices_16, fractions_14,
      SkySurfer_Core_P.CMn_dr_tableData, SkySurfer_Core_P.CMn_dr_dimSizes);

    /* Sum: '<S96>/Sum of Datum1' incorporates:
     *  Gain: '<S96>/Multiply4'
     *  Product: '<S96>/Product12'
     *  Product: '<S96>/Product9'
     *  Sum: '<S96>/Sum3'
     */
    rtb_Product16_on = (SkySurfer_Core_P.b / 2.0 * (rtb_jxi * rtb_Add4_idx_2) +
                        (rtb_Product16_on + rtb_Multiply5_o)) / rtb_Airspeed +
      rtb_DotProduct;

    /* Lookup_n-D: '<S96>/CMn_dailR' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_17[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_15[0U] = frac;
    bpIndices_17[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_15[1U] = frac;
    bpIndices_17[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_15[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_17, fractions_15,
      SkySurfer_Core_P.CMn_dailR_tableData, SkySurfer_Core_P.CMn_dailR_dimSizes);

    /* Product: '<S96>/Product13' incorporates:
     *  Gain: '<S120>/Gain1'
     */
    rtb_jxi = SkySurfer_Core_P.Gain1_Gain_e * rtb_Product_op * rtb_DotProduct;

    /* Lookup_n-D: '<S96>/CMn_dailL' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_18[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_16[0U] = frac;
    bpIndices_18[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_16[1U] = frac;
    bpIndices_18[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_16[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_18, fractions_16,
      SkySurfer_Core_P.CMn_dailL_tableData, SkySurfer_Core_P.CMn_dailL_dimSizes);

    /* Product: '<S96>/Product16' incorporates:
     *  Gain: '<S123>/Gain1'
     */
    rtb_Multiply5_o = SkySurfer_Core_P.Gain1_Gain_ps * rtb_Product1_p4 *
      rtb_DotProduct;

    /* Lookup_n-D: '<S96>/CMn_dele' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_19[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_17[0U] = frac;
    bpIndices_19[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_17[1U] = frac;
    bpIndices_19[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_17[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_19, fractions_17,
      SkySurfer_Core_P.CMn_dele_tableData, SkySurfer_Core_P.CMn_dele_dimSizes);

    /* Product: '<S96>/Product14' incorporates:
     *  Gain: '<S121>/Gain1'
     */
    rtb_Product14_hm = SkySurfer_Core_P.Gain1_Gain_os * rtb_Product2_my *
      rtb_DotProduct;

    /* Lookup_n-D: '<S96>/CMn_drud' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_1a[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.Mach, 1U,
      &frac);
    fractions_18[0U] = frac;
    bpIndices_1a[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.AoA, 5U, &frac);
    fractions_18[1U] = frac;
    bpIndices_1a[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.AoS, 2U, &frac);
    fractions_18[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_1a, fractions_18,
      SkySurfer_Core_P.CMn_drud_tableData, SkySurfer_Core_P.CMn_drud_dimSizes);

    /* SignalConversion generated from: '<S7>/Aerodynamic Forces and Moments ' incorporates:
     *  Gain: '<S122>/Gain1'
     *  Gain: '<S7>/Gain12'
     *  Product: '<S96>/Product15'
     *  Sum: '<S96>/Sum of Controls1'
     *  Sum: '<S96>/Sum4'
     */
    rtb_Product16_on += SkySurfer_Core_P.Gain12_Gain * rtb_q1dot *
      SkySurfer_Core_P.Gain1_Gain_dq * rtb_DotProduct + ((rtb_jxi +
      rtb_Multiply5_o) + rtb_Product14_hm);

    /* Lookup_n-D: '<S90>/CDtot' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_1b[0U] = plook_binc(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_19[0U] = frac;
    bpIndices_1b[1U] = plook_binc(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_19[1U] = frac;
    bpIndices_1b[2U] = plook_binc(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_19[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_1b, fractions_19,
      SkySurfer_Core_P.CDtot, SkySurfer_Core_P.CDtot_dimSizes);

    /* Lookup_n-D: '<S90>/CDp' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_1c[0U] = plook_binc(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_1a[0U] = frac;
    bpIndices_1c[1U] = plook_binc(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_1a[1U] = frac;
    bpIndices_1c[2U] = plook_binc(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_1a[2U] = frac;
    rtb_jxi = intrp3d_l_pw(bpIndices_1c, fractions_1a, SkySurfer_Core_P.CDp,
      SkySurfer_Core_P.CDp_dimSizes);

    /* Gain: '<S102>/Gain1' */
    rtb_Product2_hi = SkySurfer_Core_P.Gain1_Gain_i * rtb_Gain;

    /* Fcn: '<S7>/Stab_p' incorporates:
     *  Fcn: '<S7>/Stab_r'
     */
    rtb_SumofDatum_k = cos(rtb_Product2_hi);
    rtb_SumofControls_g = sin(rtb_Product2_hi);
    rtb_Product1_ex = tmp_0[0] * rtb_SumofDatum_k + rtb_Add4_idx_2 *
      rtb_SumofControls_g;

    /* Gain: '<S90>/Multiply' incorporates:
     *  Product: '<S90>/Product1'
     */
    rtb_Multiply5_o = SkySurfer_Core_P.b / 2.0 * (rtb_jxi * rtb_Product1_ex);

    /* Lookup_n-D: '<S90>/CDq' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_1d[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_1b[0U] = frac;
    bpIndices_1d[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_1b[1U] = frac;
    bpIndices_1d[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_1b[2U] = frac;
    rtb_jxi = intrp3d_l_pw(bpIndices_1d, fractions_1b, SkySurfer_Core_P.CDq,
      SkySurfer_Core_P.CDq_dimSizes);

    /* Gain: '<S90>/Multiply2' incorporates:
     *  Product: '<S90>/Product2'
     */
    rtb_Product14_hm = SkySurfer_Core_P.cbar / 2.0 * (rtb_jxi * tmp_0[1]);

    /* Lookup_n-D: '<S90>/CDr' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_1e[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_1c[0U] = frac;
    bpIndices_1e[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_1c[1U] = frac;
    bpIndices_1e[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_1c[2U] = frac;
    rtb_jxi = intrp3d_l_pw(bpIndices_1e, fractions_1c, SkySurfer_Core_P.CDr,
      SkySurfer_Core_P.CDr_dimSizes);

    /* Fcn: '<S7>/Stab_r' */
    rtb_u2rhoV2 = rtb_Add4_idx_2 * rtb_SumofDatum_k - tmp_0[0] *
      rtb_SumofControls_g;

    /* Lookup_n-D: '<S90>/CDd01' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_1f[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_1d[0U] = frac;
    bpIndices_1f[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_1d[1U] = frac;
    bpIndices_1f[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_1d[2U] = frac;
    rtb_Product2_hi = intrp3d_l_pw(bpIndices_1f, fractions_1d,
      SkySurfer_Core_P.CDd01, SkySurfer_Core_P.CDd01_dimSizes);

    /* Lookup_n-D: '<S90>/CDd02' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_1g[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_1e[0U] = frac;
    bpIndices_1g[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_1e[1U] = frac;
    bpIndices_1g[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_1e[2U] = frac;
    rtb_Product2_g5 = intrp3d_l_pw(bpIndices_1g, fractions_1e,
      SkySurfer_Core_P.CDd02, SkySurfer_Core_P.CDd02_dimSizes);

    /* Lookup_n-D: '<S90>/CDd03' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_1h[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_1f[0U] = frac;
    bpIndices_1h[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_1f[1U] = frac;
    bpIndices_1h[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_1f[2U] = frac;
    rtb_Product2_pw = intrp3d_l_pw(bpIndices_1h, fractions_1f,
      SkySurfer_Core_P.CDd03, SkySurfer_Core_P.CDd03_dimSizes);

    /* Lookup_n-D: '<S90>/CDd04' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_1i[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_1g[0U] = frac;
    bpIndices_1i[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_1g[1U] = frac;
    bpIndices_1i[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_1g[2U] = frac;
    rtb_Product2_ox = intrp3d_l_pw(bpIndices_1i, fractions_1g,
      SkySurfer_Core_P.CDd04, SkySurfer_Core_P.CDd04_dimSizes);

    /* Sum: '<S90>/Sum4' incorporates:
     *  Constant: '<S90>/Constant'
     *  Gain: '<S90>/Multiply1'
     *  Product: '<S90>/Product10'
     *  Product: '<S90>/Product3'
     *  Product: '<S90>/Product4'
     *  Product: '<S90>/Product5'
     *  Product: '<S90>/Product6'
     *  Product: '<S90>/Product7'
     *  Sum: '<S90>/Sum of Controls'
     *  Sum: '<S90>/Sum of Datum'
     *  Sum: '<S90>/Sum1'
     */
    rtb_Product14_hm = (((SkySurfer_Core_P.b / 2.0 * (rtb_jxi * rtb_u2rhoV2) +
                          (rtb_Multiply5_o + rtb_Product14_hm)) / rtb_Airspeed +
                         rtb_DotProduct) + SkySurfer_Core_P.CD_fix_AVL) +
      (((rtb_Product2_hi * rtb_Product_op + rtb_Product2_g5 * rtb_Product1_p4) +
        rtb_Product2_pw * rtb_Product2_my) + rtb_Product2_ox * rtb_q1dot);

    /* Lookup_n-D: '<S98>/CYtot' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_1j[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_1h[0U] = frac;
    bpIndices_1j[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_1h[1U] = frac;
    bpIndices_1j[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_1h[2U] = frac;
    rtb_Product2_hi = intrp3d_l_pw(bpIndices_1j, fractions_1h,
      SkySurfer_Core_P.CYtot, SkySurfer_Core_P.CYtot_dimSizes);

    /* Lookup_n-D: '<S98>/CYp' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_1k[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_1i[0U] = frac;
    bpIndices_1k[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_1i[1U] = frac;
    bpIndices_1k[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_1i[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_1k, fractions_1i,
      SkySurfer_Core_P.CYp, SkySurfer_Core_P.CYp_dimSizes);

    /* Gain: '<S98>/Multiply' incorporates:
     *  Product: '<S98>/Product1'
     */
    rtb_jxi = SkySurfer_Core_P.b / 2.0 * (rtb_DotProduct * rtb_Product1_ex);

    /* Lookup_n-D: '<S98>/CYq' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_1l[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_1j[0U] = frac;
    bpIndices_1l[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_1j[1U] = frac;
    bpIndices_1l[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_1j[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_1l, fractions_1j,
      SkySurfer_Core_P.CYq, SkySurfer_Core_P.CYq_dimSizes);

    /* Gain: '<S98>/Multiply2' incorporates:
     *  Product: '<S98>/Product2'
     */
    rtb_Multiply5_o = SkySurfer_Core_P.cbar / 2.0 * (rtb_DotProduct * tmp_0[1]);

    /* Lookup_n-D: '<S98>/CYr' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_1m[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_1k[0U] = frac;
    bpIndices_1m[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_1k[1U] = frac;
    bpIndices_1m[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_1k[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_1m, fractions_1k,
      SkySurfer_Core_P.CYr, SkySurfer_Core_P.CYr_dimSizes);

    /* Sum: '<S98>/Sum of Datum' incorporates:
     *  Gain: '<S98>/Multiply1'
     *  Product: '<S98>/Product10'
     *  Product: '<S98>/Product3'
     *  Sum: '<S98>/Sum1'
     */
    rtb_SumofDatum_k = (SkySurfer_Core_P.b / 2.0 * (rtb_DotProduct * rtb_u2rhoV2)
                        + (rtb_jxi + rtb_Multiply5_o)) / rtb_Airspeed +
      rtb_Product2_hi;

    /* Lookup_n-D: '<S98>/CYd01' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_1n[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_1l[0U] = frac;
    bpIndices_1n[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_1l[1U] = frac;
    bpIndices_1n[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_1l[2U] = frac;
    rtb_Product2_hi = intrp3d_l_pw(bpIndices_1n, fractions_1l,
      SkySurfer_Core_P.CYd01, SkySurfer_Core_P.CYd01_dimSizes);

    /* Lookup_n-D: '<S98>/CYd02' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_1o[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_1m[0U] = frac;
    bpIndices_1o[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_1m[1U] = frac;
    bpIndices_1o[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_1m[2U] = frac;
    rtb_Product2_g5 = intrp3d_l_pw(bpIndices_1o, fractions_1m,
      SkySurfer_Core_P.CYd02, SkySurfer_Core_P.CYd02_dimSizes);

    /* Lookup_n-D: '<S98>/CYd03' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_1p[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_1n[0U] = frac;
    bpIndices_1p[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_1n[1U] = frac;
    bpIndices_1p[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_1n[2U] = frac;
    rtb_Product2_pw = intrp3d_l_pw(bpIndices_1p, fractions_1n,
      SkySurfer_Core_P.CYd03, SkySurfer_Core_P.CYd03_dimSizes);

    /* Lookup_n-D: '<S98>/CYd04' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_1q[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_1o[0U] = frac;
    bpIndices_1q[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_1o[1U] = frac;
    bpIndices_1q[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_1o[2U] = frac;
    rtb_Product2_ox = intrp3d_l_pw(bpIndices_1q, fractions_1o,
      SkySurfer_Core_P.CYd04, SkySurfer_Core_P.CYd04_dimSizes);

    /* Sum: '<S98>/Sum of Controls' incorporates:
     *  Product: '<S98>/Product4'
     *  Product: '<S98>/Product5'
     *  Product: '<S98>/Product6'
     *  Product: '<S98>/Product7'
     */
    rtb_SumofControls_g = ((rtb_Product2_hi * rtb_Product_op + rtb_Product2_g5 *
      rtb_Product1_p4) + rtb_Product2_pw * rtb_Product2_my) + rtb_Product2_ox *
      rtb_q1dot;

    /* Lookup_n-D: '<S92>/CLtot' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_1r[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_1p[0U] = frac;
    bpIndices_1r[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_1p[1U] = frac;
    bpIndices_1r[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_1p[2U] = frac;
    rtb_Product2_hi = intrp3d_l_pw(bpIndices_1r, fractions_1p,
      SkySurfer_Core_P.CLtot, SkySurfer_Core_P.CLtot_dimSizes);

    /* Lookup_n-D: '<S92>/CLp' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_1s[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_1q[0U] = frac;
    bpIndices_1s[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_1q[1U] = frac;
    bpIndices_1s[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_1q[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_1s, fractions_1q,
      SkySurfer_Core_P.CLp, SkySurfer_Core_P.CLp_dimSizes);

    /* Gain: '<S92>/Multiply' incorporates:
     *  Product: '<S92>/Product1'
     */
    rtb_jxi = SkySurfer_Core_P.b / 2.0 * (rtb_DotProduct * rtb_Product1_ex);

    /* Lookup_n-D: '<S92>/CLq' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_1t[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_1r[0U] = frac;
    bpIndices_1t[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_1r[1U] = frac;
    bpIndices_1t[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_1r[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_1t, fractions_1r,
      SkySurfer_Core_P.CLq, SkySurfer_Core_P.CLq_dimSizes);

    /* Gain: '<S92>/Multiply2' incorporates:
     *  Product: '<S92>/Product2'
     */
    rtb_Multiply5_o = SkySurfer_Core_P.cbar / 2.0 * (rtb_DotProduct * tmp_0[1]);

    /* Lookup_n-D: '<S92>/CLr' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_1u[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_1s[0U] = frac;
    bpIndices_1u[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_1s[1U] = frac;
    bpIndices_1u[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_1s[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_1u, fractions_1s,
      SkySurfer_Core_P.CLr, SkySurfer_Core_P.CLr_dimSizes);

    /* Sum: '<S92>/Sum of Datum' incorporates:
     *  Gain: '<S92>/Multiply1'
     *  Product: '<S92>/Product10'
     *  Product: '<S92>/Product3'
     *  Sum: '<S92>/Sum1'
     */
    rtb_SumofDatum_ax = (SkySurfer_Core_P.b / 2.0 * (rtb_DotProduct *
      rtb_u2rhoV2) + (rtb_jxi + rtb_Multiply5_o)) / rtb_Airspeed +
      rtb_Product2_hi;

    /* Lookup_n-D: '<S92>/CLd01' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_1v[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_1t[0U] = frac;
    bpIndices_1v[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_1t[1U] = frac;
    bpIndices_1v[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_1t[2U] = frac;
    rtb_Product2_hi = intrp3d_l_pw(bpIndices_1v, fractions_1t,
      SkySurfer_Core_P.CLd01, SkySurfer_Core_P.CLd01_dimSizes);

    /* Lookup_n-D: '<S92>/CLd02' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_1w[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_1u[0U] = frac;
    bpIndices_1w[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_1u[1U] = frac;
    bpIndices_1w[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_1u[2U] = frac;
    rtb_Product2_g5 = intrp3d_l_pw(bpIndices_1w, fractions_1u,
      SkySurfer_Core_P.CLd02, SkySurfer_Core_P.CLd02_dimSizes);

    /* Lookup_n-D: '<S92>/CLd03' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_1x[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_1v[0U] = frac;
    bpIndices_1x[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_1v[1U] = frac;
    bpIndices_1x[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_1v[2U] = frac;
    rtb_Product2_pw = intrp3d_l_pw(bpIndices_1x, fractions_1v,
      SkySurfer_Core_P.CLd03, SkySurfer_Core_P.CLd03_dimSizes);

    /* Lookup_n-D: '<S92>/CLd04' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_1y[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_1w[0U] = frac;
    bpIndices_1y[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_1w[1U] = frac;
    bpIndices_1y[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_1w[2U] = frac;
    rtb_Product2_ox = intrp3d_l_pw(bpIndices_1y, fractions_1w,
      SkySurfer_Core_P.CLd04, SkySurfer_Core_P.CLd04_dimSizes);

    /* Sum: '<S92>/Sum of Controls' incorporates:
     *  Product: '<S92>/Product4'
     *  Product: '<S92>/Product5'
     *  Product: '<S92>/Product6'
     *  Product: '<S92>/Product7'
     */
    rtb_SumofControls_o = ((rtb_Product2_hi * rtb_Product_op + rtb_Product2_g5 *
      rtb_Product1_p4) + rtb_Product2_pw * rtb_Product2_my) + rtb_Product2_ox *
      rtb_q1dot;

    /* Lookup_n-D: '<S99>/Cltot' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_1z[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_1x[0U] = frac;
    bpIndices_1z[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_1x[1U] = frac;
    bpIndices_1z[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_1x[2U] = frac;
    rtb_Product2_hi = intrp3d_l_pw(bpIndices_1z, fractions_1x,
      SkySurfer_Core_P.Cltot, SkySurfer_Core_P.Cltot_dimSizes);

    /* Lookup_n-D: '<S99>/Clp' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_20[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_1y[0U] = frac;
    bpIndices_20[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_1y[1U] = frac;
    bpIndices_20[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_1y[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_20, fractions_1y,
      SkySurfer_Core_P.Clp, SkySurfer_Core_P.Clp_dimSizes);

    /* Gain: '<S99>/Multiply' incorporates:
     *  Product: '<S99>/Product1'
     */
    rtb_jxi = SkySurfer_Core_P.b / 2.0 * (rtb_DotProduct * rtb_Product1_ex);

    /* Lookup_n-D: '<S99>/Clq' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_21[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_1z[0U] = frac;
    bpIndices_21[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_1z[1U] = frac;
    bpIndices_21[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_1z[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_21, fractions_1z,
      SkySurfer_Core_P.Clq, SkySurfer_Core_P.Clq_dimSizes);

    /* Gain: '<S99>/Multiply2' incorporates:
     *  Product: '<S99>/Product2'
     */
    rtb_Multiply5_o = SkySurfer_Core_P.cbar / 2.0 * (rtb_DotProduct * tmp_0[1]);

    /* Lookup_n-D: '<S99>/Clr' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_22[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_20[0U] = frac;
    bpIndices_22[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_20[1U] = frac;
    bpIndices_22[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_20[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_22, fractions_20,
      SkySurfer_Core_P.Clr, SkySurfer_Core_P.Clr_dimSizes);

    /* Lookup_n-D: '<S99>/Cld01' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_23[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_21[0U] = frac;
    bpIndices_23[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_21[1U] = frac;
    bpIndices_23[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_21[2U] = frac;
    rtb_Product2_g5 = intrp3d_l_pw(bpIndices_23, fractions_21,
      SkySurfer_Core_P.Cld01, SkySurfer_Core_P.Cld01_dimSizes);

    /* Lookup_n-D: '<S99>/Cld02' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_24[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_22[0U] = frac;
    bpIndices_24[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_22[1U] = frac;
    bpIndices_24[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_22[2U] = frac;
    rtb_Product2_pw = intrp3d_l_pw(bpIndices_24, fractions_22,
      SkySurfer_Core_P.Cld02, SkySurfer_Core_P.Cld02_dimSizes);

    /* Lookup_n-D: '<S99>/Cld03' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_25[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_23[0U] = frac;
    bpIndices_25[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_23[1U] = frac;
    bpIndices_25[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_23[2U] = frac;
    rtb_Product2_ox = intrp3d_l_pw(bpIndices_25, fractions_23,
      SkySurfer_Core_P.Cld03, SkySurfer_Core_P.Cld03_dimSizes);

    /* Lookup_n-D: '<S99>/Cld04' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_26[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_24[0U] = frac;
    bpIndices_26[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_24[1U] = frac;
    bpIndices_26[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_24[2U] = frac;
    rtb_Product2_aw = intrp3d_l_pw(bpIndices_26, fractions_24,
      SkySurfer_Core_P.Cld04, SkySurfer_Core_P.Cld04_dimSizes);

    /* Sum: '<S99>/Sum4' incorporates:
     *  Gain: '<S99>/Gain'
     *  Gain: '<S99>/Multiply1'
     *  Product: '<S99>/Product10'
     *  Product: '<S99>/Product3'
     *  Product: '<S99>/Product4'
     *  Product: '<S99>/Product5'
     *  Product: '<S99>/Product6'
     *  Product: '<S99>/Product7'
     *  Sum: '<S99>/Sum of Controls'
     *  Sum: '<S99>/Sum of Datum'
     *  Sum: '<S99>/Sum1'
     */
    rtb_Sum4_h1 = ((SkySurfer_Core_P.b / 2.0 * (rtb_DotProduct * rtb_u2rhoV2) +
                    (rtb_jxi + rtb_Multiply5_o)) / rtb_Airspeed +
                   rtb_Product2_hi) + (((rtb_Product2_g5 * rtb_Product_op +
      rtb_Product2_pw * rtb_Product1_p4) + rtb_Product2_ox * rtb_Product2_my) +
      rtb_Product2_aw * rtb_q1dot) * SkySurfer_Core_P.Gain_Gain;

    /* Lookup_n-D: '<S100>/Cmtot' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_27[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_25[0U] = frac;
    bpIndices_27[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_25[1U] = frac;
    bpIndices_27[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_25[2U] = frac;
    rtb_Product2_hi = intrp3d_l_pw(bpIndices_27, fractions_25,
      SkySurfer_Core_P.Cmtot, SkySurfer_Core_P.Cmtot_dimSizes);

    /* Lookup_n-D: '<S100>/Cmp' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_28[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_26[0U] = frac;
    bpIndices_28[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_26[1U] = frac;
    bpIndices_28[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_26[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_28, fractions_26,
      SkySurfer_Core_P.Cmp, SkySurfer_Core_P.Cmp_dimSizes);

    /* Gain: '<S100>/Multiply' incorporates:
     *  Product: '<S100>/Product1'
     */
    rtb_jxi = SkySurfer_Core_P.b / 2.0 * (rtb_DotProduct * rtb_Product1_ex);

    /* Lookup_n-D: '<S100>/Cmq' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_29[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_27[0U] = frac;
    bpIndices_29[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_27[1U] = frac;
    bpIndices_29[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_27[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_29, fractions_27,
      SkySurfer_Core_P.Cmq, SkySurfer_Core_P.Cmq_dimSizes);

    /* Gain: '<S100>/Multiply2' incorporates:
     *  Product: '<S100>/Product2'
     */
    rtb_Multiply5_o = SkySurfer_Core_P.cbar / 2.0 * (rtb_DotProduct * tmp_0[1]);

    /* Lookup_n-D: '<S100>/Cmr' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_2a[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_28[0U] = frac;
    bpIndices_2a[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_28[1U] = frac;
    bpIndices_2a[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_28[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_2a, fractions_28,
      SkySurfer_Core_P.Cmr, SkySurfer_Core_P.Cmr_dimSizes);

    /* Sum: '<S100>/Sum of Datum' incorporates:
     *  Gain: '<S100>/Multiply1'
     *  Product: '<S100>/Product10'
     *  Product: '<S100>/Product3'
     *  Sum: '<S100>/Sum1'
     */
    rtb_SumofDatum_g = (SkySurfer_Core_P.b / 2.0 * (rtb_DotProduct * rtb_u2rhoV2)
                        + (rtb_jxi + rtb_Multiply5_o)) / rtb_Airspeed +
      rtb_Product2_hi;

    /* Lookup_n-D: '<S100>/Cmd01' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_2b[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_29[0U] = frac;
    bpIndices_2b[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_29[1U] = frac;
    bpIndices_2b[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_29[2U] = frac;
    rtb_Product2_hi = intrp3d_l_pw(bpIndices_2b, fractions_29,
      SkySurfer_Core_P.Cmd01, SkySurfer_Core_P.Cmd01_dimSizes);

    /* Lookup_n-D: '<S100>/Cmd02' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_2c[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_2a[0U] = frac;
    bpIndices_2c[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_2a[1U] = frac;
    bpIndices_2c[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_2a[2U] = frac;
    rtb_Product2_g5 = intrp3d_l_pw(bpIndices_2c, fractions_2a,
      SkySurfer_Core_P.Cmd02, SkySurfer_Core_P.Cmd02_dimSizes);

    /* Lookup_n-D: '<S100>/Cmd03' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_2d[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_2b[0U] = frac;
    bpIndices_2d[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_2b[1U] = frac;
    bpIndices_2d[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_2b[2U] = frac;
    rtb_Product2_pw = intrp3d_l_pw(bpIndices_2d, fractions_2b,
      SkySurfer_Core_P.Cmd03, SkySurfer_Core_P.Cmd03_dimSizes);

    /* Lookup_n-D: '<S100>/Cmd04' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_2e[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_2c[0U] = frac;
    bpIndices_2e[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_2c[1U] = frac;
    bpIndices_2e[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_2c[2U] = frac;
    rtb_Product2_ox = intrp3d_l_pw(bpIndices_2e, fractions_2c,
      SkySurfer_Core_P.Cmd04, SkySurfer_Core_P.Cmd04_dimSizes);

    /* Lookup_n-D: '<S101>/Cntot' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_2f[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_2d[0U] = frac;
    bpIndices_2f[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_2d[1U] = frac;
    bpIndices_2f[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_2d[2U] = frac;
    rtb_Product2_aw = intrp3d_l_pw(bpIndices_2f, fractions_2d,
      SkySurfer_Core_P.Cntot, SkySurfer_Core_P.Cntot_dimSizes);

    /* Lookup_n-D: '<S101>/Cnp' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_2g[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_2e[0U] = frac;
    bpIndices_2g[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_2e[1U] = frac;
    bpIndices_2g[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_2e[2U] = frac;
    rtb_DotProduct = intrp3d_l_pw(bpIndices_2g, fractions_2e,
      SkySurfer_Core_P.Cnp, SkySurfer_Core_P.Cnp_dimSizes);

    /* Lookup_n-D: '<S101>/Cnq' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_2h[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_2f[0U] = frac;
    bpIndices_2h[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_2f[1U] = frac;
    bpIndices_2h[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_2f[2U] = frac;
    rtb_Product1_e = intrp3d_l_pw(bpIndices_2h, fractions_2f,
      SkySurfer_Core_P.Cnq, SkySurfer_Core_P.Cnq_dimSizes);

    /* Lookup_n-D: '<S101>/Cnr' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_2i[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_2g[0U] = frac;
    bpIndices_2i[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_2g[1U] = frac;
    bpIndices_2i[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_2g[2U] = frac;
    rtb_Product1_pw = intrp3d_l_pw(bpIndices_2i, fractions_2g,
      SkySurfer_Core_P.Cnr, SkySurfer_Core_P.Cnr_dimSizes);

    /* Lookup_n-D: '<S101>/Cnd01' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_2j[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_2h[0U] = frac;
    bpIndices_2j[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_2h[1U] = frac;
    bpIndices_2j[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_2h[2U] = frac;
    rtb_u2rhoV2_i = intrp3d_l_pw(bpIndices_2j, fractions_2h,
      SkySurfer_Core_P.Cnd01, SkySurfer_Core_P.Cnd01_dimSizes);

    /* Lookup_n-D: '<S101>/Cnd02' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_2k[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_2i[0U] = frac;
    bpIndices_2k[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_2i[1U] = frac;
    bpIndices_2k[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_2i[2U] = frac;
    rtb_u2rhoV2_n = intrp3d_l_pw(bpIndices_2k, fractions_2i,
      SkySurfer_Core_P.Cnd02, SkySurfer_Core_P.Cnd02_dimSizes);

    /* Lookup_n-D: '<S101>/Cnd03' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_2l[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_2j[0U] = frac;
    bpIndices_2l[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_2j[1U] = frac;
    bpIndices_2l[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_2j[2U] = frac;
    rtb_u2rhoV2_m = intrp3d_l_pw(bpIndices_2l, fractions_2j,
      SkySurfer_Core_P.Cnd03, SkySurfer_Core_P.Cnd03_dimSizes);

    /* Lookup_n-D: '<S101>/Cnd04' incorporates:
     *  SignalConversion generated from: '<S90>/CDd01'
     */
    bpIndices_2m[0U] = plook_binx(rtb_Product1_ow, SkySurfer_Core_P.mach_avl, 1U,
      &frac);
    fractions_2k[0U] = frac;
    bpIndices_2m[1U] = plook_binx(rtb_Gain, SkySurfer_Core_P.alpha_avl, 5U,
      &frac);
    fractions_2k[1U] = frac;
    bpIndices_2m[2U] = plook_binx(rtb_Gain_h, SkySurfer_Core_P.beta_avl, 4U,
      &frac);
    fractions_2k[2U] = frac;
    rtb_u2rhoV2_e = intrp3d_l_pw(bpIndices_2m, fractions_2k,
      SkySurfer_Core_P.Cnd04, SkySurfer_Core_P.Cnd04_dimSizes);

    /* Gain: '<S103>/1//2rhoV^2' incorporates:
     *  Product: '<S103>/Product2'
     */
    rtb_jxi = rtb_Airspeed_tmp * rtb_rho0 * SkySurfer_Core_P.u2rhoV2_Gain;

    /* AerodynamicForcesAndMoments: '<S7>/Aerodynamic Forces and Moments 1' incorporates:
     *  Constant: '<S7>/b3'
     *  Constant: '<S7>/b4'
     *  Gain: '<S101>/Multiply'
     *  Gain: '<S101>/Multiply1'
     *  Gain: '<S101>/Multiply2'
     *  Product: '<S100>/Product4'
     *  Product: '<S100>/Product5'
     *  Product: '<S100>/Product6'
     *  Product: '<S100>/Product7'
     *  Product: '<S101>/Product1'
     *  Product: '<S101>/Product10'
     *  Product: '<S101>/Product2'
     *  Product: '<S101>/Product3'
     *  Product: '<S101>/Product4'
     *  Product: '<S101>/Product5'
     *  Product: '<S101>/Product6'
     *  Product: '<S101>/Product7'
     *  SignalConversion generated from: '<S7>/Aerodynamic Forces and Moments 1'
     *  Sum: '<S100>/Sum of Controls'
     *  Sum: '<S100>/Sum4'
     *  Sum: '<S101>/Sum of Controls'
     *  Sum: '<S101>/Sum of Datum'
     *  Sum: '<S101>/Sum1'
     *  Sum: '<S101>/Sum4'
     *  Sum: '<S92>/Sum4'
     *  Sum: '<S98>/Sum4'
     */
    rtb_Airspeed_tmp = rt_atan2d_snf(rtb_sincos_o1_idx_2,
      rtb_VectorConcatenate_idx_6);
    rtb_Multiply5_o = rt_atan2d_snf(rtb_sincos_o1_idx_2,
      rtb_VectorConcatenate_idx_6);
    pData_idx_0 = rt_atan2d_snf(rtb_sincos_o1_idx_2, rtb_VectorConcatenate_idx_6);
    frac = -rtb_Product14_hm * rtb_jxi * SkySurfer_Core_P.S;
    rtb_Product14_hm = (rtb_SumofDatum_k + rtb_SumofControls_g) * rtb_jxi *
      SkySurfer_Core_P.S;
    rtb_SumofDatum_k = -(rtb_SumofDatum_ax + rtb_SumofControls_o) * rtb_jxi *
      SkySurfer_Core_P.S;
    _mm_storeu_pd(&tmp_0[0], _mm_sub_pd(_mm_set_pd(-SkySurfer_Core_P.CG_m[1],
      -SkySurfer_Core_P.CG_m[0]), _mm_set_pd(-SkySurfer_Core_P.XREF_m[1],
      -SkySurfer_Core_P.XREF_m[0])));
    rtb_SumofControls_g = -SkySurfer_Core_P.CG_m[2] - (-SkySurfer_Core_P.XREF_m
      [2]);
    rtb_SumofDatum_ax = sin(rtb_Multiply5_o);
    rtb_SumofControls_o = cos(rtb_Multiply5_o);
    pData_idx_0_tmp = 0.0 * tmp_0[1];
    rtb_Multiply5_o = (rtb_SumofControls_o * tmp_0[0] + pData_idx_0_tmp) +
      rtb_SumofDatum_ax * rtb_SumofControls_g;
    pData_idx_1 = (0.0 * tmp_0[0] + tmp_0[1]) + 0.0 * rtb_SumofControls_g;
    rtb_SumofControls_g = (-rtb_SumofDatum_ax * tmp_0[0] + pData_idx_0_tmp) +
      rtb_SumofControls_o * rtb_SumofControls_g;
    rtb_Sum4_h1 = rtb_Sum4_h1 * SkySurfer_Core_P.b * SkySurfer_Core_P.S *
      rtb_jxi + (rtb_Product14_hm * rtb_SumofControls_g - pData_idx_1 *
                 rtb_SumofDatum_k);
    rtb_Product2_hi = ((((rtb_Product2_hi * rtb_Product_op + rtb_Product2_g5 *
                          rtb_Product1_p4) + rtb_Product2_pw * rtb_Product2_my)
                        + rtb_Product2_ox * rtb_q1dot) + rtb_SumofDatum_g) *
      SkySurfer_Core_P.cbar * SkySurfer_Core_P.S * rtb_jxi + (rtb_Multiply5_o *
      rtb_SumofDatum_k - frac * rtb_SumofControls_g);
    rtb_SumofControls_g = ((((SkySurfer_Core_P.b / 2.0 * (rtb_DotProduct *
      rtb_Product1_ex) + SkySurfer_Core_P.cbar / 2.0 * (rtb_Product1_e *
      rtb_Add4_idx_1)) + SkySurfer_Core_P.b / 2.0 * (rtb_Product1_pw *
      rtb_u2rhoV2)) / rtb_Airspeed + rtb_Product2_aw) + (((rtb_u2rhoV2_i *
      rtb_Product_op + rtb_u2rhoV2_n * rtb_Product1_p4) + rtb_u2rhoV2_m *
      rtb_Product2_my) + rtb_u2rhoV2_e * rtb_q1dot)) * SkySurfer_Core_P.b *
      SkySurfer_Core_P.S * rtb_jxi + (frac * pData_idx_1 - rtb_Multiply5_o *
      rtb_Product14_hm);
    rtb_DotProduct = sin(rtb_Airspeed_tmp);
    rtb_Product_op = cos(rtb_Airspeed_tmp);
    rtb_q1dot = sin(pData_idx_0);
    rtb_Product1_p4 = cos(pData_idx_0);

    /* AerodynamicForcesAndMoments: '<S7>/Aerodynamic Forces and Moments ' incorporates:
     *  Constant: '<S7>/b1'
     *  Constant: '<S7>/b2'
     *  Constant: '<S91>/Constant'
     *  Sum: '<S91>/Sum2'
     *  Sum: '<S93>/Sum4'
     *  Sum: '<S94>/Sum4'
     *  Sum: '<S95>/Sum4'
     *  Sum: '<S97>/Sum4'
     */
    rtb_Airspeed_tmp = rt_atan2d_snf(rtb_sincos_o1_idx_2,
      rtb_VectorConcatenate_idx_6);
    rtb_SumofDatum_ax = sqrt(rtb_Merge_idx_0 + rtb_Merge_idx_1);
    pData_idx_1 = rt_atan2d_snf(rtb_sincos_o1_idx_1, rtb_SumofDatum_ax);
    rtb_SumofControls_o = cos(rtb_Airspeed_tmp);
    rtb_Merge_idx_0 = sin(rtb_Airspeed_tmp);
    rtb_Merge_idx_1 = cos(pData_idx_1);
    rtb_Product2_my = sin(pData_idx_1);
    rtb_Airspeed_tmp = rt_atan2d_snf(rtb_sincos_o1_idx_2,
      rtb_VectorConcatenate_idx_6);
    pData_idx_1 = rt_atan2d_snf(rtb_sincos_o1_idx_1, rtb_SumofDatum_ax);
    pData_idx_0 = cos(rtb_Airspeed_tmp);
    rtb_Product2_pw = sin(rtb_Airspeed_tmp);
    rtb_Product2_ox = cos(pData_idx_1);
    rtb_Product2_aw = sin(pData_idx_1);
    rtb_Airspeed_tmp = rt_atan2d_snf(rtb_sincos_o1_idx_2,
      rtb_VectorConcatenate_idx_6);
    pData_idx_1 = rt_atan2d_snf(rtb_sincos_o1_idx_1, rtb_SumofDatum_ax);
    rtb_SumofDatum_ax = cos(rtb_Airspeed_tmp);
    rtb_Product1_ex = sin(rtb_Airspeed_tmp);
    rtb_u2rhoV2 = cos(pData_idx_1);
    rtb_Product2_g5 = sin(pData_idx_1);
    rtb_Airspeed_tmp = -((rtb_Merge_idx_2 + SkySurfer_Core_P.CD_fix_VSP) +
                         rtb_Multiply2) * rtb_jxi * SkySurfer_Core_P.S;
    pData_idx_1 = -(rtb_Product7 + rtb_Product5) * rtb_jxi * SkySurfer_Core_P.S;
    rtb_Merge_idx_2 = -(rtb_Product14 + rtb_Product14_d) * rtb_jxi *
      SkySurfer_Core_P.S;
    _mm_storeu_pd(&tmp_0[0], _mm_sub_pd(_mm_set_pd(-SkySurfer_Core_P.CG_m[1],
      -SkySurfer_Core_P.CG_m[0]), _mm_set_pd(-SkySurfer_Core_P.XREF_m[1],
      -SkySurfer_Core_P.XREF_m[0])));
    rtb_Multiply2 = -SkySurfer_Core_P.CG_m[2] - (-SkySurfer_Core_P.XREF_m[2]);
    pData_idx_0_tmp = rtb_Product2_aw * 0.0;
    rtb_Product5 = rtb_Product2_ox * 0.0;
    rtb_Product14 = 0.0 * -rtb_Product2_pw;
    rtb_Product7 = 0.0 * pData_idx_0;
    rtb_Multiply5_o = (((rtb_Product2_ox * pData_idx_0 + pData_idx_0_tmp) +
                        rtb_Product14) * tmp_0[0] + (rtb_Product5 +
      rtb_Product2_aw) * tmp_0[1]) + ((rtb_Product2_ox * rtb_Product2_pw +
      pData_idx_0_tmp) + rtb_Product7) * rtb_Multiply2;
    rtb_Product5 = (((pData_idx_0 * -rtb_Product2_aw + rtb_Product5) +
                     rtb_Product14) * tmp_0[0] + (-rtb_Product2_aw * 0.0 +
      rtb_Product2_ox) * tmp_0[1]) + ((rtb_Product2_pw * -rtb_Product2_aw +
      rtb_Product5) + rtb_Product7) * rtb_Multiply2;
    rtb_Multiply2 = ((rtb_Product7 - rtb_Product2_pw) * tmp_0[0] + tmp_0[1] *
                     0.0) + (0.0 * rtb_Product2_pw + pData_idx_0) *
      rtb_Multiply2;
    pData_idx_0 = (rtb_Product16 + rtb_Product16_j) * SkySurfer_Core_P.b *
      SkySurfer_Core_P.S * rtb_jxi + (pData_idx_1 * rtb_Multiply2 - rtb_Product5
      * rtb_Merge_idx_2);
    rtb_Product7 = (rtb_Product16_a + rtb_Product14_k) * SkySurfer_Core_P.cbar *
      SkySurfer_Core_P.S * rtb_jxi + (rtb_Multiply5_o * rtb_Merge_idx_2 -
      rtb_Airspeed_tmp * rtb_Multiply2);
    rtb_Multiply2 = rtb_Product16_on * SkySurfer_Core_P.b * SkySurfer_Core_P.S *
      rtb_jxi + (rtb_Airspeed_tmp * rtb_Product5 - rtb_Multiply5_o * pData_idx_1);

    /* Switch: '<S7>/Switch' incorporates:
     *  Constant: '<S7>/b7'
     */
    if (SkySurfer_Core_P.useAVL_VSP > SkySurfer_Core_P.Switch_Threshold) {
      /* AerodynamicForcesAndMoments: '<S7>/Aerodynamic Forces and Moments ' */
      rtb_Product5 = 0.0 * -rtb_Merge_idx_0;

      /* Switch: '<S7>/Switch' incorporates:
       *  AerodynamicForcesAndMoments: '<S7>/Aerodynamic Forces and Moments '
       */
      SkySurfer_Core_DW->Switch[0] = (((rtb_Merge_idx_1 * rtb_SumofControls_o +
        rtb_Product2_my * 0.0) + rtb_Product5) * rtb_Airspeed_tmp +
        ((rtb_SumofControls_o * -rtb_Product2_my + rtb_Merge_idx_1 * 0.0) +
         rtb_Product5) * pData_idx_1) + (0.0 * rtb_SumofControls_o -
        rtb_Merge_idx_0) * rtb_Merge_idx_2;
    } else {
      /* Switch: '<S7>/Switch' incorporates:
       *  AerodynamicForcesAndMoments: '<S7>/Aerodynamic Forces and Moments 1'
       */
      SkySurfer_Core_DW->Switch[0] = (rtb_Product_op * frac + 0.0 *
        rtb_Product14_hm) + -rtb_DotProduct * rtb_SumofDatum_k;
    }

    /* Switch: '<S7>/Switch1' incorporates:
     *  Constant: '<S7>/b8'
     */
    if (SkySurfer_Core_P.useAVL_VSP > SkySurfer_Core_P.Switch1_Threshold) {
      /* AerodynamicForcesAndMoments: '<S7>/Aerodynamic Forces and Moments ' */
      rtb_Product5 = 0.0 * -rtb_Product1_ex;

      /* Switch: '<S7>/Switch1' incorporates:
       *  AerodynamicForcesAndMoments: '<S7>/Aerodynamic Forces and Moments '
       */
      SkySurfer_Core_DW->Switch1[0] = (((rtb_u2rhoV2 * rtb_SumofDatum_ax +
        rtb_Product2_g5 * 0.0) + rtb_Product5) * pData_idx_0 +
        ((rtb_SumofDatum_ax * -rtb_Product2_g5 + rtb_u2rhoV2 * 0.0) +
         rtb_Product5) * rtb_Product7) + (0.0 * rtb_SumofDatum_ax -
        rtb_Product1_ex) * rtb_Multiply2;
    } else {
      /* Switch: '<S7>/Switch1' incorporates:
       *  AerodynamicForcesAndMoments: '<S7>/Aerodynamic Forces and Moments 1'
       */
      SkySurfer_Core_DW->Switch1[0] = (rtb_Product1_p4 * rtb_Sum4_h1 + 0.0 *
        rtb_Product2_hi) + -rtb_q1dot * rtb_SumofControls_g;
    }

    /* Switch: '<S7>/Switch' incorporates:
     *  Constant: '<S7>/b7'
     */
    if (SkySurfer_Core_P.useAVL_VSP > SkySurfer_Core_P.Switch_Threshold) {
      /* Switch: '<S7>/Switch' incorporates:
       *  AerodynamicForcesAndMoments: '<S7>/Aerodynamic Forces and Moments '
       */
      SkySurfer_Core_DW->Switch[1] = ((rtb_Merge_idx_1 * 0.0 + rtb_Product2_my) *
        rtb_Airspeed_tmp + (-rtb_Product2_my * 0.0 + rtb_Merge_idx_1) *
        pData_idx_1) + rtb_Merge_idx_2 * 0.0;
    } else {
      /* Switch: '<S7>/Switch' incorporates:
       *  AerodynamicForcesAndMoments: '<S7>/Aerodynamic Forces and Moments 1'
       */
      SkySurfer_Core_DW->Switch[1] = (0.0 * frac + rtb_Product14_hm) + 0.0 *
        rtb_SumofDatum_k;
    }

    /* Switch: '<S7>/Switch1' incorporates:
     *  Constant: '<S7>/b8'
     */
    if (SkySurfer_Core_P.useAVL_VSP > SkySurfer_Core_P.Switch1_Threshold) {
      /* Switch: '<S7>/Switch1' incorporates:
       *  AerodynamicForcesAndMoments: '<S7>/Aerodynamic Forces and Moments '
       */
      SkySurfer_Core_DW->Switch1[1] = ((rtb_u2rhoV2 * 0.0 + rtb_Product2_g5) *
        pData_idx_0 + (-rtb_Product2_g5 * 0.0 + rtb_u2rhoV2) * rtb_Product7) +
        rtb_Multiply2 * 0.0;
    } else {
      /* Switch: '<S7>/Switch1' incorporates:
       *  AerodynamicForcesAndMoments: '<S7>/Aerodynamic Forces and Moments 1'
       */
      SkySurfer_Core_DW->Switch1[1] = (0.0 * rtb_Sum4_h1 + rtb_Product2_hi) +
        0.0 * rtb_SumofControls_g;
    }

    /* Switch: '<S7>/Switch' incorporates:
     *  Constant: '<S7>/b7'
     */
    if (SkySurfer_Core_P.useAVL_VSP > SkySurfer_Core_P.Switch_Threshold) {
      /* AerodynamicForcesAndMoments: '<S7>/Aerodynamic Forces and Moments ' */
      rtb_Product5 = 0.0 * rtb_SumofControls_o;

      /* Switch: '<S7>/Switch' incorporates:
       *  AerodynamicForcesAndMoments: '<S7>/Aerodynamic Forces and Moments '
       */
      SkySurfer_Core_DW->Switch[2] = (((rtb_Merge_idx_1 * rtb_Merge_idx_0 +
        rtb_Product2_my * 0.0) + rtb_Product5) * rtb_Airspeed_tmp +
        ((rtb_Merge_idx_0 * -rtb_Product2_my + rtb_Merge_idx_1 * 0.0) +
         rtb_Product5) * pData_idx_1) + (0.0 * rtb_Merge_idx_0 +
        rtb_SumofControls_o) * rtb_Merge_idx_2;
    } else {
      /* Switch: '<S7>/Switch' incorporates:
       *  AerodynamicForcesAndMoments: '<S7>/Aerodynamic Forces and Moments 1'
       */
      SkySurfer_Core_DW->Switch[2] = (rtb_DotProduct * frac + 0.0 *
        rtb_Product14_hm) + rtb_Product_op * rtb_SumofDatum_k;
    }

    /* Switch: '<S7>/Switch1' incorporates:
     *  Constant: '<S7>/b8'
     */
    if (SkySurfer_Core_P.useAVL_VSP > SkySurfer_Core_P.Switch1_Threshold) {
      /* AerodynamicForcesAndMoments: '<S7>/Aerodynamic Forces and Moments ' */
      rtb_Product5 = 0.0 * rtb_SumofDatum_ax;

      /* Switch: '<S7>/Switch1' incorporates:
       *  AerodynamicForcesAndMoments: '<S7>/Aerodynamic Forces and Moments '
       */
      SkySurfer_Core_DW->Switch1[2] = (((rtb_u2rhoV2 * rtb_Product1_ex +
        rtb_Product2_g5 * 0.0) + rtb_Product5) * pData_idx_0 + ((rtb_Product1_ex
        * -rtb_Product2_g5 + rtb_u2rhoV2 * 0.0) + rtb_Product5) * rtb_Product7)
        + (0.0 * rtb_Product1_ex + rtb_SumofDatum_ax) * rtb_Multiply2;
    } else {
      /* Switch: '<S7>/Switch1' incorporates:
       *  AerodynamicForcesAndMoments: '<S7>/Aerodynamic Forces and Moments 1'
       */
      SkySurfer_Core_DW->Switch1[2] = (rtb_q1dot * rtb_Sum4_h1 + 0.0 *
        rtb_Product2_hi) + rtb_Product1_p4 * rtb_SumofControls_g;
    }
  }

  /* End of Outputs for SubSystem: '<S5>/Aerodynamic' */

  /* Switch: '<S5>/Switch2' incorporates:
   *  Constant: '<S5>/Constant6'
   */
  if (rtb_Airspeed > SkySurfer_Core_P.Switch2_Threshold) {
    rtb_Merge_idx_0 = SkySurfer_Core_DW->Switch1[0];
    rtb_Merge_idx_1 = SkySurfer_Core_DW->Switch1[1];
    rtb_Merge_idx_2 = SkySurfer_Core_DW->Switch1[2];
  } else {
    rtb_Merge_idx_0 = SkySurfer_Core_P.Constant6_Value[0];
    rtb_Merge_idx_1 = SkySurfer_Core_P.Constant6_Value[1];
    rtb_Merge_idx_2 = SkySurfer_Core_P.Constant6_Value[2];
  }

  /* End of Switch: '<S5>/Switch2' */

  /* Sum: '<S5>/Add1' incorporates:
   *  Constant: '<S12>/Constant'
   *  Constant: '<S12>/Constant4'
   */
  rtb_Add1_m[0] = SkySurfer_Core_P.Constant4_Value + rtb_Merge_idx_0;
  rtb_Add1_m[1] = rtb_Gain_az + rtb_Merge_idx_1;
  rtb_Add1_m[2] = SkySurfer_Core_P.Constant_Value_k5 + rtb_Merge_idx_2;
  if (tmp) {
    for (i = 0; i < 3; i++) {
      /* Selector: '<S16>/Selector1' incorporates:
       *  Concatenate: '<S15>/Matrix Concatenation'
       */
      SkySurfer_Core_DW->Selector1[3 * i] = rtb_MatrixConcatenation[6 * i + 3];

      /* Selector: '<S16>/Selector' incorporates:
       *  Concatenate: '<S15>/Matrix Concatenation'
       */
      SkySurfer_Core_DW->Selector[3 * i] = rtb_MatrixConcatenation[6 * i];

      /* Selector: '<S16>/Selector1' incorporates:
       *  Selector: '<S16>/Selector'
       */
      rtb_MatrixConcatenation_tmp = 3 * i + 1;

      /* Selector: '<S16>/Selector1' incorporates:
       *  Concatenate: '<S15>/Matrix Concatenation'
       */
      SkySurfer_Core_DW->Selector1[rtb_MatrixConcatenation_tmp] =
        rtb_MatrixConcatenation[6 * i + 4];

      /* Selector: '<S16>/Selector' incorporates:
       *  Concatenate: '<S15>/Matrix Concatenation'
       */
      SkySurfer_Core_DW->Selector[rtb_MatrixConcatenation_tmp] =
        rtb_MatrixConcatenation[6 * i + 1];

      /* Selector: '<S16>/Selector1' incorporates:
       *  Selector: '<S16>/Selector'
       */
      rtb_MatrixConcatenation_tmp = 3 * i + 2;

      /* Selector: '<S16>/Selector1' incorporates:
       *  Concatenate: '<S15>/Matrix Concatenation'
       */
      SkySurfer_Core_DW->Selector1[rtb_MatrixConcatenation_tmp] =
        rtb_MatrixConcatenation[6 * i + 5];

      /* Selector: '<S16>/Selector' incorporates:
       *  Concatenate: '<S15>/Matrix Concatenation'
       */
      SkySurfer_Core_DW->Selector[rtb_MatrixConcatenation_tmp] =
        rtb_MatrixConcatenation[6 * i + 2];
    }
  }

  /* Product: '<S84>/Product' incorporates:
   *  Reshape: '<S84>/Reshape1'
   *  Selector: '<S16>/Selector'
   *  Switch: '<S5>/Switch1'
   */
  rtb_Multiply2 = 0.0;
  rtb_Product7 = 0.0;
  rtb_Product5 = 0.0;
  for (i = 0; i < 3; i++) {
    _mm_storeu_pd(&tmp_0[0], _mm_add_pd(_mm_mul_pd(_mm_loadu_pd
      (&SkySurfer_Core_DW->Selector[3 * i]), _mm_set1_pd(rtb_u[i])), _mm_set_pd
      (rtb_Product7, rtb_Multiply2)));
    rtb_Multiply2 = tmp_0[0];
    rtb_Product7 = tmp_0[1];
    rtb_Product5 += SkySurfer_Core_DW->Selector[3 * i + 2] * rtb_u[i];
  }

  /* End of Product: '<S84>/Product' */

  /* Product: '<S85>/Product' incorporates:
   *  Reshape: '<S85>/Reshape1'
   *  Selector: '<S16>/Selector1'
   */
  rtb_Product16 = 0.0;
  rtb_DotProduct = 0.0;
  rtb_Product14 = 0.0;
  for (i = 0; i < 3; i++) {
    _mm_storeu_pd(&tmp_0[0], _mm_add_pd(_mm_mul_pd(_mm_loadu_pd
      (&SkySurfer_Core_DW->Selector1[3 * i]), _mm_set1_pd(rtb_u[i])), _mm_set_pd
      (rtb_DotProduct, rtb_Product16)));
    rtb_Product16 = tmp_0[0];
    rtb_DotProduct = tmp_0[1];
    rtb_Product14 += SkySurfer_Core_DW->Selector1[3 * i + 2] * rtb_u[i];
  }

  rtb_MatrixMultiply[2] = rtb_Product14;
  rtb_MatrixMultiply[1] = rtb_DotProduct;
  rtb_MatrixMultiply[0] = rtb_Product16;

  /* Product: '<S16>/Product2' incorporates:
   *  Product: '<S10>/Matrix Multiply'
   *  Product: '<S85>/Product'
   *  Product: '<S86>/i x j'
   *  Product: '<S86>/j x k'
   *  Product: '<S86>/k x i'
   *  Product: '<S87>/i x k'
   *  Product: '<S87>/j x i'
   *  Product: '<S87>/k x j'
   *  Reshape: '<S16>/Reshape'
   *  Selector: '<S16>/Selector2'
   *  Sum: '<S16>/Sum2'
   *  Sum: '<S83>/Sum'
   */
  _mm_storeu_pd(&fractions[0], _mm_sub_pd(_mm_sub_pd(_mm_loadu_pd(&rtb_Add1_m[0]),
    _mm_loadu_pd(&rtb_MatrixMultiply[0])), _mm_sub_pd(_mm_mul_pd(_mm_set_pd
    (rtb_Multiply2, rtb_u[1]), _mm_set_pd(rtb_u[2], rtb_Product5)), _mm_mul_pd
    (_mm_set_pd(rtb_u[0], rtb_Product7), _mm_set_pd(rtb_Product5, rtb_u[2])))));
  fractions[2] = (rtb_Add1_m[2] - rtb_Product14) - (rtb_u[0] * rtb_Product7 -
    rtb_Multiply2 * rtb_u[1]);
  rt_mrdivide_U1d1x3_U2d3x3_Yd1x3_snf(fractions, SkySurfer_Core_DW->Selector2,
    SkySurfer_Core_DW->Reshape);

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[19] = SkySurfer_Core_DW->Reshape[0];

  /* Switch: '<S5>/Switch1' incorporates:
   *  Constant: '<S5>/Constant5'
   */
  if (rtb_Airspeed > SkySurfer_Core_P.Switch1_Threshold_n) {
    rtb_Multiply2 = SkySurfer_Core_DW->Switch[0];
    rtb_Product7 = SkySurfer_Core_DW->Switch[1];
    rtb_Product5 = SkySurfer_Core_DW->Switch[2];
  } else {
    rtb_Multiply2 = SkySurfer_Core_P.Constant5_Value_d[0];
    rtb_Product7 = SkySurfer_Core_P.Constant5_Value_d[1];
    rtb_Product5 = SkySurfer_Core_P.Constant5_Value_d[2];
  }

  /* End of Switch: '<S5>/Switch1' */

  /* Product: '<S129>/Product' */
  rtb_Product14 = 0.0;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[20] = SkySurfer_Core_DW->Reshape[1];

  /* Product: '<S129>/Product' */
  rtb_Product16 = 0.0;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[21] = SkySurfer_Core_DW->Reshape[2];

  /* Product: '<S129>/Product' incorporates:
   *  Constant: '<S129>/Constant'
   *  Reshape: '<S32>/Reshape (9) to [3x3] column-major'
   */
  rtb_DotProduct = 0.0;
  for (i = 0; i < 3; i++) {
    _mm_storeu_pd(&tmp_0[0], _mm_add_pd(_mm_mul_pd(_mm_loadu_pd
      (&rtb_Reshape9to3x3columnmajor[3 * i]), _mm_set1_pd
      (SkySurfer_Core_P.Constant_Value_f0[i])), _mm_set_pd(rtb_Product16,
      rtb_Product14)));
    rtb_Product14 = tmp_0[0];
    rtb_Product16 = tmp_0[1];
    rtb_DotProduct += rtb_Reshape9to3x3columnmajor[3 * i + 2] *
      SkySurfer_Core_P.Constant_Value_f0[i];
  }

  /* Product: '<S129>/Product3' incorporates:
   *  Constant: '<S4>/const1'
   */
  rtb_Product14 *= SkySurfer_Core_P.Mass0;
  rtb_Product_op = SkySurfer_Core_P.Mass0 * rtb_Product16;
  rtb_Product16_j = SkySurfer_Core_P.Mass0 * rtb_DotProduct;

  /* Switch: '<S152>/Switch' incorporates:
   *  Constant: '<S152>/Constant'
   *  Gain: '<S152>/Damper'
   *  Gain: '<S152>/Spring Kp'
   *  Sum: '<S152>/Add'
   *  UnaryMinus: '<S152>/Unary Minus'
   *  UnaryMinus: '<S152>/Unary Minus1'
   */
  if (-rtb_Add_h_idx_2 > SkySurfer_Core_P.Switch_Threshold_n) {
    rtb_DotProduct = SkySurfer_Core_P.Constant_Value_d;
  } else {
    rtb_DotProduct = -SkySurfer_Core_P.uavData.contact.spring * -rtb_Add_h_idx_2
      + -SkySurfer_Core_P.uavData.contact.damper * -SkySurfer_Core_DW->Reshape2
      [2];
  }

  /* End of Switch: '<S152>/Switch' */

  /* Saturate: '<S152>/Saturation' */
  if (rtb_DotProduct > SkySurfer_Core_P.Saturation_UpperSat) {
    rtb_DotProduct = SkySurfer_Core_P.Saturation_UpperSat;
  } else if (rtb_DotProduct < SkySurfer_Core_P.Saturation_LowerSat) {
    rtb_DotProduct = SkySurfer_Core_P.Saturation_LowerSat;
  }

  /* End of Saturate: '<S152>/Saturation' */

  /* Gain: '<S153>/vd' */
  rtb_Product16 = 1.0 / SkySurfer_Core_P.uavData.contact.vd;

  /* SignalConversion generated from: '<S10>/Matrix Multiply' incorporates:
   *  Gain: '<S153>/friction coefficient'
   *  Gain: '<S153>/vd'
   *  Product: '<S151>/Product'
   *  Trigonometry: '<S153>/Tanh'
   *  UnaryMinus: '<S10>/Unary Minus1'
   *  UnaryMinus: '<S151>/Unary Minus'
   */
  rtb_MatrixMultiply[0] = -(tanh(rtb_Product16 * SkySurfer_Core_DW->Reshape2[0])
    * SkySurfer_Core_P.uavData.contact.rollingFriction * rtb_DotProduct);
  rtb_MatrixMultiply[1] = -(tanh(rtb_Product16 * SkySurfer_Core_DW->Reshape2[1])
    * SkySurfer_Core_P.uavData.contact.rollingFriction * rtb_DotProduct);
  rtb_MatrixMultiply[2] = -rtb_DotProduct;

  /* Product: '<S10>/Matrix Multiply' incorporates:
   *  Reshape: '<S32>/Reshape (9) to [3x3] column-major'
   */
  rtb_DotProduct = 0.0;
  rtb_Product16 = 0.0;
  rtb_Product14_d = 0.0;
  for (i = 0; i < 3; i++) {
    _mm_storeu_pd(&tmp_0[0], _mm_add_pd(_mm_mul_pd(_mm_loadu_pd
      (&rtb_Reshape9to3x3columnmajor[3 * i]), _mm_set1_pd(rtb_MatrixMultiply[i])),
      _mm_set_pd(rtb_Product16, rtb_DotProduct)));
    rtb_DotProduct = tmp_0[0];
    rtb_Product16 = tmp_0[1];
    rtb_Product14_d += rtb_Reshape9to3x3columnmajor[3 * i + 2] *
      rtb_MatrixMultiply[i];
  }

  rtb_MatrixMultiply[2] = rtb_Product14_d;
  rtb_MatrixMultiply[1] = rtb_Product16;
  rtb_MatrixMultiply[0] = rtb_DotProduct;

  /* Sum: '<S5>/Add' incorporates:
   *  Constant: '<S12>/Constant5'
   *  Constant: '<S12>/Constant6'
   *  Product: '<S10>/Matrix Multiply'
   *  Product: '<S129>/Product3'
   */
  _mm_storeu_pd(&tmp_0[0], _mm_add_pd(_mm_add_pd(_mm_add_pd(_mm_set_pd
    (rtb_Product7, rtb_Multiply2), _mm_set_pd(SkySurfer_Core_P.Constant5_Value,
    rtb_VectorConcatenate_idx_1)), _mm_set_pd(rtb_Product_op, rtb_Product14)),
    _mm_loadu_pd(&rtb_MatrixMultiply[0])));
  rtb_Add_h_idx_2 = ((rtb_Product5 + SkySurfer_Core_P.Constant6_Value_o) +
                     rtb_Product16_j) + rtb_Product14_d;

  /* Product: '<S6>/Product' incorporates:
   *  Constant: '<S4>/const1'
   */
  rtb_q1dot = tmp_0[0] / SkySurfer_Core_P.Mass0;
  rtb_Product1_p4 = tmp_0[1] / SkySurfer_Core_P.Mass0;
  rtb_Product2_my = rtb_Add_h_idx_2 / SkySurfer_Core_P.Mass0;

  /* Sum: '<S6>/Sum' incorporates:
   *  Product: '<S88>/i x j'
   *  Product: '<S88>/j x k'
   *  Product: '<S88>/k x i'
   *  Product: '<S89>/i x k'
   *  Product: '<S89>/j x i'
   *  Product: '<S89>/k x j'
   *  Sum: '<S17>/Sum'
   */
  _mm_storeu_pd(&SkySurfer_Core_DW->Sum[0], _mm_add_pd(_mm_sub_pd(_mm_mul_pd
    (_mm_set_pd(rtb_u[0], rtb_Sum_mi_idx_1), _mm_set_pd(rtb_Sum_mi_idx_2, rtb_u
    [2])), _mm_mul_pd(_mm_set_pd(rtb_Sum_mi_idx_0, rtb_u[1]), _mm_set_pd(rtb_u[2],
    rtb_Sum_mi_idx_2))), _mm_set_pd(rtb_Product1_p4, rtb_q1dot)));
  SkySurfer_Core_DW->Sum[2] = (rtb_Sum_mi_idx_0 * rtb_u[1] - rtb_u[0] *
    rtb_Sum_mi_idx_1) + rtb_Product2_my;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   *  Constant: '<S12>/Constant5'
   *  Constant: '<S12>/Constant6'
   */
  CoreSnapshot_Concat[34] = rtb_VectorConcatenate_idx_1;
  CoreSnapshot_Concat[35] = SkySurfer_Core_P.Constant5_Value;
  CoreSnapshot_Concat[36] = SkySurfer_Core_P.Constant6_Value_o;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   *  Constant: '<S12>/Constant'
   *  Constant: '<S12>/Constant4'
   */
  CoreSnapshot_Concat[37] = SkySurfer_Core_P.Constant4_Value;
  CoreSnapshot_Concat[38] = rtb_Gain_az;
  CoreSnapshot_Concat[39] = SkySurfer_Core_P.Constant_Value_k5;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[52] = rtb_Airspeed;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[53] = rtb_Gain;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[54] = rtb_Gain_h;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[55] = rtb_Product1_ow;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[22] = SkySurfer_Core_DW->Sum[0];

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[25] = rtb_q1dot;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[28] = rtb_Multiply2;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[31] = rtb_Merge_idx_0;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   *  Product: '<S10>/Matrix Multiply'
   */
  CoreSnapshot_Concat[40] = rtb_DotProduct;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   *  Product: '<S129>/Product3'
   */
  CoreSnapshot_Concat[43] = rtb_Product14;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[46] = tmp_0[0];

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[49] = rtb_Add1_m[0];

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[56] = rtb_VectorConcatenate_idx_6;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[23] = SkySurfer_Core_DW->Sum[1];

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[26] = rtb_Product1_p4;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[29] = rtb_Product7;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[32] = rtb_Merge_idx_1;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   *  Product: '<S10>/Matrix Multiply'
   */
  CoreSnapshot_Concat[41] = rtb_Product16;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   *  Product: '<S129>/Product3'
   */
  CoreSnapshot_Concat[44] = rtb_Product_op;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[47] = tmp_0[1];

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[50] = rtb_Add1_m[1];

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[57] = rtb_sincos_o1_idx_1;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   *  Sum: '<S11>/Add4'
   */
  CoreSnapshot_Concat[60] = rtb_Add4_idx_1;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[24] = SkySurfer_Core_DW->Sum[2];

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[27] = rtb_Product2_my;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[30] = rtb_Product5;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[33] = rtb_Merge_idx_2;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   *  Product: '<S10>/Matrix Multiply'
   */
  CoreSnapshot_Concat[42] = rtb_Product14_d;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   *  Product: '<S129>/Product3'
   */
  CoreSnapshot_Concat[45] = rtb_Product16_j;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   *  Sum: '<S5>/Add'
   */
  CoreSnapshot_Concat[48] = rtb_Add_h_idx_2;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[51] = rtb_Add1_m[2];

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[58] = rtb_sincos_o1_idx_2;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   *  Sum: '<S11>/Add4'
   */
  CoreSnapshot_Concat[61] = rtb_Add4_idx_2;

  /* UnitConversion: '<S139>/Temperature Conversion' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  /* Unit Conversion - from: K to: K
     Expression: output = (1*input) + (0) */
  CoreSnapshot_Concat[62] = rtb_q2dot;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[63] = rtb_q0dot;

  /* UnitConversion: '<S137>/Pressure Conversion' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   *  Gain: '<S136>/P0'
   *  Product: '<S136>/Product2'
   */
  /* Unit Conversion - from: Pa to: Pa
     Expression: output = (1*input) + (0) */
  CoreSnapshot_Concat[64] = SkySurfer_Core_P.P0_Gain * rtb_TT0gLR * rtb_q3dot;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[65] = rtb_rho0;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[66] = rtb_Gain3;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[67] = rtb_Gain5;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[68] = rtb_Gain4;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[69] = rtb_Gain8;

  /* SignalConversion generated from: '<S5>/CoreSnapshot_Concat' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[70] = rtb_Thr;

  /* DataTypeConversion: '<S5>/Core_33_aero_active' incorporates:
   *  Concatenate: '<S5>/CoreSnapshot_Concat'
   */
  CoreSnapshot_Concat[71] = Compare;
  if (tmp) {
    /* Outport: '<Root>/CoreSnapshot' incorporates:
     *  Concatenate: '<S5>/CoreSnapshot_Concat'
     *  ZeroOrderHold: '<Root>/SampleCoreSnapshot'
     */
    memcpy(&SkySurfer_Core_Y->CoreSnapshot[0], &CoreSnapshot_Concat[0], 72U *
           sizeof(double));

    /* If: '<S41>/If1' incorporates:
     *  Constant: '<S41>/Constant'
     */
    rtAction = -1;
    if (rtsiIsModeUpdateTimeStep(&SkySurfer_Core_M->solverInfo)) {
      if (SkySurfer_Core_P.DCM2Ang_action > 1) {
        rtAction = 0;
      }

      SkySurfer_Core_DW->If1_ActiveSubsystem = rtAction;
    } else {
      rtAction = SkySurfer_Core_DW->If1_ActiveSubsystem;
    }

    if (rtAction == 0) {
      /* Outputs for IfAction SubSystem: '<S41>/If Warning//Error' incorporates:
       *  ActionPort: '<S50>/if'
       */
      /* Bias: '<S54>/Bias1' incorporates:
       *  Math: '<S54>/Math Function'
       *  Product: '<S54>/Product'
       *  Reshape: '<S74>/Reshape (9) to [3x3] column-major'
       */
      for (i = 0; i < 3; i++) {
        for (rtb_MatrixConcatenation_tmp = 0; rtb_MatrixConcatenation_tmp < 3;
             rtb_MatrixConcatenation_tmp++) {
          rtb_VectorConcatenate_j_tmp = 3 * rtb_MatrixConcatenation_tmp + i;
          rtb_Reshape9to3x3columnmajor[rtb_VectorConcatenate_j_tmp] =
            ((rtb_VectorConcatenate_k[3 * i + 1] * rtb_VectorConcatenate_k[3 *
              rtb_MatrixConcatenation_tmp + 1] + rtb_VectorConcatenate_k[3 * i] *
              rtb_VectorConcatenate_k[3 * rtb_MatrixConcatenation_tmp]) +
             rtb_VectorConcatenate_k[3 * i + 2] * rtb_VectorConcatenate_k[3 *
             rtb_MatrixConcatenation_tmp + 2]) +
            SkySurfer_Core_P.Bias1_Bias[rtb_VectorConcatenate_j_tmp];
        }
      }

      /* End of Bias: '<S54>/Bias1' */

      /* RelationalOperator: '<S62>/Compare' incorporates:
       *  Abs: '<S54>/Abs2'
       *  Constant: '<S62>/Constant'
       *  Reshape: '<S54>/Reshape'
       */
      for (i = 0; i < 9; i++) {
        rtb_Reshape_b[i] = (fabs(rtb_Reshape9to3x3columnmajor[i]) >
                            SkySurfer_Core_P.DCM2Ang_tolerance);
      }

      /* End of RelationalOperator: '<S62>/Compare' */

      /* Logic: '<S54>/Logical Operator1' incorporates:
       *  Reshape: '<S54>/Reshape'
       */
      Compare = rtb_Reshape_b[0];
      for (i = 0; i < 8; i++) {
        Compare = (Compare || rtb_Reshape_b[i + 1]);
      }

      /* If: '<S50>/If' incorporates:
       *  Abs: '<S55>/Abs1'
       *  Bias: '<S55>/Bias'
       *  Constant: '<S64>/Constant'
       *  Logic: '<S54>/Logical Operator1'
       *  Product: '<S63>/Product'
       *  Product: '<S63>/Product1'
       *  Product: '<S63>/Product2'
       *  Product: '<S63>/Product3'
       *  Product: '<S63>/Product4'
       *  Product: '<S63>/Product5'
       *  RelationalOperator: '<S64>/Compare'
       *  Reshape: '<S74>/Reshape (9) to [3x3] column-major'
       *  Sum: '<S63>/Sum'
       */
      if (fabs((((((rtb_VectorConcatenate_k[0] * rtb_VectorConcatenate_k[4] *
                    rtb_VectorConcatenate_k[8] - rtb_VectorConcatenate_k[0] *
                    rtb_VectorConcatenate_k[5] * rtb_VectorConcatenate_k[7]) -
                   rtb_VectorConcatenate_k[1] * rtb_VectorConcatenate_k[3] *
                   rtb_VectorConcatenate_k[8]) + rtb_VectorConcatenate_k[2] *
                  rtb_VectorConcatenate_k[3] * rtb_VectorConcatenate_k[7]) +
                 rtb_VectorConcatenate_k[1] * rtb_VectorConcatenate_k[5] *
                 rtb_VectorConcatenate_k[6]) - rtb_VectorConcatenate_k[2] *
                rtb_VectorConcatenate_k[4] * rtb_VectorConcatenate_k[6]) +
               SkySurfer_Core_P.Bias_Bias) > SkySurfer_Core_P.DCM2Ang_tolerance)
      {
        /* Outputs for IfAction SubSystem: '<S50>/If Not Proper' incorporates:
         *  ActionPort: '<S53>/Action Port'
         */
        /* If: '<S53>/If' incorporates:
         *  Constant: '<S53>/Constant'
         */
        if (SkySurfer_Core_P.DCM2Ang_action == 2) {
          /* Outputs for IfAction SubSystem: '<S53>/Warning' incorporates:
           *  ActionPort: '<S61>/Action Port'
           */
          /* Assertion: '<S61>/Assertion' incorporates:
           *  Constant: '<S53>/Constant1'
           */
          utAssert(SkySurfer_Core_P.Constant1_Value != 0.0);

          /* End of Outputs for SubSystem: '<S53>/Warning' */
        } else if (SkySurfer_Core_P.DCM2Ang_action == 3) {
          /* Outputs for IfAction SubSystem: '<S53>/Error' incorporates:
           *  ActionPort: '<S59>/Action Port'
           */
          /* Assertion: '<S59>/Assertion' incorporates:
           *  Constant: '<S53>/Constant1'
           */
          utAssert(SkySurfer_Core_P.Constant1_Value != 0.0);

          /* End of Outputs for SubSystem: '<S53>/Error' */
        }

        /* End of If: '<S53>/If' */
        /* End of Outputs for SubSystem: '<S50>/If Not Proper' */
      } else if (Compare) {
        /* Outputs for IfAction SubSystem: '<S50>/Else If Not Orthogonal' incorporates:
         *  ActionPort: '<S51>/Action Port'
         */
        /* If: '<S51>/If' incorporates:
         *  Constant: '<S51>/Constant'
         */
        if (SkySurfer_Core_P.DCM2Ang_action == 2) {
          /* Outputs for IfAction SubSystem: '<S51>/Warning' incorporates:
           *  ActionPort: '<S58>/Action Port'
           */
          /* Assertion: '<S58>/Assertion' incorporates:
           *  Constant: '<S51>/Constant1'
           */
          utAssert(SkySurfer_Core_P.Constant1_Value_a != 0.0);

          /* End of Outputs for SubSystem: '<S51>/Warning' */
        } else if (SkySurfer_Core_P.DCM2Ang_action == 3) {
          /* Outputs for IfAction SubSystem: '<S51>/Error' incorporates:
           *  ActionPort: '<S56>/Action Port'
           */
          /* Assertion: '<S56>/Assertion' incorporates:
           *  Constant: '<S51>/Constant1'
           */
          utAssert(SkySurfer_Core_P.Constant1_Value_a != 0.0);

          /* End of Outputs for SubSystem: '<S51>/Error' */
        }

        /* End of If: '<S51>/If' */
        /* End of Outputs for SubSystem: '<S50>/Else If Not Orthogonal' */
      }

      /* End of If: '<S50>/If' */
      /* End of Outputs for SubSystem: '<S41>/If Warning//Error' */
    }

    /* End of If: '<S41>/If1' */
  }

  /* Sqrt: '<S79>/sqrt' incorporates:
   *  Product: '<S80>/Product'
   *  Product: '<S80>/Product1'
   *  Product: '<S80>/Product2'
   *  Product: '<S80>/Product3'
   *  Sum: '<S80>/Sum'
   */
  rtb_DotProduct = sqrt(((rtb_Q0123_idx_0 * rtb_Q0123_idx_0 + rtb_Q0123_idx_1 *
    rtb_Q0123_idx_1) + rtb_Q0123_idx_2 * rtb_Q0123_idx_2) + rtb_Q0123_idx_3 *
                        rtb_Q0123_idx_3);

  /* Product: '<S78>/Product' */
  rtb_Product_op = rtb_Q0123_idx_0 / rtb_DotProduct;

  /* Product: '<S78>/Product1' */
  rtb_Product1_p4 = rtb_Q0123_idx_1 / rtb_DotProduct;

  /* Product: '<S78>/Product2' */
  rtb_Product2_my = rtb_Q0123_idx_2 / rtb_DotProduct;

  /* Product: '<S78>/Product3' */
  rtb_DotProduct = rtb_Q0123_idx_3 / rtb_DotProduct;

  /* SignalConversion generated from: '<S14>/Q0123' incorporates:
   *  Fcn: '<S22>/q0dot'
   *  Fcn: '<S22>/q1dot'
   *  Fcn: '<S22>/q2dot'
   *  Fcn: '<S22>/q3dot'
   */
  _mm_storeu_pd(&SkySurfer_Core_DW->TmpSignalConversionAtQ0123Inport1[0],
                _mm_mul_pd(_mm_add_pd(_mm_add_pd(_mm_mul_pd(_mm_set_pd
    (rtb_Product_op, rtb_Product1_p4), _mm_set1_pd(rtb_u[0])), _mm_mul_pd
    (_mm_set1_pd(rtb_Product2_my), _mm_loadu_pd(&rtb_u[1]))), _mm_mul_pd
    (_mm_mul_pd(_mm_set1_pd(rtb_DotProduct), _mm_set_pd(rtb_u[1], rtb_u[2])),
     _mm_set_pd(-1.0, 1.0))), _mm_set_pd(0.5, -0.5)));
  _mm_storeu_pd(&SkySurfer_Core_DW->TmpSignalConversionAtQ0123Inport1[2],
                _mm_mul_pd(_mm_sub_pd(_mm_add_pd(_mm_mul_pd(_mm_set1_pd
    (rtb_Product_op), _mm_loadu_pd(&rtb_u[1])), _mm_mul_pd(_mm_set_pd
    (rtb_Product1_p4, rtb_DotProduct), _mm_loadu_pd(&rtb_u[0]))), _mm_mul_pd
    (_mm_set_pd(rtb_Product2_my, rtb_Product1_p4), _mm_set_pd(rtb_u[0], rtb_u[2]))),
    _mm_set1_pd(0.5)));

  /* Sqrt: '<S11>/Sqrt' incorporates:
   *  DotProduct: '<S11>/Dot Product'
   */
  SkySurfer_Core_DW->Sqrt = sqrt((SkySurfer_Core_DW->Reshape2[0] *
    SkySurfer_Core_DW->Reshape2[0] + SkySurfer_Core_DW->Reshape2[1] *
    SkySurfer_Core_DW->Reshape2[1]) + SkySurfer_Core_DW->Reshape2[2] *
    SkySurfer_Core_DW->Reshape2[2]);
  if (tmp) {
    /* Saturate: '<S3>/Limit_ELE' incorporates:
     *  Inport: '<Root>/Controls'
     */
    if (SkySurfer_Core_U->Controls[2] > SkySurfer_Core_P.Limit_ELE_UpperSat) {
      rtb_Product16 = SkySurfer_Core_P.Limit_ELE_UpperSat;
    } else if (SkySurfer_Core_U->Controls[2] <
               SkySurfer_Core_P.Limit_ELE_LowerSat) {
      rtb_Product16 = SkySurfer_Core_P.Limit_ELE_LowerSat;
    } else {
      rtb_Product16 = SkySurfer_Core_U->Controls[2];
    }

    /* Gain: '<S3>/Gain' incorporates:
     *  Saturate: '<S3>/Limit_ELE'
     */
    SkySurfer_Core_DW->Gain_g = SkySurfer_Core_P.Gain_Gain_h * rtb_Product16;

    /* Saturate: '<S3>/Limit_RUD' incorporates:
     *  Inport: '<Root>/Controls'
     */
    if (SkySurfer_Core_U->Controls[3] > SkySurfer_Core_P.Limit_RUD_UpperSat) {
      rtb_Product16 = SkySurfer_Core_P.Limit_RUD_UpperSat;
    } else if (SkySurfer_Core_U->Controls[3] <
               SkySurfer_Core_P.Limit_RUD_LowerSat) {
      rtb_Product16 = SkySurfer_Core_P.Limit_RUD_LowerSat;
    } else {
      rtb_Product16 = SkySurfer_Core_U->Controls[3];
    }

    /* Gain: '<S3>/Gain1' incorporates:
     *  Saturate: '<S3>/Limit_RUD'
     */
    SkySurfer_Core_DW->Gain1 = SkySurfer_Core_P.Gain1_Gain_fv * rtb_Product16;

    /* Saturate: '<S3>/Limit_AIL_L' incorporates:
     *  Inport: '<Root>/Controls'
     */
    if (SkySurfer_Core_U->Controls[0] > SkySurfer_Core_P.Limit_AIL_L_UpperSat) {
      rtb_Product16 = SkySurfer_Core_P.Limit_AIL_L_UpperSat;
    } else if (SkySurfer_Core_U->Controls[0] <
               SkySurfer_Core_P.Limit_AIL_L_LowerSat) {
      rtb_Product16 = SkySurfer_Core_P.Limit_AIL_L_LowerSat;
    } else {
      rtb_Product16 = SkySurfer_Core_U->Controls[0];
    }

    /* Gain: '<S3>/Gain2' incorporates:
     *  Saturate: '<S3>/Limit_AIL_L'
     */
    SkySurfer_Core_DW->Gain2 = SkySurfer_Core_P.Gain2_Gain_f * rtb_Product16;

    /* Saturate: '<S3>/Limit_AIL_R' incorporates:
     *  Inport: '<Root>/Controls'
     */
    if (SkySurfer_Core_U->Controls[1] > SkySurfer_Core_P.Limit_AIL_R_UpperSat) {
      rtb_Product16 = SkySurfer_Core_P.Limit_AIL_R_UpperSat;
    } else if (SkySurfer_Core_U->Controls[1] <
               SkySurfer_Core_P.Limit_AIL_R_LowerSat) {
      rtb_Product16 = SkySurfer_Core_P.Limit_AIL_R_LowerSat;
    } else {
      rtb_Product16 = SkySurfer_Core_U->Controls[1];
    }

    /* Gain: '<S3>/Gain6' incorporates:
     *  Saturate: '<S3>/Limit_AIL_R'
     */
    SkySurfer_Core_DW->Gain6 = SkySurfer_Core_P.Gain6_Gain * rtb_Product16;

    /* Saturate: '<S3>/Limit_THR' incorporates:
     *  Inport: '<Root>/Controls'
     */
    if (SkySurfer_Core_U->Controls[4] > SkySurfer_Core_P.Limit_THR_UpperSat) {
      /* Saturate: '<S3>/Limit_THR' */
      SkySurfer_Core_DW->Limit_THR = SkySurfer_Core_P.Limit_THR_UpperSat;
    } else if (SkySurfer_Core_U->Controls[4] <
               SkySurfer_Core_P.Limit_THR_LowerSat) {
      /* Saturate: '<S3>/Limit_THR' */
      SkySurfer_Core_DW->Limit_THR = SkySurfer_Core_P.Limit_THR_LowerSat;
    } else {
      /* Saturate: '<S3>/Limit_THR' */
      SkySurfer_Core_DW->Limit_THR = SkySurfer_Core_U->Controls[4];
    }

    /* End of Saturate: '<S3>/Limit_THR' */
  }

  if (rtmIsMajorTimeStep(SkySurfer_Core_M)) {
    /* Update for Integrator: '<S6>/XYZe' */
    SkySurfer_Core_DW->XYZe_DWORK1 = false;

    /* Update for Integrator: '<S6>/UVWb' */
    SkySurfer_Core_DW->UVWb_DWORK1 = false;

    /* Update for Integrator: '<S14>/Q0123' */
    SkySurfer_Core_DW->Q0123_DWORK1 = false;

    /* Update for RateLimiter: '<S3>/Rate Limiter' incorporates:
     *  RateLimiter: '<S3>/Rate Limiter1'
     *  RateLimiter: '<S3>/Rate Limiter2'
     *  RateLimiter: '<S3>/Rate Limiter3'
     */
    SkySurfer_Core_DW->PrevY = SkySurfer_Core_DW->RateLimiter;
    SkySurfer_Core_DW->LastMajorTime = SkySurfer_Core_M->Timing.t[0];

    /* Update for RateLimiter: '<S3>/Rate Limiter3' */
    SkySurfer_Core_DW->PrevY_p = SkySurfer_Core_DW->RateLimiter3;
    SkySurfer_Core_DW->LastMajorTime_e = SkySurfer_Core_DW->LastMajorTime;

    /* Update for RateLimiter: '<S3>/Rate Limiter1' */
    SkySurfer_Core_DW->PrevY_d = SkySurfer_Core_DW->RateLimiter1;
    SkySurfer_Core_DW->LastMajorTime_p = SkySurfer_Core_DW->LastMajorTime;

    /* Update for RateLimiter: '<S3>/Rate Limiter2' */
    SkySurfer_Core_DW->PrevY_m = SkySurfer_Core_DW->RateLimiter2;
    SkySurfer_Core_DW->LastMajorTime_d = SkySurfer_Core_DW->LastMajorTime;
  }                                    /* end MajorTimeStep */

  if (rtmIsMajorTimeStep(SkySurfer_Core_M)) {
    rt_ertODEUpdateContinuousStates(&SkySurfer_Core_M->solverInfo,
      SkySurfer_Core_M, SkySurfer_Core_U, SkySurfer_Core_Y);

    /* Update absolute time for base rate */
    /* The "clockTick0" counts the number of times the code of this task has
     * been executed. The absolute time is the multiplication of "clockTick0"
     * and "Timing.stepSize0". Size of "clockTick0" ensures timer will not
     * overflow during the application lifespan selected.
     */
    ++SkySurfer_Core_M->Timing.clockTick0;
    SkySurfer_Core_M->Timing.t[0] = rtsiGetSolverStopTime
      (&SkySurfer_Core_M->solverInfo);

    {
      /* Update absolute timer for sample time: [0.004s, 0.0s] */
      /* The "clockTick1" counts the number of times the code of this task has
       * been executed. The resolution of this integer timer is 0.004, which is the step size
       * of the task. Size of "clockTick1" ensures timer will not overflow during the
       * application lifespan selected.
       */
      SkySurfer_Core_M->Timing.clockTick1++;
    }
  }                                    /* end MajorTimeStep */
}

/* Derivatives for root system: '<Root>' */
void SkySurfer_Core_derivatives(RT_MODEL_SkySurfer_Core_T *const
  SkySurfer_Core_M)
{
  DW_SkySurfer_Core_T *SkySurfer_Core_DW = SkySurfer_Core_M->dwork;
  X_SkySurfer_Core_T *SkySurfer_Core_X = SkySurfer_Core_M->contStates;
  XDot_SkySurfer_Core_T *_rtXdot;
  bool lsat;
  bool usat;
  _rtXdot = ((XDot_SkySurfer_Core_T *) SkySurfer_Core_M->derivs);

  /* Derivatives for Integrator: '<S6>/XYZe' */
  _rtXdot->XYZe_CSTATE[0] = SkySurfer_Core_DW->Reshape2[0];

  /* Derivatives for Integrator: '<S6>/UVWb' */
  _rtXdot->UVWb_CSTATE[0] = SkySurfer_Core_DW->Sum[0];

  /* Derivatives for Integrator: '<S6>/XYZe' */
  _rtXdot->XYZe_CSTATE[1] = SkySurfer_Core_DW->Reshape2[1];

  /* Derivatives for Integrator: '<S6>/UVWb' */
  _rtXdot->UVWb_CSTATE[1] = SkySurfer_Core_DW->Sum[1];

  /* Derivatives for Integrator: '<S6>/XYZe' */
  _rtXdot->XYZe_CSTATE[2] = SkySurfer_Core_DW->Reshape2[2];

  /* Derivatives for Integrator: '<S6>/UVWb' */
  _rtXdot->UVWb_CSTATE[2] = SkySurfer_Core_DW->Sum[2];

  /* Derivatives for Integrator: '<S14>/Q0123' */
  _rtXdot->Q0123_CSTATE[0] =
    SkySurfer_Core_DW->TmpSignalConversionAtQ0123Inport1[0];
  _rtXdot->Q0123_CSTATE[1] =
    SkySurfer_Core_DW->TmpSignalConversionAtQ0123Inport1[1];
  _rtXdot->Q0123_CSTATE[2] =
    SkySurfer_Core_DW->TmpSignalConversionAtQ0123Inport1[2];
  _rtXdot->Q0123_CSTATE[3] =
    SkySurfer_Core_DW->TmpSignalConversionAtQ0123Inport1[3];

  /* Derivatives for Integrator: '<S6>/PQR' */
  _rtXdot->PQR_CSTATE[0] = SkySurfer_Core_DW->Reshape[0];
  _rtXdot->PQR_CSTATE[1] = SkySurfer_Core_DW->Reshape[1];
  _rtXdot->PQR_CSTATE[2] = SkySurfer_Core_DW->Reshape[2];

  /* Derivatives for TransferFcn: '<S3>/Transfer Fcn3' */
  _rtXdot->TransferFcn3_CSTATE = 0.0;
  _rtXdot->TransferFcn3_CSTATE += SkySurfer_Core_P.TransferFcn3_A *
    SkySurfer_Core_X->TransferFcn3_CSTATE;
  _rtXdot->TransferFcn3_CSTATE += SkySurfer_Core_DW->Limit_THR;

  /* Derivatives for Enabled SubSystem: '<S140>/Distance into gust (x)' */
  if (SkySurfer_Core_DW->Distanceintogustx_MODE) {
    /* Derivatives for Integrator: '<S144>/Distance into Gust (x) (Limited to gust length d)' */
    lsat = (SkySurfer_Core_X->DistanceintoGustxLimitedtogustlengthd_CSTATE_p <=
            SkySurfer_Core_P.DistanceintoGustxLimitedtogustlengthd_LowerSat);

    /* Derivatives for Enabled SubSystem: '<S140>/Distance into gust (x)' */
    usat = (SkySurfer_Core_X->DistanceintoGustxLimitedtogustlengthd_CSTATE_p >=
            SkySurfer_Core_P.Distanceintogustx_d_m);

    /* End of Derivatives for SubSystem: '<S140>/Distance into gust (x)' */
    if ((!lsat && !usat) || (lsat && (SkySurfer_Core_DW->Sqrt > 0.0)) || (usat &&
         (SkySurfer_Core_DW->Sqrt < 0.0))) {
      _rtXdot->DistanceintoGustxLimitedtogustlengthd_CSTATE_p =
        SkySurfer_Core_DW->Sqrt;
    } else {
      /* in saturation */
      _rtXdot->DistanceintoGustxLimitedtogustlengthd_CSTATE_p = 0.0;
    }

    /* End of Derivatives for Integrator: '<S144>/Distance into Gust (x) (Limited to gust length d)' */
  } else {
    ((XDot_SkySurfer_Core_T *) SkySurfer_Core_M->derivs)
      ->DistanceintoGustxLimitedtogustlengthd_CSTATE_p = 0.0;
  }

  /* End of Derivatives for SubSystem: '<S140>/Distance into gust (x)' */

  /* Derivatives for Enabled SubSystem: '<S140>/Distance into gust (y)' */
  /* Derivatives for Enabled SubSystem: '<S140>/Distance into gust (y)' */
  SkySurfer_Core_Distanceintogusty_Deriv(SkySurfer_Core_DW->Sqrt,
    SkySurfer_Core_P.Distanceintogusty_d_m,
    &SkySurfer_Core_DW->Distanceintogusty, &SkySurfer_Core_P.Distanceintogusty,
    &SkySurfer_Core_X->Distanceintogusty, &_rtXdot->Distanceintogusty);

  /* End of Derivatives for SubSystem: '<S140>/Distance into gust (y)' */
  /* End of Derivatives for SubSystem: '<S140>/Distance into gust (y)' */

  /* Derivatives for Enabled SubSystem: '<S140>/Distance into gust (z)' */
  /* Derivatives for Enabled SubSystem: '<S140>/Distance into gust (z)' */
  SkySurfer_Core_Distanceintogusty_Deriv(SkySurfer_Core_DW->Sqrt,
    SkySurfer_Core_P.Distanceintogustz_d_m,
    &SkySurfer_Core_DW->Distanceintogustz, &SkySurfer_Core_P.Distanceintogustz,
    &SkySurfer_Core_X->Distanceintogustz, &_rtXdot->Distanceintogustz);

  /* End of Derivatives for SubSystem: '<S140>/Distance into gust (z)' */
  /* End of Derivatives for SubSystem: '<S140>/Distance into gust (z)' */

  /* Derivatives for TransferFcn: '<S3>/Transfer Fcn' */
  _rtXdot->TransferFcn_CSTATE = 0.0;
  _rtXdot->TransferFcn_CSTATE += SkySurfer_Core_P.TransferFcn_A *
    SkySurfer_Core_X->TransferFcn_CSTATE;
  _rtXdot->TransferFcn_CSTATE += SkySurfer_Core_DW->Gain6;

  /* Derivatives for TransferFcn: '<S3>/Transfer Fcn4' */
  _rtXdot->TransferFcn4_CSTATE = 0.0;
  _rtXdot->TransferFcn4_CSTATE += SkySurfer_Core_P.TransferFcn4_A *
    SkySurfer_Core_X->TransferFcn4_CSTATE;
  _rtXdot->TransferFcn4_CSTATE += SkySurfer_Core_DW->Gain2;

  /* Derivatives for TransferFcn: '<S3>/Transfer Fcn1' */
  _rtXdot->TransferFcn1_CSTATE = 0.0;
  _rtXdot->TransferFcn1_CSTATE += SkySurfer_Core_P.TransferFcn1_A *
    SkySurfer_Core_X->TransferFcn1_CSTATE;
  _rtXdot->TransferFcn1_CSTATE += SkySurfer_Core_DW->Gain_g;

  /* Derivatives for TransferFcn: '<S3>/Transfer Fcn2' */
  _rtXdot->TransferFcn2_CSTATE = 0.0;
  _rtXdot->TransferFcn2_CSTATE += SkySurfer_Core_P.TransferFcn2_A *
    SkySurfer_Core_X->TransferFcn2_CSTATE;
  _rtXdot->TransferFcn2_CSTATE += SkySurfer_Core_DW->Gain1;
}

/* Model initialize function */
void SkySurfer_Core_initialize(RT_MODEL_SkySurfer_Core_T *const SkySurfer_Core_M,
  ExtU_SkySurfer_Core_T *SkySurfer_Core_U, ExtY_SkySurfer_Core_T
  *SkySurfer_Core_Y)
{
  DW_SkySurfer_Core_T *SkySurfer_Core_DW = SkySurfer_Core_M->dwork;
  X_SkySurfer_Core_T *SkySurfer_Core_X = SkySurfer_Core_M->contStates;
  XDis_SkySurfer_Core_T *SkySurfer_Core_XDis = ((XDis_SkySurfer_Core_T *)
    SkySurfer_Core_M->contStateDisabled);

  /* Registration code */

  /* initialize non-finites */
  rt_InitInfAndNaN(sizeof(double));

  /* non-finite (run-time) assignments */
  SkySurfer_Core_P.uftinf_UpperSat = rtInf;
  SkySurfer_Core_P.Saturation_UpperSat = rtInf;

  {
    /* Setup solver object */
    rtsiSetSimTimeStepPtr(&SkySurfer_Core_M->solverInfo,
                          &SkySurfer_Core_M->Timing.simTimeStep);
    rtsiSetTPtr(&SkySurfer_Core_M->solverInfo, &rtmGetTPtr(SkySurfer_Core_M));
    rtsiSetStepSizePtr(&SkySurfer_Core_M->solverInfo,
                       &SkySurfer_Core_M->Timing.stepSize0);
    rtsiSetdXPtr(&SkySurfer_Core_M->solverInfo, &SkySurfer_Core_M->derivs);
    rtsiSetContStatesPtr(&SkySurfer_Core_M->solverInfo, (double **)
                         &SkySurfer_Core_M->contStates);
    rtsiSetNumContStatesPtr(&SkySurfer_Core_M->solverInfo,
      &SkySurfer_Core_M->Sizes.numContStates);
    rtsiSetNumPeriodicContStatesPtr(&SkySurfer_Core_M->solverInfo,
      &SkySurfer_Core_M->Sizes.numPeriodicContStates);
    rtsiSetPeriodicContStateIndicesPtr(&SkySurfer_Core_M->solverInfo,
      &SkySurfer_Core_M->periodicContStateIndices);
    rtsiSetPeriodicContStateRangesPtr(&SkySurfer_Core_M->solverInfo,
      &SkySurfer_Core_M->periodicContStateRanges);
    rtsiSetContStateDisabledPtr(&SkySurfer_Core_M->solverInfo, (bool**)
      &SkySurfer_Core_M->contStateDisabled);
    rtsiSetErrorStatusPtr(&SkySurfer_Core_M->solverInfo, (&rtmGetErrorStatus
      (SkySurfer_Core_M)));
    rtsiSetRTModelPtr(&SkySurfer_Core_M->solverInfo, SkySurfer_Core_M);
  }

  rtsiSetSimTimeStep(&SkySurfer_Core_M->solverInfo, MAJOR_TIME_STEP);
  rtsiSetIsMinorTimeStepWithModeChange(&SkySurfer_Core_M->solverInfo, false);
  rtsiSetIsContModeFrozen(&SkySurfer_Core_M->solverInfo, false);
  SkySurfer_Core_M->intgData.y = SkySurfer_Core_M->odeY;
  SkySurfer_Core_M->intgData.f[0] = SkySurfer_Core_M->odeF[0];
  SkySurfer_Core_M->intgData.f[1] = SkySurfer_Core_M->odeF[1];
  SkySurfer_Core_M->intgData.f[2] = SkySurfer_Core_M->odeF[2];
  SkySurfer_Core_M->intgData.f[3] = SkySurfer_Core_M->odeF[3];
  SkySurfer_Core_M->contStates = ((X_SkySurfer_Core_T *) SkySurfer_Core_X);
  SkySurfer_Core_M->contStateDisabled = ((XDis_SkySurfer_Core_T *)
    SkySurfer_Core_XDis);
  SkySurfer_Core_M->Timing.tStart = (0.0);
  rtsiSetSolverData(&SkySurfer_Core_M->solverInfo, (void *)
                    &SkySurfer_Core_M->intgData);
  rtsiSetSolverName(&SkySurfer_Core_M->solverInfo,"ode4");
  rtmSetTPtr(SkySurfer_Core_M, &SkySurfer_Core_M->Timing.tArray[0]);
  SkySurfer_Core_M->Timing.stepSize0 = 0.004;
  rtmSetFirstInitCond(SkySurfer_Core_M, 1);

  /* states (continuous) */
  {
    (void) memset((void *)SkySurfer_Core_X, 0,
                  sizeof(X_SkySurfer_Core_T));
  }

  /* disabled states */
  {
    (void) memset((void *)SkySurfer_Core_XDis, 0,
                  sizeof(XDis_SkySurfer_Core_T));
  }

  /* states (dwork) */
  (void) memset((void *)SkySurfer_Core_DW, 0,
                sizeof(DW_SkySurfer_Core_T));

  /* external inputs */
  (void)memset(SkySurfer_Core_U, 0, sizeof(ExtU_SkySurfer_Core_T));

  /* external outputs */
  {
    int32_t i;
    for (i = 0; i < 72; i++) {
      SkySurfer_Core_Y->CoreSnapshot[i] = 0.0;
    }
  }

  /* Start for If: '<S36>/If' */
  SkySurfer_Core_DW->If_ActiveSubsystem = -1;

  /* Start for If: '<S41>/If1' */
  SkySurfer_Core_DW->If1_ActiveSubsystem = -1;

  /* InitializeConditions for Integrator: '<S6>/XYZe' incorporates:
   *  Integrator: '<S14>/Q0123'
   *  Integrator: '<S6>/UVWb'
   */
  if (rtmIsFirstInitCond(SkySurfer_Core_M)) {
    SkySurfer_Core_X->XYZe_CSTATE[0] = 0.0;
    SkySurfer_Core_X->XYZe_CSTATE[1] = 0.0;
    SkySurfer_Core_X->XYZe_CSTATE[2] = 0.0;
    SkySurfer_Core_X->UVWb_CSTATE[0] = 0.0;
    SkySurfer_Core_X->UVWb_CSTATE[1] = 0.0;
    SkySurfer_Core_X->UVWb_CSTATE[2] = 0.0;
    SkySurfer_Core_X->Q0123_CSTATE[0] = 0.0;
    SkySurfer_Core_X->Q0123_CSTATE[1] = 0.0;
    SkySurfer_Core_X->Q0123_CSTATE[2] = 0.0;
    SkySurfer_Core_X->Q0123_CSTATE[3] = 0.0;
  }

  SkySurfer_Core_DW->XYZe_DWORK1 = true;

  /* End of InitializeConditions for Integrator: '<S6>/XYZe' */

  /* InitializeConditions for Integrator: '<S6>/UVWb' */
  SkySurfer_Core_DW->UVWb_DWORK1 = true;

  /* InitializeConditions for Integrator: '<S14>/Q0123' */
  SkySurfer_Core_DW->Q0123_DWORK1 = true;

  /* InitializeConditions for Integrator: '<S6>/PQR' */
  SkySurfer_Core_X->PQR_CSTATE[0] = SkySurfer_Core_P.PQR_IC;
  SkySurfer_Core_X->PQR_CSTATE[1] = SkySurfer_Core_P.PQR_IC;
  SkySurfer_Core_X->PQR_CSTATE[2] = SkySurfer_Core_P.PQR_IC;

  /* InitializeConditions for TransferFcn: '<S3>/Transfer Fcn3' */
  SkySurfer_Core_X->TransferFcn3_CSTATE = 0.0;

  /* InitializeConditions for TransferFcn: '<S3>/Transfer Fcn' */
  SkySurfer_Core_X->TransferFcn_CSTATE = 0.0;

  /* InitializeConditions for RateLimiter: '<S3>/Rate Limiter' */
  SkySurfer_Core_DW->LastMajorTime = (rtMinusInf);

  /* InitializeConditions for TransferFcn: '<S3>/Transfer Fcn4' */
  SkySurfer_Core_X->TransferFcn4_CSTATE = 0.0;

  /* InitializeConditions for RateLimiter: '<S3>/Rate Limiter3' */
  SkySurfer_Core_DW->LastMajorTime_e = (rtMinusInf);

  /* InitializeConditions for TransferFcn: '<S3>/Transfer Fcn1' */
  SkySurfer_Core_X->TransferFcn1_CSTATE = 0.0;

  /* InitializeConditions for RateLimiter: '<S3>/Rate Limiter1' */
  SkySurfer_Core_DW->LastMajorTime_p = (rtMinusInf);

  /* InitializeConditions for TransferFcn: '<S3>/Transfer Fcn2' */
  SkySurfer_Core_X->TransferFcn2_CSTATE = 0.0;

  /* InitializeConditions for RateLimiter: '<S3>/Rate Limiter2' */
  SkySurfer_Core_DW->LastMajorTime_d = (rtMinusInf);

  /* SystemInitialize for IfAction SubSystem: '<S36>/AxisRotZeroR3' */
  /* Start for If: '<S46>/If' */
  SkySurfer_Core_DW->If_ActiveSubsystem_a = -1;

  /* End of SystemInitialize for SubSystem: '<S36>/AxisRotZeroR3' */

  /* SystemInitialize for IfAction SubSystem: '<S36>/AxisRotDefault' */
  /* Start for If: '<S42>/If' */
  SkySurfer_Core_DW->If_ActiveSubsystem_i = -1;

  /* End of SystemInitialize for SubSystem: '<S36>/AxisRotDefault' */

  /* SystemInitialize for Enabled SubSystem: '<S140>/Distance into gust (x)' */
  /* InitializeConditions for Integrator: '<S144>/Distance into Gust (x) (Limited to gust length d)' */
  SkySurfer_Core_X->DistanceintoGustxLimitedtogustlengthd_CSTATE_p =
    SkySurfer_Core_P.DistanceintoGustxLimitedtogustlengthd_IC;

  /* SystemInitialize for Integrator: '<S144>/Distance into Gust (x) (Limited to gust length d)' incorporates:
   *  Outport: '<S144>/x'
   */
  SkySurfer_Core_DW->DistanceintoGustxLimitedtogustlengthd_l =
    SkySurfer_Core_P.x_Y0;

  /* End of SystemInitialize for SubSystem: '<S140>/Distance into gust (x)' */

  /* SystemInitialize for Enabled SubSystem: '<S140>/Distance into gust (y)' */
  SkySurfer_Core_Distanceintogusty_Init
    (&SkySurfer_Core_DW->DistanceintoGustxLimitedtogustlengthd_k,
     &SkySurfer_Core_P.Distanceintogusty, &SkySurfer_Core_X->Distanceintogusty);

  /* End of SystemInitialize for SubSystem: '<S140>/Distance into gust (y)' */

  /* SystemInitialize for Enabled SubSystem: '<S140>/Distance into gust (z)' */
  SkySurfer_Core_Distanceintogusty_Init
    (&SkySurfer_Core_DW->DistanceintoGustxLimitedtogustlengthd,
     &SkySurfer_Core_P.Distanceintogustz, &SkySurfer_Core_X->Distanceintogustz);

  /* End of SystemInitialize for SubSystem: '<S140>/Distance into gust (z)' */

  /* SystemInitialize for Enabled SubSystem: '<S5>/Aerodynamic' */
  /* SystemInitialize for Switch: '<S7>/Switch' incorporates:
   *  Outport: '<S7>/F_aero'
   */
  SkySurfer_Core_DW->Switch[0] = SkySurfer_Core_P.F_aero_Y0;

  /* SystemInitialize for Switch: '<S7>/Switch1' incorporates:
   *  Outport: '<S7>/M_aero'
   */
  SkySurfer_Core_DW->Switch1[0] = SkySurfer_Core_P.M_aero_Y0;

  /* SystemInitialize for Switch: '<S7>/Switch' incorporates:
   *  Outport: '<S7>/F_aero'
   */
  SkySurfer_Core_DW->Switch[1] = SkySurfer_Core_P.F_aero_Y0;

  /* SystemInitialize for Switch: '<S7>/Switch1' incorporates:
   *  Outport: '<S7>/M_aero'
   */
  SkySurfer_Core_DW->Switch1[1] = SkySurfer_Core_P.M_aero_Y0;

  /* SystemInitialize for Switch: '<S7>/Switch' incorporates:
   *  Outport: '<S7>/F_aero'
   */
  SkySurfer_Core_DW->Switch[2] = SkySurfer_Core_P.F_aero_Y0;

  /* SystemInitialize for Switch: '<S7>/Switch1' incorporates:
   *  Outport: '<S7>/M_aero'
   */
  SkySurfer_Core_DW->Switch1[2] = SkySurfer_Core_P.M_aero_Y0;

  /* End of SystemInitialize for SubSystem: '<S5>/Aerodynamic' */

  /* set "at time zero" to false */
  if (rtmIsFirstInitCond(SkySurfer_Core_M)) {
    rtmSetFirstInitCond(SkySurfer_Core_M, 0);
  }
}

/* Model terminate function */
void SkySurfer_Core_terminate(RT_MODEL_SkySurfer_Core_T *const SkySurfer_Core_M)
{
  /* (no terminate code required) */
  UNUSED_PARAMETER(SkySurfer_Core_M);
}

/*
 * File trailer for generated code.
 *
 * [EOF]
 */
