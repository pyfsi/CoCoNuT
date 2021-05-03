from coconut import data_structure
from coconut import tools
from coconut.coupling_components.component import Component
from coconut.coupling_components.coupled_solvers.gauss_seidel import CoupledSolverGaussSeidel

import time
import os
import numpy as np


def create(parameters):
    return CoupledSolverTestSingleSolver(parameters)


class CoupledSolverTestSingleSolver(CoupledSolverGaussSeidel):

    def __init__(self, parameters):
        """"Should only initialize the solver that is to be tested"""
        Component.__init__(self)

        self.parameters = parameters
        self.settings = parameters.get("settings", {})  # settings is optional as long as the necessary parameters...
        # ... are in test_settings

        if "test_settings" not in self.parameters.keys():  # requires a new parameter input "test_settings"
            raise KeyError('The coupled_solver "test_single_solver" requires "test_settings" which was not detected.')
        test_settings = parameters["test_settings"]
        self.settings.update(test_settings)  # update settings with test_settings (test_settings are prioritized)

        # read parameters
        self.solver_index = self.settings["solver_index"]  # solver to be tested; starts at 0
        self.test_class = self.settings.get("test_class")
        self.timestep_start_current = self.timestep_start_global = self.settings.get("timestep_start", 0)
        self.restart = False  # no restart allowed
        self.delta_t = self.settings["delta_t"]
        tools.print_info(f"Using delta_t = {self.delta_t} and timestep_start = {self.timestep_start_current}")

        # create dummy components
        self.predictor = DummyComponent()
        self.convergence_criterion = DummyComponent()

        # solver wrapper settings
        parameters = self.parameters["solver_wrappers"][self.solver_index]
        if parameters["type"] == "solver_wrappers.mapped":
            parameters = parameters["settings"]["solver_wrapper"]  # for mapped solver: the solver_wrapper itself tested
        settings = parameters["settings"]

        orig_wd = settings["working_directory"]  # working directory changed to a test_working_directory
        i = 0
        while os.path.exists(f"{orig_wd}_test{i}"):
            i += 1
        cur_wd = f"{orig_wd}_test{i}"
        settings["working_directory"] = cur_wd
        os.system(f"cp -r {orig_wd} {cur_wd}")
        tools.print_info(f"{cur_wd} is the working_directory for the test\nCopying {orig_wd} to {cur_wd} \n")

        # add delta_t and timestep_start to solver_wrapper settings
        tools.pass_on_parameters(self.settings, parameters["settings"], ["timestep_start", "delta_t"])

        self.solver_wrapper = tools.create_instance(parameters)
        self.solver_wrappers = [self.solver_wrapper]  # used for printing summary

        self.components = [self.solver_wrapper]  # will only contain 1 solver wrapper

        # initialize test_class
        interface_input = self.solver_wrapper.interface_input
        if self.test_class is None:
            self.dummy_solver = None
            tools.print_info("No test class specified, zero input will be used")
            for model_part_name, variable in interface_input.model_part_variable_pairs:
                if data_structure.variables_dimensions[variable] == 1:
                    tools.print_info(f"\t0 is used as {variable} input to {model_part_name}")
                elif data_structure.variables_dimensions[variable] == 3:
                    tools.print_info(f"\t[0 0 0] is used as {variable} input to {model_part_name}")
        else:
            if not os.path.isfile('dummy_solver.py'):
                raise ModuleNotFoundError(f"Test class specified, but no file named dummy_solver.py in {os.getcwd()}")
            module = __import__('dummy_solver')
            if not hasattr(module, self.test_class):
                raise NameError(f"Module dummy_solver has no class {self.test_class}")
            self.dummy_solver = getattr(module, self.test_class)()
            tools.print_info(f"The functions from {self.test_class} will be used to calculate the following inputs:")
            for model_part_name, variable in interface_input.model_part_variable_pairs:
                if data_structure.variables_dimensions[variable] == 1:
                    tools.print_info(f"\t{variable} [Scalar] on {model_part_name}")
                elif data_structure.variables_dimensions[variable] == 3:
                    tools.print_info(f"\t{variable} [3D array] on {model_part_name}")
        tools.print_info()

        self.x = None
        self.y = None
        self.time_step = self.timestep_start_current
        self.iteration = None  # iteration
        self.solver_level = 0  # 0 is main solver (time step is printed)
        self.start_time = None
        self.run_time = None
        self.run_time_previous = 0
        self.iterations = []

        # no restart files are saved
        self.save_restart = 0

        # save results variables
        self.save_results = self.settings.get("save_results", False)
        if self.save_results:
            self.complete_solution_x = None
            self.complete_solution_y = None
            self.residual = []
            self.info = None
            self.case_name = self.settings.get("case_name", "case")  # case name
            self.case_name += "_" + cur_wd

        self.debug = False

    def initialize(self):
        Component.initialize(self)

        self.solver_wrapper.initialize()

        # initialize variables
        if self.solver_index == 1:
            self.x = self.solver_wrapper.get_interface_output()
            self.y = self.solver_wrapper.get_interface_input()
        else:
            self.x = self.solver_wrapper.get_interface_input()
            self.y = self.solver_wrapper.get_interface_output()

        if self.save_results:
            self.complete_solution_x = self.x.get_interface_data().reshape(-1, 1)
            self.complete_solution_y = self.y.get_interface_data().reshape(-1, 1)
        self.start_time = time.time()

    def solve_solution_step(self):
        interface_input = self.solver_wrapper.interface_input
        # generation of the input data
        if self.dummy_solver is not None:
            for model_part_name, variable in interface_input.model_part_variable_pairs:
                model_part = interface_input.get_model_part(model_part_name)
                data = [getattr(self.dummy_solver, f"calculate_{variable}")(model_part.x0[i], model_part.y0[i],
                                                                            model_part.z0[i], self.time_step)
                        for i in range(model_part.size)]
                interface_input.set_variable_data(model_part_name, variable, np.array(data))
        # store data in self.x and self.y
        if self.solver_index == 1:
            self.y = interface_input
            self.x = self.solver_wrapper.solve_solution_step(interface_input)
        else:
            self.x = interface_input
            self.y = self.solver_wrapper.solve_solution_step(interface_input)
        self.finalize_iteration(self.x * 0)

    def print_header(self):
        if self.time_step == self.timestep_start_current + 1:
            header = f"════════════════════════════════════════════════════════════════════════════════\n" \
                f"{'Time step':<16}{'Norm x':<28}{'Norm y':<28}"
            tools.print_info(header, flush=True)

    def print_iteration_info(self, r):
        info = f"{self.time_step:<16d}{self.x.norm():<28.17e}{self.y.norm():<28.17e}"
        tools.print_info(' │' * self.solver_level, info, flush=True)


class DummyComponent:
    def update(self, x):
        pass
