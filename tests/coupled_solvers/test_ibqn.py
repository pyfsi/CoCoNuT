from coconut import data_structure
import unittest
from coconut.coupling_components.tools import create_instance
import numpy as np


class TestCoupledSolverIBQN(unittest.TestCase):

    def assertArrayAlmostEqual(self, a1, a2):
        ls1 = list(a1)
        ls2 = list(a2)
        try:
            self.assertEqual(ls1, ls2)
        except AssertionError:
            for i in range(len(ls1)):
                self.assertAlmostEqual(ls1[i], ls2[i])

    def assertArrayEqual(self, a1, a2):
        self.assertEqual(list(a1), list(a2))

    def test_coupled_solver_ibqn(self):
        parameter_file_name = "coupled_solvers/test_ibqn.json"
        with open(parameter_file_name, 'r') as parameter_file:
            settings = data_structure.Parameters(parameter_file.read())

        coupled_solver = create_instance(settings)
        coupled_solver.initialize()
        coupled_solver.check()

        coupled_solver.initialize_solution_step()
        coupled_solver.solve_solution_step()
        sol_x = [0.00000e+00, 3.09851e-07, 0.00000e+00, 0.00000e+00,
                 3.00094e-07, 0.00000e+00, 0.00000e+00, 2.90572e-07,
                 0.00000e+00, 0.00000e+00, 2.81238e-07, 0.00000e+00,
                 0.00000e+00, 2.72094e-07, 0.00000e+00, 0.00000e+00,
                 2.63131e-07, 0.00000e+00, 0.00000e+00, 2.54343e-07,
                 0.00000e+00, 0.00000e+00, 2.45726e-07, 0.00000e+00,
                 0.00000e+00, 2.37273e-07, 0.00000e+00, 0.00000e+00,
                 2.28979e-07, 0.00000e+00]
        np.testing.assert_allclose(coupled_solver.x.GetNumpyArray(), sol_x, rtol=1e-5)

        coupled_solver.finalize_solution_step()
        coupled_solver.output_solution_step()

        coupled_solver.finalize()

if __name__ == '__main__':
    unittest.main()
