function sks_ulog_plot(ulgPath, outPng, titleText)
%SKS_ULOG_PLOT  Overview plot of one SkySurfer ULog (SITL or the FC's HITL log): course, altitude with the TECS
%setpoint, roll with the lateral-acceleration setpoint, airspeed with the TECS airspeed setpoint, and the time in
%OFFBOARD shaded. An example to start from: copy it and plot what your module needs.
%
%   sks_ulog_plot('<flight>.ulg')                    % opens a figure
%   sks_ulog_plot('<flight>.ulg', 'overview.png')    % writes the picture (no window)
%
% Needs MATLAB with UAV Toolbox (ulogreader); no Java. Without UAV Toolbox, export the topics to CSV with
% analysis/ulog_export.py and read them with readtable. Topics missing from a log are left out of the plot.
arguments
    ulgPath (1,:) char
    outPng (1,:) char = ''
    titleText (1,:) char = ''
end
reader = ulogreader(ulgPath);
names = {'vehicle_local_position', 'vehicle_attitude', 'airspeed_validated', 'fixed_wing_lateral_setpoint', ...
         'tecs_status', 'vehicle_status'};
names = names(ismember(names, reader.AvailableTopics.TopicNames));
msgs = readTopicMsgs(reader, 'TopicNames', names);
topic = @(n) pick(msgs, n);
t0 = reader.StartTime;
since = @(tt) seconds(tt.timestamp - t0);

visible = 'on';
if ~isempty(outPng), visible = 'off'; end
fig = figure('Visible', visible, 'Position', [0 0 1000 900]);
layout = tiledlayout(fig, 4, 1, 'TileSpacing', 'compact');
if isempty(titleText)
    [~, base, ext] = fileparts(ulgPath); titleText = [base ext];
end
title(layout, titleText, 'Interpreter', 'none');

offboard = [];
status = topic('vehicle_status');
if ~isempty(status)
    offboard = [since(status), double(status.nav_state == 14)];  % NAVIGATION_STATE_OFFBOARD
end

lp = topic('vehicle_local_position');
ax = nexttile(layout);
if ~isempty(lp)
    plot(ax, since(lp), rad2deg(unwrap(atan2(double(lp.vy), double(lp.vx)))), 'LineWidth', 1.2);
end
ylabel(ax, 'course [deg]'); shade(ax, offboard); grid(ax, 'on');

ax = nexttile(layout); hold(ax, 'on');
if ~isempty(lp), plot(ax, since(lp), -double(lp.z) + double(lp.ref_alt), 'LineWidth', 1.2, 'DisplayName', 'altitude'); end
tecs = topic('tecs_status');
if ~isempty(tecs), plot(ax, since(tecs), double(tecs.altitude_sp), '--', 'DisplayName', 'TECS setpoint'); end
ylabel(ax, 'altitude AMSL [m]'); legend(ax, 'Location', 'best'); shade(ax, offboard); grid(ax, 'on');

ax = nexttile(layout);
att = topic('vehicle_attitude');
if ~isempty(att)
    q = double(att.q);
    plot(ax, since(att), rad2deg(atan2(2 * (q(:,1) .* q(:,2) + q(:,3) .* q(:,4)), 1 - 2 * (q(:,2).^2 + q(:,3).^2))), ...
         'LineWidth', 1.0);
end
ylabel(ax, 'roll [deg]');
lat = topic('fixed_wing_lateral_setpoint');
if ~isempty(lat)
    yyaxis(ax, 'right'); plot(ax, since(lat), double(lat.lateral_acceleration)); ylabel(ax, 'lateral accel sp [m/s^2]');
    yyaxis(ax, 'left');
end
shade(ax, offboard); grid(ax, 'on');

ax = nexttile(layout); hold(ax, 'on');
as = topic('airspeed_validated');
if ~isempty(as), plot(ax, since(as), double(as.calibrated_airspeed_m_s), 'LineWidth', 1.2, 'DisplayName', 'CAS'); end
if ~isempty(tecs), plot(ax, since(tecs), double(tecs.equivalent_airspeed_sp), '--', 'DisplayName', 'TECS airspeed setpoint'); end
ylabel(ax, 'airspeed [m/s]'); xlabel(ax, 'time since log start [s]'); legend(ax, 'Location', 'best');
shade(ax, offboard); grid(ax, 'on');

linkaxes(findall(fig, 'Type', 'axes'), 'x');
if ~isempty(outPng)
    exportgraphics(fig, outPng, 'Resolution', 110);
    close(fig);
end
end

function data = pick(msgs, name)
row = strcmp(msgs.TopicNames, name);
if any(row), data = msgs.TopicMessages{find(row, 1)}; else, data = []; end
end

function shade(ax, offboard)
% Grey band over the time in OFFBOARD.
if isempty(offboard) || ~any(offboard(:, 2)), return, end
on = offboard(:, 2) > 0; starts = find(diff([0; on]) == 1); stops = find(diff([on; 0]) == -1);
limits = ylim(ax);
for k = 1:numel(starts)
    patch(ax, offboard([starts(k) stops(k) stops(k) starts(k)], 1), limits([1 1 2 2]), [0.5 0.5 0.5], ...
          'FaceAlpha', 0.12, 'EdgeColor', 'none', 'HandleVisibility', 'off');
end
ylim(ax, limits);
end
