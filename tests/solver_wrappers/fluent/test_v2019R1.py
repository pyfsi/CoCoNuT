from coconut import data_structure
from coconut.data_structure import tools
import unittest
from coconut.coupling_components.tools import CreateInstance

import numpy as np
from copy import deepcopy
import multiprocessing
import os
import subprocess


def print_box(text):
    n = len(text)
    top = '\n┌─' + n * '─' + '─┐'
    mid = '\n│ ' + text + ' │'
    bottom = '\n└─' + n * '─' + '─┘'
    tools.print_info(top + mid + bottom)


class TestSolverWrapperFluent2019R1(unittest.TestCase):
    """
    Only 1 Fluent version can be tested at a time,
    because the correct software version must be
    preloaded.
    """

    version = '2019R1'

    def test_solver_wrapper_fluent_2019R1(self):
        self.test_solver_wrapper_fluent_2019R1_tube2d()
        self.test_solver_wrapper_fluent_2019R1_tube3d()

    def test_solver_wrapper_fluent_2019R1_tube2d(self):
        print_box('started tests for Fluent Tube2D')

        tmp = os.path.join(os.path.dirname(__file__),
                                           f'test_v{self.version}/tube2d',
                                           'test_solver_wrapper.json')
        tools.print_info(f'\ncorrect path? \n{tmp}\n')

        parameter_file_name = os.path.join(os.path.dirname(__file__),
                                           f'test_v{self.version}/tube2d',
                                           'test_solver_wrapper.json')

        with open(parameter_file_name, 'r') as parameter_file:
            parameters = data_structure.Parameters(parameter_file.read())
        par_solver_0 = parameters['solver_wrappers'][0]

        # if running from this folder
        if os.getcwd() == os.path.realpath(os.path.dirname(__file__)):
            par_solver_0['settings'].SetString('working_directory',
                                               f'test_v{self.version}/tube2d/CFD')

        # "global" definitions
        displacement = vars(data_structure)['DISPLACEMENT']
        def get_dy(x):
            return 0.0001 * np.sin(2 * np.pi / 0.05 * x)

        # setup Fluent case
        if True:
            print_box('setup Fluent case')
            dir_tmp = os.path.join(os.path.realpath(os.path.dirname(__file__)),
                                   f'test_v{self.version}/tube2d')
            tools.print_info(f'dir_tmp = {dir_tmp}')
            p = subprocess.Popen(os.path.join(dir_tmp, 'setup_fluent.sh'), cwd=dir_tmp, shell=True)
            p.wait()

        # test if nodes are moved to the correct position
        if True:
            print_box('test if nodes are moved to the correct position')

            # adapt Parameters, create solver
            par_solver = deepcopy(par_solver_0)
            par_solver['settings'].SetInt('flow_iterations', 1)
            solver = CreateInstance(par_solver)

            # give value to DISPLACEMENT variable
            mp = solver.model['beamoutside_nodes']
            for node in mp.Nodes:
                node.SetSolutionStepValue(displacement, 0, [0., get_dy(node.X0), 0.])
            mp0 = solver.GetInterfaceInput().deepcopy().model['beamoutside_nodes']

            # update position by iterating once in solver
            solver.initialize()
            solver.initialize_solution_step()
            solver.solve_solution_step(solver.GetInterfaceInput())
            solver.finalize_solution_step()
            solver.finalize()

            # create solver to check new coordinates
            par_solver['settings'].SetInt('timestep_start', 1)
            solver = CreateInstance(par_solver)
            solver.initialize()
            solver.finalize()

            # check if correct displacement was given
            mp = solver.model['beamoutside_nodes']
            for node0, node in zip(mp0.Nodes, mp.Nodes):
                y_goal = node.Y0 + node0.GetSolutionStepValue(displacement)[1]
                self.assertAlmostEqual(node.Y, y_goal, delta=1e-16)

        # test if different partitioning gives the same ModelParts
        if True:
            print_box('test if different partitioning gives the same ModelParts')

            # create two solvers with different flow solver partitioning
            par_solver = deepcopy(par_solver_0)
            model_parts = []
            for cores in [1, multiprocessing.cpu_count()]:
                par_solver['settings'].SetInt('cores', cores)
                solver = CreateInstance(par_solver)
                solver.initialize()
                solver.finalize()
                model_parts.append(deepcopy(solver.model['beamoutside_nodes']))

            # compare Nodes in ModelParts between both solvers
            mp1, mp2 = model_parts
            for node1 in mp1.Nodes:
                node2 = mp2.GetNode(node1.Id)
                self.assertEqual(node1.X, node2.X)
                self.assertEqual(node1.Y, node2.Y)
                self.assertEqual(node1.Z, node2.Z)

        # test if same coordinates always give same pressure & traction
        if True:
            print_box('test if same coordinates always gives same pressure & traction')

            # adapt Parameters, create solver
            par_solver = deepcopy(par_solver_0)
            par_solver['settings'].SetInt('cores', multiprocessing.cpu_count())
            par_solver['settings'].SetInt('flow_iterations', 500)
            solver = CreateInstance(par_solver)
            solver.initialize()
            solver.initialize_solution_step()

            # change grid to position 1
            mp = solver.model['beamoutside_nodes']
            for node in mp.Nodes:
                node.SetSolutionStepValue(displacement, 0, [0., get_dy(node.X0), 0.])
            output1 = solver.solve_solution_step(solver.GetInterfaceInput()).deepcopy()

            # change grid to position 2
            for node in mp.Nodes:
                node.SetSolutionStepValue(displacement, 0, [0., -get_dy(node.X0), 0.])
            output2 = solver.solve_solution_step(solver.GetInterfaceInput()).deepcopy()

            # change grid back to position 1
            for node in mp.Nodes:
                node.SetSolutionStepValue(displacement, 0, [0., get_dy(node.X0), 0.])
            output3 = solver.solve_solution_step(solver.GetInterfaceInput()).deepcopy()

            solver.finalize_solution_step()
            solver.finalize()

            # normalize data and compare
            a1 = output1.GetNumpyArray()
            a2 = output2.GetNumpyArray()
            a3 = output3.GetNumpyArray()

            mean = np.mean(a1)
            ref = np.abs(a1 - mean).max()

            a1n = (a1 - mean) / ref
            a2n = (a2 - mean) / ref
            a3n = (a3 - mean) / ref

            self.assertNotAlmostEqual(np.sum(np.abs(a1n - a2n)) / a1n.size, 0., delta=1e-12)
            for i in range(a1.size):
                self.assertAlmostEqual(a1n[i] - a3n[i], 0., delta=1e-12)

        # test if restart option works correctly
        if True:
            print_box('test if restart option works correctly')

            # adapt Parameters, create solver
            par_solver = deepcopy(par_solver_0)
            par_solver['settings'].SetInt('cores', 1)
            par_solver['settings'].SetInt('flow_iterations', 30)
            solver = CreateInstance(par_solver)

            # run solver for 4 timesteps
            solver.initialize()
            for i in range(4):
                mp = solver.model['beamoutside_nodes']
                for node in mp.Nodes:
                    node.SetSolutionStepValue(displacement, 0, [0., i * get_dy(node.X0), 0.])
                solver.initialize_solution_step()
                solver.solve_solution_step(solver.GetInterfaceInput())
                solver.finalize_solution_step()
            solver.finalize()

            # get data for solver without restart
            interface1 = solver.GetInterfaceOutput().deepcopy()
            data1 = interface1.GetNumpyArray().copy()

            # create solver which restarts at timestep 2
            par_solver['settings'].SetInt('timestep_start', 2)
            solver = CreateInstance(par_solver)

            # run solver for 2 more timesteps
            solver.initialize()
            for i in range(2, 4):
                mp = solver.model['beamoutside_nodes']
                for node in mp.Nodes:
                    node.SetSolutionStepValue(displacement, 0, [0., i * get_dy(node.X0), 0.])
                solver.initialize_solution_step()
                solver.solve_solution_step(solver.GetInterfaceInput())
                solver.finalize_solution_step()
            solver.finalize()

            # get data for solver with restart
            interface2 = solver.GetInterfaceOutput().deepcopy()
            data2 = interface2.GetNumpyArray().copy()

            # compare coordinates of Nodes
            mp1 = interface1.model['beamoutside_nodes']
            mp2 = interface2.model['beamoutside_nodes']
            for node1, node2 in zip(mp1.Nodes, mp2.Nodes):
                self.assertAlmostEqual(node1.X, node2.X, delta=1e-16)
                self.assertAlmostEqual(node1.Y, node2.Y, delta=1e-16)
                self.assertAlmostEqual(node1.Z, node2.Z, delta=1e-16)

            # normalize pressure and traction data and compare
            mean = np.mean(data1)
            ref = np.abs(data1 - mean).max()

            data1n = (data1 - mean) / ref
            data2n = (data2 - mean) / ref

            for i in range(data1n.size):
                self.assertAlmostEqual(data1n[i] - data2n[i], 0., delta=1e-14)

        print_box('finished tests for Fluent Tube2D')

    def test_solver_wrapper_fluent_2019R1_tube3d(self):
        print_box('started tests for Fluent Tube3D')

        parameter_file_name = os.path.join(os.path.dirname(__file__),
                                           f'test_v{self.version}/tube3d',
                                           'test_solver_wrapper.json')

        with open(parameter_file_name, 'r') as parameter_file:
            parameters = data_structure.Parameters(parameter_file.read())
        par_solver_0 = parameters['solver_wrappers'][0]

        # if running from this folder
        if os.getcwd() == os.path.realpath(os.path.dirname(__file__)):
            par_solver_0['settings'].SetString('working_directory',
                                               f'test_v{self.version}/tube3d/CFD')

        # "global" definitions
        displacement = vars(data_structure)['DISPLACEMENT']
        def get_dy_dz(x, y, z):
            dr = 0.0001 * np.sin(2 * np.pi / 0.05 * x)
            theta = np.arctan2(z, y)
            dy = dr * np.cos(theta)
            dz = dr * np.sin(theta)
            return dy, dz

        # setup Fluent case
        if True:
            print_box('setup Fluent case')

            dir_tmp = os.path.join(os.path.realpath(os.path.dirname(__file__)),
                                   f'test_v{self.version}/tube3d')
            p = subprocess.Popen(os.path.join(dir_tmp, 'setup_fluent.sh'), cwd=dir_tmp, shell=True)
            p.wait()

        # test if nodes are moved to the correct position
        if True:
            print_box('test if nodes are moved to the correct position')

            # adapt Parameters, create solver
            par_solver = deepcopy(par_solver_0)
            par_solver['settings'].SetInt('flow_iterations', 1)
            solver = CreateInstance(par_solver)

            # give value to DISPLACEMENT variable
            mp = solver.model['wall_nodes']
            for node in mp.Nodes:
                dy, dz = get_dy_dz(node.X0, node.Y0, node.Z0)
                node.SetSolutionStepValue(displacement, 0, [0., dy, dz])
            mp0 = solver.GetInterfaceInput().deepcopy().model['wall_nodes']

            # update position by iterating once in solver
            solver.initialize()
            solver.initialize_solution_step()
            solver.solve_solution_step(solver.GetInterfaceInput())
            solver.finalize_solution_step()
            solver.finalize()

            # create solver to check new coordinates
            par_solver['settings'].SetInt('timestep_start', 1)
            solver = CreateInstance(par_solver)
            solver.initialize()
            solver.finalize()

            # check if correct displacement was given
            mp = solver.model['wall_nodes']
            for node0, node in zip(mp0.Nodes, mp.Nodes):
                disp = node0.GetSolutionStepValue(displacement)
                y_goal = node0.Y0 + disp[1]
                z_goal = node0.Z0 + disp[2]
                self.assertAlmostEqual(node.Y, y_goal, delta=1e-16)
                self.assertAlmostEqual(node.Z, z_goal, delta=1e-16)

        # test if different partitioning gives the same ModelParts
        if True:
            print_box('test if different partitioning gives the same ModelParts')

            # create two solvers with different flow solver partitioning
            par_solver = deepcopy(par_solver_0)
            model_parts = []
            for cores in [1, multiprocessing.cpu_count()]:
                par_solver['settings'].SetInt('cores', cores)
                solver = CreateInstance(par_solver)
                solver.initialize()
                solver.finalize()
                model_parts.append(deepcopy(solver.model['wall_nodes']))

            # compare Nodes in ModelParts between both solvers
            mp1, mp2 = model_parts
            for node1, node2 in zip(mp1.Nodes, mp2.Nodes):
                self.assertEqual(node1.X, node2.X)
                self.assertEqual(node1.Y, node2.Y)
                self.assertEqual(node1.Z, node2.Z)

        # test if same coordinates always give same pressure & traction
        if True:
            print_box('test if same coordinates always gives same pressure & traction')

            # adapt Parameters, create solver
            par_solver = deepcopy(par_solver_0)
            par_solver['settings'].SetInt('cores', multiprocessing.cpu_count())
            par_solver['settings'].SetInt('flow_iterations', 500)
            solver = CreateInstance(par_solver)
            solver.initialize()
            solver.initialize_solution_step()

            # change grid to position 1
            mp = solver.model['wall_nodes']
            for node in mp.Nodes:
                dy, dz = get_dy_dz(node.X0, node.Y0, node.Z0)
                node.SetSolutionStepValue(displacement, 0, [0., dy, dz])
            output1 = solver.solve_solution_step(solver.GetInterfaceInput()).deepcopy()

            # change grid to position 2
            for node in mp.Nodes:
                dy, dz = get_dy_dz(node.X0, node.Y0, node.Z0)
                node.SetSolutionStepValue(displacement, 0, [0., -dy, -dz])
            output2 = solver.solve_solution_step(solver.GetInterfaceInput()).deepcopy()

            # change grid back to position 1
            for node in mp.Nodes:
                dy, dz = get_dy_dz(node.X0, node.Y0, node.Z0)
                node.SetSolutionStepValue(displacement, 0, [0., dy, dz])
            output3 = solver.solve_solution_step(solver.GetInterfaceInput()).deepcopy()

            solver.finalize_solution_step()
            solver.finalize()

            # normalize data and compare
            a1 = output1.GetNumpyArray()
            a2 = output2.GetNumpyArray()
            a3 = output3.GetNumpyArray()

            mean = np.mean(a1)
            ref = np.abs(a1 - mean).max()

            a1n = (a1 - mean) / ref
            a2n = (a2 - mean) / ref
            a3n = (a3 - mean) / ref

            self.assertNotAlmostEqual(np.sum(np.abs(a1n - a2n)) / a1n.size, 0., delta=1e-12)
            for i in range(a1.size):
                self.assertAlmostEqual(a1n[i] - a3n[i], 0., delta=1e-12)

        # test if restart option works correctly
        if True:
            print_box('test if restart option works correctly')

            # adapt Parameters, create solver
            par_solver = deepcopy(par_solver_0)
            par_solver['settings'].SetInt('cores', 1)
            par_solver['settings'].SetInt('flow_iterations', 30)
            solver = CreateInstance(par_solver)

            # run solver for 4 timesteps
            solver.initialize()
            for i in range(4):
                mp = solver.model['wall_nodes']
                for node in mp.Nodes:
                    dy, dz = get_dy_dz(node.X0, node.Y0, node.Z0)
                    node.SetSolutionStepValue(displacement, 0, [0., i * dy, i * dz])
                solver.initialize_solution_step()
                solver.solve_solution_step(solver.GetInterfaceInput())
                solver.finalize_solution_step()
            solver.finalize()

            # get data for solver without restart
            interface1 = solver.GetInterfaceOutput().deepcopy()
            data1 = interface1.GetNumpyArray().copy()

            # create solver which restarts at timestep 2
            par_solver['settings'].SetInt('timestep_start', 2)
            solver = CreateInstance(par_solver)

            # run solver for 2 more timesteps
            solver.initialize()
            for i in range(2, 4):
                mp = solver.model['wall_nodes']
                for node in mp.Nodes:
                    dy, dz = get_dy_dz(node.X0, node.Y0, node.Z0)
                    node.SetSolutionStepValue(displacement, 0, [0., i * dy, i * dz])
                solver.initialize_solution_step()
                solver.solve_solution_step(solver.GetInterfaceInput())
                solver.finalize_solution_step()
            solver.finalize()

            # get data for solver with restart
            interface2 = solver.GetInterfaceOutput().deepcopy()
            data2 = interface2.GetNumpyArray().copy()

            # compare coordinates of Nodes
            mp1 = interface1.model['wall_nodes']
            mp2 = interface2.model['wall_nodes']
            for node1, node2 in zip(mp1.Nodes, mp2.Nodes):
                self.assertAlmostEqual(node1.X, node2.X, delta=1e-16)
                self.assertAlmostEqual(node1.Y, node2.Y, delta=1e-16)
                self.assertAlmostEqual(node1.Z, node2.Z, delta=1e-16)

            # normalize pressure and traction data and compare
            mean = np.mean(data1)
            ref = np.abs(data1 - mean).max()

            data1n = (data1 - mean) / ref
            data2n = (data2 - mean) / ref

            print(f'max rel error: {np.abs(data1n - data2n).max()}')

            for i in range(data1n.size):
                self.assertAlmostEqual(data1n[i] - data2n[i], 0., delta=1e-14)

        print_box('finished tests for Fluent Tube3D')


if __name__ == '__main__':
    unittest.main()
