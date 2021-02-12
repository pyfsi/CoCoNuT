from coconut import data_structure
from coconut.coupling_components.tools import CreateInstance

import numpy as np
from sys import argv


# Check number of command line arguments
if len(argv) != 2:
    err_msg = 'Wrong number of input arguments!\n'
    err_msg += 'Use this script in the following way:\n'
    err_msg += '    "python co_simulation_analysis.py <cosim-parameter-file>.json"\n'
    raise Exception(err_msg)


# Import data structure
parameter_file_name = argv[1]

# Import parameters using the data structure
with open(parameter_file_name, 'r') as parameter_file:
    parameters = data_structure.Parameters(parameter_file.read())

solver = CreateInstance(parameters['solver_wrappers'][0])


settings = parameters['solver_wrappers'][0]['settings']

# steady test
if 0:
    solver.Initialize()
    solver.InitializeSolutionStep()

    interface_input = solver.GetInterfaceInput()
    for iteration in range(3):
        iteration += 1
        print(f'\niteration {iteration}')
        solver.SolveSolutionStep(interface_input)
        interface_input = solver.GetInterfaceInput()
        for key in settings['interface_input'].keys():
            for node in interface_input.model[key].Nodes:
                dy = (1 - np.cos(2 * np.pi * node.X0)) * 0.5 * 0.01  # this used node.X before
                node.SetSolutionStepValue(vars(data_structure)['DISPLACEMENT'], 0, [0., dy, 0.])

    solver.FinalizeSolutionStep()
    solver.Finalize()

# unsteady test
else:
    solver.Initialize()

    interface_input = solver.GetInterfaceInput()
    for timestep in range(1, 5):
        f = 0.005 * (-1) ** (timestep + 1)
        f = 0.05
        solver.InitializeSolutionStep()
        for iteration in range(1, 3):
            solver.SolveSolutionStep(interface_input)
            interface_input = solver.GetInterfaceInput()
            for key in settings['interface_input'].keys():
                for node in interface_input.model[key].Nodes:
                    dy = (1 - np.cos(
                        2 * np.pi * (node.X0 - timestep / 4 - iteration / 16))) * 0.5 * f  # this used node.X before
                    node.SetSolutionStepValue(vars(data_structure)['DISPLACEMENT'], 0, [0., dy, 0.])
        solver.FinalizeSolutionStep()

    solver.Finalize()