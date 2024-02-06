"""
This file contains the module load commands for the solvers, for different machines in form of python-dict. This
is used for setting up the environment variables required by the solvers. During the simulation, the solver wrapper
uses the environment variables in all the spawned processes, used for executing the solver-specific terminal commands
in the various stages of the simulation.
"""

machine_name = 'ugent_cluster_CO7'

solver_load_cmd_dict = {
    'ugent_cluster_CO7': {
        'fluent.v2019R3': 'ml ANSYS_CFD/2019R3',
        'fluent.v2021R1': 'ml ANSYS_CFD/2021R1',
        'fluent.v2023R1': 'ml ANSYS_CFD/2023R1',
        'abaqus.v2021': 'ml intel/2020a && ml ABAQUS/2021 && export LM_LICENSE_FILE=@ir03lic1.ugent.be:@bump.ugent.be',
        'abaqus.v2022': 'ml intel/2020a && ml ABAQUS/2022 && export LM_LICENSE_FILE=@ir03lic1.ugent.be:@bump.ugent.be',
        'kratos_structure.v91': 'ml Anaconda3-python/2020.11',
        'openfoam.v8': 'ml OpenFOAM/8-foss-2020b && source $FOAM_BASH'
    },
    'ugent_hpc': {
        'fluent.v2019R3': 'ml FLUENT/2019R3 && ml intel/2020a && unset SLURM_GTIDS '
                          '&& export ANSYSLI_SERVERS=2325@ir03lic1.ugent.be '
                          '&& export ANSYSLMD_LICENSE_FILE=1055@ir03lic1.ugent.be && cat $PBS_NODEFILE > fluent.hosts',
        'fluent.v2023R1': 'ml FLUENT/2023R1 && ml intel/2021a && unset SLURM_GTIDS '
                          '&& export ANSYSLI_SERVERS=2325@ir03lic1.ugent.be '
                          '&& export ANSYSLMD_LICENSE_FILE=1055@ir03lic1.ugent.be && cat $PBS_NODEFILE > fluent.hosts',
        'abaqus.v2021': 'ml intel/2020a && ml ABAQUS/2021-hotfix-2132 '
                        '&& export LM_LICENSE_FILE=@ir03lic1.ugent.be:@bump.ugent.be',
        'abaqus.v2022': 'ml intel/2020a && ml ABAQUS/2022-hotfix-2214 '
                        '&& export LM_LICENSE_FILE=@ir03lic1.ugent.be:@bump.ugent.be',
        'openfoam.v8': 'ml OpenFOAM/8-foss-2020b && source $FOAM_BASH'
    },
    'hortense': {
        'fluent.v2019R3': 'ml FLUENT/2019R3 && ml intel/2021a '
                          '&& export ANSYSLI_SERVERS=2325@ir03lic1.ugent.be '
                          '&& export ANSYSLMD_LICENSE_FILE=1055@ir03lic1.ugent.be && cat $PBS_NODEFILE > fluent.hosts',
        'fluent.v2021R1': 'ml FLUENT/2021R1 && ml intel/2021a '
                          '&& export ANSYSLI_SERVERS=2325@ir03lic1.ugent.be '
                          '&& export ANSYSLMD_LICENSE_FILE=1055@ir03lic1.ugent.be && cat $PBS_NODEFILE > fluent.hosts',
        'fluent.v2023R1': 'ml FLUENT/2023R1 && ml intel/2021a '
                          '&& export ANSYSLI_SERVERS=2325@ir03lic1.ugent.be '
                          '&& export ANSYSLMD_LICENSE_FILE=1055@ir03lic1.ugent.be && cat $PBS_NODEFILE > fluent.hosts',
        'abaqus.v2022': 'ml intel/2021a && module load ABAQUS/2022 '
                        '&& export LM_LICENSE_FILE=@ir03lic1.ugent.be:@bump.ugent.be',
        'openfoam.v8': 'ml OpenFOAM/8-foss-2020b && source $FOAM_BASH'
    }
}


def get_solver_cmd(solver_name):
    return solver_load_cmd_dict[machine_name][solver_name]
