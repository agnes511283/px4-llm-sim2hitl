function gate = reuse_policy_gate(projectRoot)
% Reuse-library policy gate of the core builder (plant/core/build_core.m).
%
% The project declares in .satk/reuse-libraries.json that the source uses no custom reuse
% libraries ("libraries": [], "confirmed_none": true). The builder does not support custom
% libraries, so anything else (missing or unreadable file, confirmed_none not true, any library
% listed) is refused. SATK's library.settingsLookup reports gatePass = true even when the file is
% missing or confirmed_none is false, so it cannot serve as the gate; its result is only recorded.
% The policy file's SHA-256 is recorded by hitl/update.py (no Java needed here).
policyFile = fullfile(projectRoot, '.satk', 'reuse-libraries.json');
gate = struct('policy_file', policyFile, 'confirmed_none', false, ...
    'libraries', 0, 'satk_gate_pass', [], 'status', 'FAIL', 'reason', '');
if ~isfile(policyFile)
    gate.reason = 'Reuse-library policy file is missing.';
    return
end
try
    policy = jsondecode(fileread(policyFile));
catch err
    gate.reason = ['Reuse-library policy is not valid JSON: ' err.message];
    return
end
if isfield(policy, 'confirmed_none') && islogical(policy.confirmed_none) && isscalar(policy.confirmed_none)
    gate.confirmed_none = policy.confirmed_none;
end
if isfield(policy, 'libraries'), gate.libraries = numel(policy.libraries); end
if ~isempty(which('library.settingsLookup'))
    previous = cd(projectRoot); back = onCleanup(@() cd(previous));
    satk = library.settingsLookup(); gate.satk_gate_pass = logical(satk.gatePass);
end
if ~isfield(policy, 'libraries')
    gate.reason = 'Reuse-library policy has no "libraries" list.';
elseif ~gate.confirmed_none
    gate.reason = 'Reuse-library policy is not confirmed_none = true.';
elseif gate.libraries ~= 0
    gate.reason = 'Custom reuse libraries are listed; the core builder does not support them.';
else
    gate.status = 'PASS';
end
end
