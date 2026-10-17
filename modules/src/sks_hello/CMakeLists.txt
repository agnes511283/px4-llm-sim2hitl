# sks_hello: report-only module (ROADMAP batch 6). Sources by absolute path, so the SITL wrapper
# (sitl/px4_external/src/sks_hello/CMakeLists.txt) can include this file unchanged.
px4_add_module(
	MODULE modules__sks_hello
	MAIN sks_hello
	SRCS
		${CMAKE_CURRENT_LIST_DIR}/SksHello.cpp
		${CMAKE_CURRENT_LIST_DIR}/SksHello.hpp
	)
# External modules are configured before src/lib: PX4 libraries are linked by name.
target_link_libraries(modules__sks_hello PRIVATE px4_work_queue)
