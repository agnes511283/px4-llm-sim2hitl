# sks_sim: the SkySurfer plant (core + C Truth + C sensors) as an in-process PX4 simulator module.
# The plant is the validated libskysurfer_plant.dylib of a model build cache (plant/core/compile_core.py),
# passed as -DSKS_PLANT_LIB=<cache>/native/libskysurfer_plant.dylib; it is linked, not recompiled with PX4 flags.
if(NOT SKS_PLANT_LIB)
	set(SKS_PLANT_LIB $ENV{SKS_PLANT_LIB})
endif()
if(NOT EXISTS "${SKS_PLANT_LIB}")
	message(FATAL_ERROR "sks_sim: set SKS_PLANT_LIB to <cache>/native/libskysurfer_plant.dylib")
endif()
get_filename_component(SKS_PROJECT_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../../.." ABSOLUTE)

px4_add_module(
	MODULE modules__sks_sim
	MAIN sks_sim
	INCLUDES
		${SKS_PROJECT_ROOT}/plant/include
	SRCS
		SksSim.cpp
		SksSim.hpp
	)
# External modules are configured before src/lib, so PX4 libraries are linked by name here (resolved at
# generation time) instead of px4_add_module DEPENDS.
target_link_libraries(modules__sks_sim PRIVATE drivers_accelerometer drivers_gyroscope ${SKS_PLANT_LIB})
