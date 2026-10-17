# Out-of-tree PX4 modules of the SkySurfer SITL (docs/ROADMAP.md decision 8).
# Built with: make px4_sitl_default EXTERNAL_MODULES_LOCATION=<this folder's parent> (see sitl/README.md).
set(config_module_list_external
	sks_sim
	sks_hello
	PARENT_SCOPE
)
