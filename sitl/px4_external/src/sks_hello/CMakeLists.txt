# SITL wrapper: the module itself is modules/src/sks_hello/ (the firmware's EXTERNAL_MODULES_LOCATION).
get_filename_component(SKS_PROJECT_ROOT "${CMAKE_CURRENT_LIST_DIR}/../../../.." ABSOLUTE)
include(${SKS_PROJECT_ROOT}/modules/src/sks_hello/CMakeLists.txt)
