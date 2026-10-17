function cacheRoot = build_core()
% Generate the reusable plant core (C) from the saved FW_SkySurfer_HIL.slx.
%
% The source model already exposes the core interface: root inport Controls[16] and root outport
% CoreSnapshot[72] (layout in docs/MODEL_INTERFACE.md). This builder works on a cache copy only:
% it adds a Thil zero-order hold so the snapshot is sampled at t_k, binds the initial conditions as
% per-instance model parameters, and generates ERT C with CodeInterfacePackaging = Reusable function.
% It also simulates the source copy and the core copy with the same controls (ground and air) and
% writes results/source_<case>.csv and core_<case>.csv: the HIL release validation
% (hil_runtime/tests/validate_library.py) requires them to be identical and compares the native
% library against them. Compile and validate with plant/core/compile_core.py. The formal source is
% never modified. It refuses to start unless the reuse-library policy gate passes
% (reuse_policy_gate.m; result in results/reuse_policy.json).
coreDir = fileparts(mfilename('fullpath'));
projectRoot = fileparts(fileparts(coreDir));
sourceModel = 'FW_SkySurfer_HIL';
sourceFile = fullfile(projectRoot, [sourceModel '.slx']);
if bdIsLoaded(sourceModel)
    assert(strcmp(get_param(sourceModel, 'Dirty'), 'off'), 'Save the source model before building the core.');
    assert(strcmp(get_param(sourceModel, 'SimulationStatus'), 'stopped'), 'Stop the source model before building the core.');
end
% Reuse-library policy gate (plant/core/reuse_policy_gate.m): refuse before creating a cache.
gate = reuse_policy_gate(projectRoot);
assert(strcmp(gate.status, 'PASS'), 'Custom library policy is not ready: %s', gate.reason);
model = 'SkySurfer_Core';
assert(~bdIsLoaded(model), 'Close the previous SkySurfer_Core copy before rebuilding.');
cacheRoot = fullfile(getenv('HOME'), 'Library', 'Caches', 'Codex', 'SkySurferPhaseB', ...
    ['core_' char(datetime('now', 'Format', 'yyyyMMdd_HHmmss_SSS'))]);
mkdir(fullfile(cacheRoot, 'models')); mkdir(fullfile(cacheRoot, 'results'));
fid = fopen(fullfile(cacheRoot, 'results', 'reuse_policy.json'), 'w');
fprintf(fid, '%s', jsonencode(gate, 'PrettyPrint', true)); fclose(fid);
previousFolder = pwd; previousFileGen = Simulink.fileGenControl('getConfig');
restore = onCleanup(@() core_restore(previousFolder, previousFileGen, model));
cd(projectRoot);
copyfile(sourceFile, fullfile(cacheRoot, 'models', [model '.slx']));
evalin('base', "run('PX4_HIL_preload.m'); lastRunModel='FW_SkySurfer_HIL'; run('FW_SkySurfer_InitialFunction.m');");
load_system(fullfile(cacheRoot, 'models', [model '.slx']));
set_param(model, 'PreLoadFcn', '', 'InitFcn', '', 'EnablePacing', 'off');

% Root interface check: exactly Controls[16] in, CoreSnapshot out.
inports = find_system(model, 'SearchDepth', 1, 'BlockType', 'Inport');
outports = find_system(model, 'SearchDepth', 1, 'BlockType', 'Outport');
assert(isequal(get_param(inports, 'Name'), {'Controls'}) && isequal(get_param(outports, 'Name'), {'CoreSnapshot'}), ...
    'Source root interface changed: expected Controls -> CoreSnapshot.');
mapping = Simulink.ID.getFullName([model ':96293']);
selectors = find_system(mapping, 'SearchDepth', 1, 'BlockType', 'Selector');
assert(numel(selectors) == 1 && isequal(str2num(get_param(selectors{1}, 'Indices')), [1 2 3 4 5]), ...
    'Mapping interface changed: review the core wrapper.'); %#ok<ST2NM>

% Sample the snapshot at t_k (same output phase as the HIL ABI).
out = [model '/CoreSnapshot'];
line = get_param(get_param(out, 'LineHandles').Inport, 'Handle');
src = get_param(line, 'SrcPortHandle'); delete_line(line);
p = get_param(out, 'Position');
add_block('simulink/Discrete/Zero-Order Hold', [model '/SampleCoreSnapshot'], 'SampleTime', 'Thil', ...
    'Position', [p(1) - 80, p(2) - 3, p(1) - 40, p(4) + 3]);
zoh = get_param([model '/SampleCoreSnapshot'], 'PortHandles');
add_line(model, src, zoh.Inport(1)); add_line(model, zoh.Outport(1), get_param(out, 'PortHandles').Inport(1));

% Initial conditions per instance. Reusable ERT code keeps model parameters in one shared global,
% so the seven initial-condition constants of SETTING1 are replaced (in this copy only) by a root
% inport InitialConditions[7] = [U0 V0 W0 H0 Phi0 Theta0 Psi0] (m/s, m, deg), which lives in each
% instance's input structure. Line names are kept because the INI_COND bus takes its element names
% from them. Lat0/Lon0 stay constants: the core no longer uses them (C Truth computes LLA).
icNames = {'U0', 'V0', 'W0', 'H0', 'Phi0', 'Theta0', 'Psi0'};
icSids = [94888 94889 94890 94881 94891 94892 94878]; % const5 const6 const7 const13 const8 const9 const10
baseline = struct;
for k = 1:numel(icNames), baseline.(icNames{k}) = evalin('base', icNames{k}); end
p = get_param(inports{1}, 'Position');
add_block('simulink/Sources/In1', [model '/InitialConditions'], 'Port', '2', 'PortDimensions', '7', ...
    'SampleTime', 'Thil', 'Interpolate', 'off', 'Position', p + [0 120 0 120]);
add_block('simulink/Signal Routing/Demux', [model '/SplitInitialConditions'], 'Outputs', '7', ...
    'Position', p + [80 100 85 260]);
icIn = get_param([model '/InitialConditions'], 'PortHandles'); demux = get_param([model '/SplitInitialConditions'], 'PortHandles');
add_line(model, icIn.Outport(1), demux.Inport(1));
for k = 1:numel(icNames)
    tag = ['IC_' icNames{k}];
    add_block('simulink/Signal Routing/Goto', [model '/Goto_' tag], 'GotoTag', tag, 'TagVisibility', 'global', ...
        'Position', p + [140 100 + 22 * (k - 1) 220 116 + 22 * (k - 1)]);
    add_line(model, demux.Outport(k), get_param([model '/Goto_' tag], 'PortHandles').Inport(1));
    constant = Simulink.ID.getHandle(sprintf('%s:%d', model, icSids(k)));
    assert(strcmp(get_param(constant, 'Value'), icNames{k}), 'SETTING1 constant %d no longer holds %s.', icSids(k), icNames{k});
    parent = get_param(constant, 'Parent'); pos = get_param(constant, 'Position');
    lineHandle = get_param(constant, 'LineHandles').Outport;
    signalName = get_param(lineHandle, 'Name'); dst = get_param(lineHandle, 'DstPortHandle');
    delete_line(lineHandle); delete_block(constant);
    from = [parent '/From_' tag];
    add_block('simulink/Signal Routing/From', from, 'GotoTag', tag, 'Position', pos);
    newLine = add_line(parent, get_param(from, 'PortHandles').Outport(1), dst);
    set_param(newLine, 'Name', signalName);
end
set_param(model, 'SystemTargetFile', 'ert.tlc', 'ProdHWDeviceType', 'Apple->ARM64', 'TargetLang', 'C', ...
    'Solver', 'ode4', 'SolverType', 'Fixed-step', 'FixedStep', 'Thil', 'SupportContinuousTime', 'on', ...
    'SupportNonFinite', 'on', 'CodeInterfacePackaging', 'Reusable function', 'RootIOFormat', 'Structure reference', ...
    'GenerateAllocFcn', 'off', 'MultiInstanceErrorCode', 'Error', 'IncludeMdlTerminateFcn', 'on', ...
    'CombineOutputUpdateFcns', 'on', 'DefaultParameterBehavior', 'Tunable', 'GenerateReport', 'off', ...
    'GenerateSampleERTMain', 'off', 'MatFileLogging', 'off', 'ExtMode', 'off', 'GenCodeOnly', 'on');
save_system(model, fullfile(cacheRoot, 'models', [model '.slx']));
core_references(cacheRoot, sourceFile, model, baseline);
Simulink.fileGenControl('set', 'CacheFolder', fullfile(cacheRoot, 'cache'), ...
    'CodeGenFolder', fullfile(cacheRoot, 'codegen'), 'createDir', true);
baseline.source_slx_sha256 = core_sha256(sourceFile);
baseline.matlab = version;
baseline.dt = evalin('base', 'Thil');
fid = fopen(fullfile(cacheRoot, 'results', 'core_build.json'), 'w');
fprintf(fid, '%s', jsonencode(baseline, 'PrettyPrint', true)); fclose(fid);
diary(fullfile(cacheRoot, 'results', 'codegen.log'));
slbuild(model, 'GenerateCodeOnly', true);
diary off;
end

function core_references(cacheRoot, sourceFile, model, baseline)
% Ground and air reference runs of the unmodified source (copy) and of the core copy.
source = 'SkySurfer_CoreSource';
assert(~bdIsLoaded(source), 'Close the previous SkySurfer_CoreSource copy before rebuilding.');
copyfile(sourceFile, fullfile(cacheRoot, 'models', [source '.slx']));
load_system(fullfile(cacheRoot, 'models', [source '.slx']));
closer = onCleanup(@() close_system(source, 0));
set_param(source, 'PreLoadFcn', '', 'InitFcn', '', 'EnablePacing', 'off');
dt = 0.004; duration = 1.2; t = (0:dt:duration)';
controls = zeros(numel(t), 16); % five single-channel pulses, then all 16 channels
for k = 1:5
    controls(t >= 0.1 + (k - 1) * 0.15 & t < 0.15 + (k - 1) * 0.15, k) = 0.1 * k;
end
controls(t >= 0.9 & t < 1, :) = repmat((1:16) * 0.015, sum(t >= 0.9 & t < 1), 1);
labels = {'ground', 'air'};
values = {struct(), struct('U0', 20, 'H0', 100, 'Psi0', 25)};
names = {'U0', 'V0', 'W0', 'H0', 'Phi0', 'Theta0', 'Psi0'};
for c = 1:2
    ic = zeros(1, 7);
    for k = 1:7
        ic(k) = baseline.(names{k});
        if isfield(values{c}, names{k}), ic(k) = values{c}.(names{k}); end
    end
    in = Simulink.SimulationInput(source);
    in = in.setModelParameter('StopTime', num2str(duration), 'SaveOutput', 'on', 'SaveFormat', 'Dataset', ...
        'SaveTime', 'on', 'OutputSaveName', 'yout');
    ds = Simulink.SimulationData.Dataset; ds{1} = timeseries(controls, t); in = in.setExternalInput(ds);
    for k = 1:7, in = in.setVariable(names{k}, ic(k)); end
    sourceData = core_snapshot_rows(sim(in));
    in = Simulink.SimulationInput(model);
    in = in.setModelParameter('StopTime', num2str(duration), 'SaveOutput', 'on', 'SaveFormat', 'Dataset', ...
        'SaveTime', 'on', 'OutputSaveName', 'yout');
    ds = Simulink.SimulationData.Dataset; ds{1} = timeseries(controls, t); ds{2} = timeseries(repmat(ic, numel(t), 1), t);
    in = in.setExternalInput(ds);
    coreData = core_snapshot_rows(sim(in));
    writematrix(sourceData, fullfile(cacheRoot, 'results', ['source_' labels{c} '.csv']));
    writematrix(coreData, fullfile(cacheRoot, 'results', ['core_' labels{c} '.csv']));
    writematrix([t, controls], fullfile(cacheRoot, 'results', ['controls_' labels{c} '.csv']));
    fprintf('REFERENCE %s: %d samples, source == core copy: %d\n', labels{c}, size(coreData, 1), isequal(sourceData, coreData));
end
end

function rows = core_snapshot_rows(out)
% [time, CoreSnapshot(72)] at the major steps t_k.
v = out.yout.getElement(1).Values;
d = squeeze(v.Data);
if size(d, 1) ~= numel(v.Time), d = d.'; end
assert(size(d, 2) == 72, 'CoreSnapshot width changed');
rows = [v.Time, double(d)];
end

function digest = core_sha256(file)
fid = fopen(file, 'r'); bytes = fread(fid, inf, '*uint8'); fclose(fid);
md = java.security.MessageDigest.getInstance('SHA-256');
digest = sprintf('%02x', typecast(md.digest(bytes), 'uint8'));
end

function core_restore(folder, fileGen, model)
cd(folder); Simulink.fileGenControl('setConfig', 'config', fileGen);
if bdIsLoaded(model), close_system(model, 0); end
end
