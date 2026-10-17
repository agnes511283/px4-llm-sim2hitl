/**
 * sks_hello: a report-only module (ROADMAP batch 6: one small change through the whole of flow A).
 *
 * It reads nothing and publishes nothing: it only says that it runs. At start, and then every
 * SksHello::REPORT_INTERVAL of PX4 time, PX4_INFO writes "sks_hello report <n>"; PX4 publishes that as
 * log_message, so it is in the ULog (and on the console). `sks_hello status` prints the count.
 * On the FC it is started by /fs/microsd/etc/extras.txt ("sks_hello start"; hil_bridge/docs/
 * BEHAVIOR_CONTRACT.md 7f); in SITL by run_sitl.py --start "sks_hello start".
 */
#pragma once

#include <px4_platform_common/module.h>
#include <px4_platform_common/px4_work_queue/ScheduledWorkItem.hpp>
#include <drivers/drv_hrt.h>

using namespace time_literals;

class SksHello : public ModuleBase<SksHello>, public px4::ScheduledWorkItem
{
public:
	static constexpr hrt_abstime REPORT_INTERVAL = 10_s;

	SksHello();
	~SksHello() override = default;

	static int task_spawn(int argc, char *argv[]);
	static int custom_command(int argc, char *argv[]);
	static int print_usage(const char *reason = nullptr);

	bool init();
	int print_status() override;

private:
	void Run() override;

	uint32_t _reports{0};
	hrt_abstime _started{0};
};
