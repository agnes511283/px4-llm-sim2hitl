# Out-of-tree PX4 modules of the SITL.
# Built with: make px4_sitl_default EXTERNAL_MODULES_LOCATION=<this folder's parent> (see sitl/README.md).
set(config_module_list_external
	plant_sim
	guidance_template
	PARENT_SCOPE
)
