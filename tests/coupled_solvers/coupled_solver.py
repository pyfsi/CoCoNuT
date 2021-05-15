from coconut.tools import create_instance, cd

import unittest
import os
import json
import numpy as np
import shutil
import pickle


class TestCoupledSolver(unittest.TestCase):
    parameter_file_name = None

    def setUp(self):
        dir_name = os.path.realpath(os.path.dirname(__file__))  # path to coupled_solvers directory

        # read settings
        parameter_file_name = os.path.join(dir_name, 'coupled_solver.json')
        with open(parameter_file_name, 'r') as parameter_file:
            self.parameters = json.load(parameter_file)
        parameter_file_name = os.path.join(dir_name, self.parameter_file_name)
        with open(parameter_file_name, 'r') as parameter_file:
            coupled_solver_parameters = json.load(parameter_file)
        self.parameters['type'] = coupled_solver_parameters['type']
        self.parameters['settings'].update(coupled_solver_parameters['settings'])

        # set working directories
        self.working_dir = os.path.join(dir_name, 'coupled_solver_tmp')
        working_dir_cfd = os.path.join(self.working_dir, 'CFD')
        working_dir_csm = os.path.join(self.working_dir, 'CSM')
        self.parameters['solver_wrappers'][0]['settings']['working_directory'] = os.path.relpath(working_dir_cfd,
                                                                                                 start=self.working_dir)
        self.parameters['solver_wrappers'][1]['settings']['working_directory'] = os.path.relpath(working_dir_csm,
                                                                                                 start=self.working_dir)

        # setup
        shutil.rmtree(os.path.join(dir_name, self.working_dir), ignore_errors=True)
        os.mkdir(self.working_dir)
        os.mkdir(working_dir_cfd)
        os.mkdir(working_dir_csm)
        shutil.copy(os.path.join(dir_name, 'setup_tube_flow/solver_parameters.json'), working_dir_cfd)
        shutil.copy(os.path.join(dir_name, 'setup_tube_structure/solver_parameters.json'), working_dir_csm)

    def test_coupled_solver(self):
        with cd(self.working_dir):
            coupled_solver = create_instance(self.parameters)
            coupled_solver.initialize()

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
            # TODO: The reference solution has to be modified. Future work: mock solver
            np.testing.assert_allclose(coupled_solver.x.get_interface_data(), sol_x, rtol=1e-5)

            coupled_solver.finalize_solution_step()
            coupled_solver.output_solution_step()

            coupled_solver.finalize()

    def test_restart(self):
        # test if restart option works correctly

        with cd(self.working_dir):
            # adapt parameters, create coupled solver without restart
            self.parameters['settings']['save_results'] = 4
            self.parameters['settings']['case_name'] = 'no_restart'
            coupled_solver = create_instance(self.parameters)
            coupled_solver.initialize()

            # run solver for 4 time steps
            for i in range(4):
                coupled_solver.initialize_solution_step()
                coupled_solver.solve_solution_step()
                coupled_solver.finalize_solution_step()
                coupled_solver.output_solution_step()
            coupled_solver.finalize()

            # get results for solver without restart
            with open(os.path.join(self.working_dir, 'no_restart_results.pickle'), 'rb') as file:
                results_no_restart = pickle.load(file)

            # adapt parameters, create coupled solver for restart
            self.parameters['settings']['save_restart'] = 2
            self.parameters['settings']['save_results'] = 2
            self.parameters['settings']['case_name'] = 'restart'
            coupled_solver = create_instance(self.parameters)
            coupled_solver.initialize()

            # run solver for 2 time steps
            for i in range(2):
                coupled_solver.initialize_solution_step()
                coupled_solver.solve_solution_step()
                coupled_solver.finalize_solution_step()
                coupled_solver.output_solution_step()
            coupled_solver.finalize()

            # adapt parameters, create coupled solver which restarts
            self.parameters['settings']['timestep_start'] = 2
            self.parameters['settings']['save_results'] = 2
            self.parameters['settings']['case_name'] = 'restart'
            coupled_solver = create_instance(self.parameters)
            coupled_solver.initialize()

            # run solver for 2 more time steps
            for i in range(2):
                coupled_solver.initialize_solution_step()
                coupled_solver.solve_solution_step()
                coupled_solver.finalize_solution_step()
                coupled_solver.output_solution_step()
            coupled_solver.finalize()

            # get results for solver without restart
            with open(os.path.join(self.working_dir, 'restart_results.pickle'), 'rb') as file:
                results_restart = pickle.load(file)

        # remove non equal items
        for results in (results_no_restart, results_restart):
            for key in ['info', 'run_time', 'case_name']:
                results.pop(key)

        # check equality
        np.testing.assert_array_equal(results_no_restart.pop('solution_x'), results_restart.pop('solution_x'))
        np.testing.assert_array_equal(results_no_restart.pop('solution_y'), results_restart.pop('solution_y'))
        self.assertEqual(results_no_restart, results_restart)

    def tearDown(self):
        shutil.rmtree(self.working_dir)


if __name__ == '__main__':
    unittest.main()
