from coconut.tools import create_instance
from coconut.coupling_components.component import Component
from coconut.coupling_components import tools
from coconut import data_structure
import numpy as np

""" proposed changes to mapped.py
- do initialization of mappers in Initialize method, would be more logical
- remove all set_interface_input/Output methods?
- use copy in get_interface_input/Output methods?
    and just refer to actual solver wrapper in SolverWrapperMapped
- all Interfaces are stored in this mapper, e.g. self.interface_output_to and 3 others;
    I see no reason for this; furthermore, it is only useful to store it if you take copies all the time
- output_solution_step is barely used; what's the deal with it??
"""


def create(parameters):
    return SolverWrapperMapped(parameters)


class SolverWrapperMapped(Component):
    def __init__(self, parameters):
        super().__init__()

        # Read parameters
        self.parameters = parameters
        self.settings = parameters["settings"]

        # Create solver
        self.solver_wrapper = create_instance(self.settings["solver_wrapper"])

        # run time
        self.run_time = 0.0

        #model

        self.model = data_structure.Model()

    def initialize(self):
        super().initialize()

        self.solver_wrapper.initialize()

    def initialize_solution_step(self):
        super().initialize_solution_step()

        self.solver_wrapper.initialize_solution_step()

        print("initialize iteration")
        self.iteration = 0
        print(self.iteration)

        self.myArrays = {}
        self.myArrays[self.iteration] = np.zeros((100,3))


    @tools.time_solve_solution_step
    def solve_solution_step(self, interface_input_from):

        self.iteration +=1
        print("iteration")
        print(self.iteration)
        # self.parameters2 =  {'model_part': 'mp_intermediate' + str(self.iteration), 'variables': ['displacement']},

        self.interface_input_from = interface_input_from
        for item_input_from in self.interface_input_from.parameters:
            print("item_input_from")
            print(item_input_from)
            mp_input_from = self.interface_input_from.get_model_part(item_input_from['model_part'])
            print(mp_input_from)
            print(item_input_from['variables'])
            print(item_input_from['variables'][0])
            print(item_input_from['model_part'])
            print(mp_input_from.x0.size)
            varia1 = self.interface_input_from.get_variable_data(item_input_from['model_part'], item_input_from['variables'][0])

        for item_input_to in self.interface_input_to.parameters:
            mp_input_to = self.interface_input_to.get_model_part(item_input_to['model_part'])
            print("mp_input-to")
            print(mp_input_to)
            print(mp_input_to.x0.size)
        #
        #     self.model.create_model_part('intermediate_mp' + str(self.iteration), mp_input_to.x0, mp_input_to.y0, mp_input_to.z0,
        #                                  np.arange(mp_input_to.x0.size))
        #     parameters = [{'model_part': 'intermediate_mp'+str(self.iteration), 'variables': ['displacement']}]
        #     self.interface_intermediate = data_structure.Interface(parameters, self.model)
        #     self.interface_intermediate.set_variable_data('intermediate_mp' + str(self.iteration), 'displacement', np.zeros((mp_input_to.x0.size,3)))
        #     mp_intermediate = self.interface_intermediate.get_variable_data('intermediate_mp' + str(self.iteration), 'displacement')
        #     # print("zeros")
        #     # print(mp_intermediate)
        #     if self.iteration > 1:
        #         self.interface_output_from_intermediate = self.interface_output_from.copy()
        #         self.interface_output_from_intermediate.set_variable_data('BEAMINSIDEMOVING_nodes', 'displacement', self.myArrays[self.iteration - 1])
        #         check = self.interface_output_from_intermediate.get_variable_data('BEAMINSIDEMOVING_nodes', 'displacement')
        #
        #     varia1 = self.interface_input_to.get_variable_data(item_input_to['model_part'],
        #                                                        item_input_to['variables'][1])

        self.mapper_interface_input(self.interface_input_from, self.interface_input_to)

        self.interface_output_from = self.solver_wrapper.solve_solution_step(self.interface_input_to)
        for item_output_from in self.interface_output_from.parameters:
            # print("item_output_from")
            # print(item_output_from)
            mp_output_from = self.interface_output_from.get_model_part(item_output_from['model_part'])
            # print(mp_output_from)
            # print(item_output_from['variables'])

            x = mp_output_from.x0
            y = mp_output_from.y0

            self.varia = self.interface_output_from.get_variable_data(item_output_from['model_part'], item_output_from['variables'][0])
            # print('currentOne')
            # print(self.varia)
            self.myArrays[self.iteration] = self.varia
            # self.varia[:,0] = np.add(self.varia[:,0], x)
            # self.varia[:,1] = np.add(self.varia[:,1], y)

        self.mapper_interface_output(self.interface_output_from, self.interface_output_to)
        for item_output_to in self.interface_output_to.parameters:
            print("item_output_to")
            print(item_output_to)
            mp_output_to = self.interface_output_to.get_model_part(item_output_to['model_part'])
            print(mp_output_to)
            # print(item_output_to['variables'])
            self.varia2 = self.interface_output_from.get_variable_data(item_output_from['model_part'], item_output_from['variables'][0])
            # print(self.varia2)
        return self.interface_output_to

    def finalize_solution_step(self):
        super().finalize_solution_step()

        self.solver_wrapper.finalize_solution_step()

    def finalize(self):
        super().finalize()

        self.solver_wrapper.finalize()
        self.mapper_interface_input.finalize()
        self.mapper_interface_output.finalize()

    def output_solution_step(self):
        super().output_solution_step()

        self.solver_wrapper.output_solution_step()
        self.mapper_interface_input.output_solution_step()
        self.mapper_interface_output.output_solution_step()

    def get_interface_input(self):
        # Does not contain most recent data
        # *** shouldn't this just call the underlying solver wrapper?
        return self.interface_input_from

    def set_interface_input(self,interface_input_from):
        # Create input mapper
        self.interface_input_from = interface_input_from.copy()
        print('intermediate interface_input_from')
        print(interface_input_from)
        self.interface_input_to = self.solver_wrapper.get_interface_input()
        print('intermediate interface input to')
        print(self.interface_input_to)

        self.mapper_interface_input = create_instance(self.settings["mapper_interface_input"])
        self.mapper_interface_input.initialize(self.interface_input_from, self.interface_input_to)

    def get_interface_output(self):
        self.interface_output_from = self.solver_wrapper.get_interface_output()
        self.mapper_interface_output(self.interface_output_from, self.interface_output_to)
        return self.interface_output_to.copy()

    def set_interface_output(self, interface_output_to):
        # Create output mapper
        self.interface_output_to = interface_output_to.copy()
        self.interface_output_from = self.solver_wrapper.get_interface_output()

        self.mapper_interface_output = create_instance(self.settings["mapper_interface_output"])
        self.mapper_interface_output.initialize(self.interface_output_from, self.interface_output_to)

    def print_components_info(self, pre):
        tools.print_info(pre, "The component ", self.__class__.__name__, " maps the following solver wrapper:")
        pre = tools.update_pre(pre)
        self.solver_wrapper.print_components_info(pre + '├─')
        tools.print_info(pre, '├─', "Input mapper:")
        self.mapper_interface_input.print_components_info(pre + '│ └─')
        tools.print_info(pre, '└─', "Output mapper:")
        self.mapper_interface_output.print_components_info(pre + '  └─')
