function tables = build_avl_mat(resultJson, templateMat, outMat, machTag)
% BUILD_AVL_MAT  Convert an AVL MCP job result into the cell-table MAT format read by
% import_aerostates_avl.m (one 93x6 cell per alpha: column 1 labels, columns 2..6 = beta).
%
%   tables = build_avl_mat(resultJson, templateMat, outMat, machTag)
%
%   resultJson  result.json of an AVL MCP job (60 cases: Mach x alpha x beta grid)
%   templateMat existing MAT (m_05.mat or m_1.mat) whose row labels are reused
%   outMat      MAT file to write; '' returns the tables without writing
%   machTag     'm05' (Mach 0.05) or 'm1' (Mach 0.10)
%
% Controls are matched by name: d01 aileronR, d02 aileronL, d03 elevator, d04 rudder (the
% order the Simulink Aerodynamic subsystem wires them), not by AVL declaration order.
mach = struct('m05', 0.05, 'm1', 0.10);
mach = mach.(machTag);
alphas = [-10 -5 0 5 10 15];
betas = [-10 -5 0 5 10];
controls = {'aileronR', 'aileronL', 'elevator', 'rudder'};
r = jsondecode(fileread(resultJson));
cases = r.results;
if ~iscell(cases), cases = num2cell(cases); end
tpl = load(templateMat);
names = fieldnames(tpl);
labels = tpl.(names{1})(:, 1);
tables = struct;
for ia = 1:numel(alphas)
    a = alphas(ia);
    name = sprintf('%s_a_%s', machTag, alpha_token(a));
    t = cell(numel(labels), 1 + numel(betas));
    t(:, 1) = labels;
    for ib = 1:numel(betas)
        c = find_case(cases, mach, a, betas(ib));
        for row = 1:numel(labels)
            if strcmp(labels{row}, 'Cnb') && row == numel(labels)
                % The last row is AVL's spiral parameter Clb*Cnr/(Clr*Cnb), parsed as 'Cnb'.
                t{row, ib + 1} = c.stability.diagnostics.spiral_parameter;
            else
                t{row, ib + 1} = value_for(labels{row}, c, machTag, a, betas(ib), controls);
            end
        end
    end
    tables.(name) = t;
end
if ~isempty(outMat)
    save(outMat, '-struct', 'tables');
end
end

function c = find_case(cases, mach, a, b)
for k = 1:numel(cases)
    f = cases{k}.total.fields;
    if abs(f.Mach - mach) < 1e-9 && abs(f.Alpha - a) < 1e-9 && abs(f.Beta - b) < 1e-9
        assert(cases{k}.success, 'AVL case failed: M=%g a=%g b=%g', mach, a, b);
        c = cases{k};
        return
    end
end
error('Missing AVL case: M=%g a=%g b=%g', mach, a, b);
end

function s = alpha_token(a)
if a < 0, s = sprintf('n%d', -a); else, s = sprintf('%d', a); end
end

function v = value_for(label, c, machTag, a, b, controls)
tf = c.total.fields;
sd = c.stability.derivatives;
cd = c.stability.control_derivatives;
switch label
    case 'CaseName', v = sprintf('%s_a_%s_b_%s', machTag, alpha_token(a), alpha_token(b)); return
    case 'Alpha', v = tf.Alpha; return
    case 'Beta', v = tf.Beta; return
    case 'Mach', v = tf.Mach; return
    case 'pb_over_2V', v = tf.pb_2V; return
    case 'p_dot_b_over_2V', v = tf.p_b_2V; return
    case 'qc_over_2V', v = tf.qc_2V; return
    case 'rb_over_2V', v = tf.rb_2V; return
    case 'r_dot_b_over_2V', v = tf.r_b_2V; return
    case 'Cl_dot_tot', v = tf.Cl_tot; return
    case 'Cn_dot_tot', v = tf.Cn_tot; return
    case 'Xnp', v = c.stability.diagnostics.neutral_point_x; return
end
if any(strcmp(label, controls)), v = c.total.controls.(label); return, end
if isfield(tf, label), v = tf.(label); return, end
tok = regexp(label, '^(CL|CY|CD|Cl|Cm|Cn|CDff|e)d0([1-4])$', 'tokens', 'once');
if ~isempty(tok)
    ctrl = controls{str2double(tok{2})};
    key = tok{1};
    v = cd.(ctrl).(key);
    return
end
if isfield(sd, label), v = sd.(label); return, end
error('No AVL source for row label %s', label);
end
