%% FW_SkySurfer_InitialFunction
% Source parameters for FW_SkySurfer_HIL.slx: initial conditions, mass properties, geometry,
% aerodynamic tables, actuator effectiveness, ground contact and sample time.
% Runs from the model InitFcn and from plant/core/build_core.m.

%% Caller check
if evalin('base', 'exist(''lastRunModel'', ''var'')')
    modelName = evalin('base', 'lastRunModel');
    if ~strcmp(modelName, 'FW_SkySurfer_HIL')
        error('Unrecognized model name: %s', modelName);
    end
elseif exist('ByPass_lastRunModel', 'var') && ByPass_lastRunModel == 1
    modelName = 'ByPass';
    ByPass_lastRunModel = 0;
else
    error('Variable lastRunModel does not exist in the base workspace. Please ensure the model InitFcn is set.');
end

%% Initial Condition

if strcmp(modelName, 'FW_SkySurfer_HIL')
    U0                  =  0 * convvel(1, 'kts', 'm/s');        % ini. velocity, kts
    W0                  =  0 * convvel(1, 'kts', 'm/s');        % ini. velocity, kts
    H0                  =  0 * convlength(1, 'ft', 'm');        % ini. altitude, ft
else
    U0                  =  40.0309 * convvel(1, 'kts', 'm/s');  % ini. velocity, kts
    W0                  =  0.6032 * convvel(1, 'kts', 'm/s');   % ini. velocity, kts
    H0                  =  1000 * convlength(1, 'ft', 'm');     % ini. altitude, ft
end

V0                      =  0;
Phi0                    =  0;
Theta0                  =  0.8633;                              % ini. euler angle, deg
Psi0                    =  0;

Lon0                    =  120.31096929726908;                  % ini. lon.
Lat0                    =  22.910275834988674;                  % ini. lat.

Vel_w                   =  0;                                   % wind velocity, kts
Psi_w                   =  0;                                   % wind direction, deg

%%  UAV Parameter

Mass0                   =   1.3;                        % empty weight, kg

Ixx                     =   2 * 0.023;                  % kg*m^2
Ixy                     =   6.56e-05;                   % kg*m^2
Iyy                     =   3 * 0.029;                  % kg*m^2
Iyz                     =   2.784e-04;                  % kg*m^2
Izz                     =   0.05;                       % kg*m^2
Ixz                     =  -2.266e-05;                  % kg*m^2

Inertia0	            =  [  Ixx -Ixy -Ixz  ;...       % moment of inertia, kg*m^2
                             -Ixy  Iyy -Iyz  ;...
                             -Ixz -Iyz  Izz ];

% Positions on the body station axis in metres (aft positive from the fuselage datum).
% The Aerodynamic block takes -CG_m / -XREF_m as body-axis (forward positive) positions and
% transfers the moments from XREF_m to CG_m. The AVL tables must be computed about XREF_m.
CG_m                    =  [0.330, 0, 0];               % centre of gravity, m
XREF_m                  =  [0.330, 0, 0];               % moment reference point of the aero tables, m

cbar                    =  0.20;                        % chord length, m
b                       =  1.41;                        % wing span, m
S                       =  0.238;                       % wing reference area, m^2
del_z                   =  0 ;                          % thrust z-axis offset, m

% Onborad Atmosphere Model
g                       =  9.80665;                     % gravity, m/s^2

%% Choose which Aerodynamic table and Fix term
useAVL_VSP = 0; % 0: AVL, 1: VSP

% Control-surface effectiveness versus |deflection| (deg); clipped outside the breakpoints.
Aeroelasticity_Gain_AIL     = [ 0.8  0.5];
Aeroelasticity_AIL          = [   5   15];
Aeroelasticity_Gain_ELE     = [ 0.9  0.6];
Aeroelasticity_ELE          = [   5   15];
Aeroelasticity_Gain_RUD     = [ 0.9  0.6];
Aeroelasticity_RUD          = [   5   15];

% AVL
run import_aerostates_avl.m;
CD_fix_AVL = 0.075;
% VSP
run import_aerostates_vsp.m;
CD_fix_VSP = 0.065;

%% Sampling Timer
Thil                    =  1/250;               % model fixed step, s

%% HIL Setting (used by sensor_HIL and the HIL_UDP blocks)
uT_to_gauss = 0.01;
m_to_mm = 1000;
ms_to_cms = 100;
gpsFreq = 10;
heartbeatFreq = 1;

%% Ground contact
uavData.contact.vd = 0.02;
uavData.contact.rollingFriction = 0.2;
uavData.contact.naturalFreq = 20;
uavData.contact.spring = Mass0*(uavData.contact.naturalFreq*2*pi)^2;
uavData.contact.damper = 2*Mass0*sqrt(uavData.contact.spring/Mass0);
