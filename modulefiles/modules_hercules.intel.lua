help([[
Modules necessary for wxvx4ufs on Hercules
]])

prepend_path("MODULEPATH", "/apps/contrib/spack-stack/spack-stack-1.9.2/envs/ue-oneapi-2024.1.0/install/modulefiles/Core")

stack_oneapi_ver=os.getenv("stack_oneapi_ver") or "2024.2.1"
load(pathJoin("stack-oneapi", stack_oneapi_ver))

prod_util_ver=os.getenv("prod_util_ver") or "2.1.1"
load(pathJoin("prod_util", prod_util_ver))

ecflow_ver=os.getenv("ecflow_ver") or "5.11.4"
load(pathJoin("ecflow", ecflow_ver))
