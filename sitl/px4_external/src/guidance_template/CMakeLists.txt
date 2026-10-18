# SITL wrapper: the module itself is modules/src/guidance_template/ (the firmware's EXTERNAL_MODULES_LOCATION).
get_filename_component(SIM2HITL_PROJECT_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../../.." ABSOLUTE)
include(${SIM2HITL_PROJECT_ROOT}/modules/src/guidance_template/CMakeLists.txt)
