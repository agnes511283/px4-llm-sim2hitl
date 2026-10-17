#include "SksHello.hpp"

#include <px4_platform_common/log.h>

SksHello::SksHello() : ScheduledWorkItem(MODULE_NAME, px4::wq_configurations::lp_default) {}

bool SksHello::init()
{
	_started = hrt_absolute_time();
	ScheduleNow();  // the first report at once, then every REPORT_INTERVAL
	ScheduleOnInterval(REPORT_INTERVAL, REPORT_INTERVAL);
	return true;
}

void SksHello::Run()
{
	if (should_exit()) {
		ScheduleClear();
		exit_and_cleanup();
		return;
	}

	_reports++;
	PX4_INFO("sks_hello report %u (%.0f s after start)", (unsigned)_reports,
		 (double)((hrt_absolute_time() - _started) * 1e-6));
}

int SksHello::task_spawn(int argc, char *argv[])
{
	SksHello *instance = new SksHello();

	if (instance) {
		_object.store(instance);
		_task_id = task_id_is_work_queue;

		if (instance->init()) {
			return PX4_OK;
		}

	} else {
		PX4_ERR("alloc failed");
	}

	delete instance;
	_object.store(nullptr);
	_task_id = -1;
	return PX4_ERROR;
}

int SksHello::print_status()
{
	PX4_INFO("running, %u reports", (unsigned)_reports);
	return 0;
}

int SksHello::custom_command(int argc, char *argv[])
{
	return print_usage("unknown command");
}

int SksHello::print_usage(const char *reason)
{
	if (reason) {
		PX4_WARN("%s\n", reason);
	}

	PRINT_MODULE_DESCRIPTION(
		R"DESCR_STR(
### Description
SkySurfer report-only module: writes "sks_hello report <n>" at start and every 10 s, nothing else.
)DESCR_STR");

	PRINT_MODULE_USAGE_NAME("sks_hello", "template");
	PRINT_MODULE_USAGE_COMMAND("start");
	PRINT_MODULE_USAGE_DEFAULT_COMMANDS();
	return 0;
}

extern "C" __EXPORT int sks_hello_main(int argc, char *argv[])
{
	return SksHello::main(argc, argv);
}
