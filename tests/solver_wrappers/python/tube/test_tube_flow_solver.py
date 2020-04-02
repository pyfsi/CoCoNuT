from coconut import data_structure
from coconut.data_structure import KratosUnittest
from coconut.coupling_components.tools import CreateInstance

import numpy as np
import os
import subprocess

class TestSolverWrapperTubeFlowSolver(KratosUnittest.TestCase):
    def assertArrayAlmostEqual(self, a1, a2, delta=None):
        ls1 = list(a1)
        ls2 = list(a2)
        try:
            self.assertEqual(ls1, ls2)
        except AssertionError:
            for i in range(len(ls1)):
                self.assertAlmostEqual(ls1[i], ls2[i], delta=delta)

    def test_solver_wrapper_tube_flow_solver(self):
        parameter_file_name = os.path.join(os.path.dirname(__file__), 'test_tube_flow_solver.json')
        with open(parameter_file_name, 'r') as parameter_file:
            parameters = data_structure.Parameters(parameter_file.read())
        parameters_solver = parameters['solver_wrappers'][0]

        # "global" definitions
        displacement = vars(data_structure)['DISPLACEMENT']

        # setup case
        dir_tmp = os.path.realpath(os.path.dirname(__file__))
        p = subprocess.Popen(os.path.join(dir_tmp, 'setup_tube_flow.sh'), cwd=dir_tmp, shell=True)
        p.wait()

        def get_dy(x):
            return 0.0001 * np.sin(2 * np.pi / 0.05 * x)

        # test if same coordinates always give same pressure
        if True:
            # create solver
            solver_1 = CreateInstance(parameters_solver)
            solver_2 = CreateInstance(parameters_solver)
            solvers = [solver_1, solver_2]
            for solver in solvers:
                solver.Initialize()
                solver.InitializeSolutionStep()

            # change solver_1 to end position and solve
            mp = solver_1.model['wall']
            for node in mp.Nodes:
                node.SetSolutionStepValue(displacement, 0, [0., get_dy(node.X0), 0.])
            output1_end = solver_1.SolveSolutionStep(solver_1.GetInterfaceInput()).deepcopy()

            # change solver_2 to intermediate position and solve
            for node in mp.Nodes:
                node.SetSolutionStepValue(displacement, 0, [0., -get_dy(node.X0), 0.])
            solver_2.SolveSolutionStep(solver_2.GetInterfaceInput()).deepcopy()

            # change solver_2 to end position and solve
            for node in mp.Nodes:
                node.SetSolutionStepValue(displacement, 0, [0., get_dy(node.X0), 0.])
            output2_end = solver_2.SolveSolutionStep(solver_2.GetInterfaceInput()).deepcopy()

            for solver in solvers:
                solver.FinalizeSolutionStep()
                solver.Finalize()

            # compare
            a1 = output1_end.GetNumpyArray()
            a2 = output2_end.GetNumpyArray()

            self.assertArrayAlmostEqual(a1, a2, delta=1e-12)


if __name__ == '__main__':
    KratosUnittest.main()
