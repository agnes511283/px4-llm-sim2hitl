# guidance_template: example module (OFFBOARD guidance from inside the firmware). Sources by absolute path, so the SITL wrapper
# (sitl/px4_external/src/guidance_template/CMakeLists.txt) can include this file unchanged.
px4_add_module(
	MODULE modules__guidance_template
	MAIN guidance_template
	SRCS
		${CMAKE_CURRENT_LIST_DIR}/GuidanceTemplate.cpp
		${CMAKE_CURRENT_LIST_DIR}/GuidanceTemplate.hpp
	)
# External modules are configured before src/lib: PX4 libraries are linked by name.
target_link_libraries(modules__guidance_template PRIVATE px4_work_queue)
