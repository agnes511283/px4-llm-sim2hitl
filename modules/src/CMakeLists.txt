# Out-of-tree PX4 modules of the SkySurfer firmware (docs/ROADMAP.md decision 9, flow A step 2).
# Firmware: make px4_fmu-v6c_default EXTERNAL_MODULES_LOCATION=<this folder's parent>; the SITL build uses each
# module through a wrapper in sitl/px4_external/src/ (one EXTERNAL_MODULES_LOCATION per build).
set(config_module_list_external
	sks_hello
	PARENT_SCOPE
)
