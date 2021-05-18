from coconut.tools import create_instance
from coconut.coupling_components.component import Component
from coconut import tools
from coconut import data_structure
import matplotlib.pyplot as plt

import numpy as np


def create(parameters):
    return SolverWrapperMapped_update(parameters)


class SolverWrapperMapped_update(Component):
    def __init__(self, parameters):
        super().__init__()

        self.parameters = parameters
        self.settings = parameters["settings"]

        # create solver
        tools.pass_on_parameters(self.settings, self.settings["solver_wrapper"]["settings"],
                                 ["timestep_start", "delta_t"])
        self.solver_wrapper = create_instance(self.settings["solver_wrapper"])

        # create mappers
        self.mapper_interface_input = create_instance(self.settings["mapper_interface_input"])
        self.mapper_interface_output = create_instance(self.settings["mapper_interface_output"])

        self.mapper_interface_input_update_to = create_instance(self.settings["mapper_interface_input_update_to"])
        self.mapper_interface_input_update_from = create_instance(self.settings["mapper_interface_input_update_from"])

        self.interface_input_from = None
        self.interface_input_to = None
        self.interface_output_to = None

        # run time
        self.run_time = 0.0

    def initialize(self, interface_input_from, interface_output_to):
        super().initialize()

        self.solver_wrapper.initialize()

        # create input mapper
        self.interface_input_from = interface_input_from.copy()
        self.interface_input_to = self.solver_wrapper.get_interface_input()
        self.mapper_interface_input.initialize(self.interface_input_from, self.interface_input_to)

        # create output mapper
        self.interface_output_to = interface_output_to.copy()
        self.interface_output_from = self.solver_wrapper.get_interface_output()
        self.mapper_interface_output.initialize(self.interface_output_from, self.interface_output_to)

        #create mp input_update_to
        model1 = self.interface_input_to.model
        parameters1 = self.interface_input_to.parameters
        for dct in parameters1:
            dct['variables'] = ["displacement"]
        self.new_interface_input_to = data_structure.Interface(parameters1,model1)

        # for i in self.interface_input_from.parameters:
        #     tyl = self.interface_input_from.get_model_part(i['model_part'])
        #     tyl2 = self.interface_input_from.get_variable_data(i["model_part"],i['variables'][0])
        #     print("x-coord interface output from")
        #     print(tyl.x0)
        #     print("y-coord  interface output from")
        #     print(tyl.y0)
        #     print("z-coord  interface output from")
        #     print(tyl.z0)

        #create mp_input_udate_from
        model2 = self.interface_input_from.model
        parameters2 = self.interface_input_from.parameters
        for dct2 in parameters2:
            dct2['variables'] = ["displacement"]
        self.new_interface_input_from = data_structure.Interface(parameters2, model2)

        #create input_update_to mapper
        self.mapper_interface_input_update_to.initialize(self.interface_output_from, self.new_interface_input_to)


        #create input_update_from mapper
        self.mapper_interface_input_update_from.initialize(self.interface_output_to, self.new_interface_input_from)

    def initialize_solution_step(self):
        super().initialize_solution_step()

        self.solver_wrapper.initialize_solution_step()
        self.iteration = 0

    @tools.time_solve_solution_step
    def solve_solution_step(self, interface_input_from):

        self.iteration += 1

        self.interface_input_from = interface_input_from.copy()

        # Creating an updated self.interface_input_from

        # purple box 1 mapping
        self.mapper_interface_input_update_from(self.interface_output_to, self.new_interface_input_from)

        # add the mapped displacement to interface_input_from by creating a new mp
        self.model_new_from = data_structure.Model()
        for item_new_input_from in self.new_interface_input_from.parameters:
            mp_intermediate_input_from = self.new_interface_input_from.get_model_part(item_new_input_from['model_part'])
            disp_intermediate_from = self.new_interface_input_from.get_variable_data(item_new_input_from['model_part'],
                                                                               item_new_input_from['variables'][0])
            x0_new = disp_intermediate_from[:, 0] + mp_intermediate_input_from.x0
            # print("disp_intermediate_from")
            # print(disp_intermediate_from)
            y0_new = disp_intermediate_from[:, 1] + mp_intermediate_input_from.y0
            z0_new = disp_intermediate_from[:, 2] + mp_intermediate_input_from.z0
            ids_from = np.arange(0, mp_intermediate_input_from.x0.size)

            # create new mp with interface_new_to to update self.interface_input_to
            self.model_new_from.create_model_part(item_new_input_from['model_part'],
                                                x0_new, y0_new, z0_new,
                                                ids_from)

        self.interface_new_from = data_structure.Interface(interface_input_from.parameters, self.model_new_from)

        self.tmp = self.interface_input_from.get_interface_data()
        self.interface_new_from.set_interface_data(self.tmp)

        self.interface_input_from = self.interface_new_from

        # Creating an updated self.interface_input_to

        # for output_from in self.interface_output_from.parameters:
        #     output = self.interface_output_from.get_model_part(output_from['model_part'])
        #     tmp = self.interface_output_from.get_variable_data(output_from['model_part'], output_from['variables'][0])
        #     print("output.x0", self.iteration)
        #     print(output.x0)
        #     print("output.y0", self.iteration)
        #     print(output.y0)
            # print("displacement")
            # print(tmp)

        #purple box 2 mapping
        self.mapper_interface_input_update_to(self.interface_output_from, self.new_interface_input_to)

        # add the mapped displacement to interface_input_to by creating a new mp
        self.model_new_to = data_structure.Model()
        for item_new_input_to in self.new_interface_input_to.parameters:
            mp_intermediate_input_to = self.new_interface_input_to.get_model_part(item_new_input_to['model_part'])
            tmp = self.new_interface_input_to.get_variable_data(item_new_input_to['model_part'],
                                                                               item_new_input_to['variables'][0])
            x0_new_to = tmp[:, 0] + mp_intermediate_input_to.x0
            y0_new_to = tmp[:, 1] + mp_intermediate_input_to.y0
            # print("tmp", self.iteration)
            # print(tmp[:,1])
            z0_new_to = tmp[:, 2] + mp_intermediate_input_to.z0
            ids_to = np.arange(0, mp_intermediate_input_to.x0.size)

            #create new mp with interface_new_to to update self.interface_input_to
            self.model_new_to.create_model_part(item_new_input_to['model_part'],
                                                x0_new_to, y0_new_to, z0_new_to,
                                                ids_to)

        self.interface_new_to = data_structure.Interface(self.interface_input_to.parameters, self.model_new_to)


        for i in self.interface_new_to.parameters:
            tyl = self.interface_new_to.get_model_part(i['model_part'])
            tyl2 = self.interface_new_to.get_variable_data(i["model_part"],i['variables'][0])
            # print("x-coord new interface output from")
            # print(tyl.x0)
            # print("y-coord new interface output from")
            # print(tyl.y0)
            # print("z-coord new interface output from")
            # print(tyl.z0)


        # Creating an updated self.interface_input_to
        #todo 
        # self.interface_input_to = self.interface_new_to


        for i in self.interface_input_to.parameters:
            tyl = self.interface_input_to.get_model_part(i['model_part'])
            tyl2 = self.interface_input_to.get_variable_data(i["model_part"],i['variables'][0])
            # print("x-coord interface input to", self.iteration)
            # print(tyl.x0)
            # print("y-coord  interface input to before mapping", self.iteration)
            # print(tyl.y0)
            # print("z-coord  interface input to", self.iteration)
            # print(tyl.z0)

        self.mapper_interface_input = create_instance(self.settings["mapper_interface_input"])
        self.mapper_interface_input.initialize(self.interface_input_from, self.interface_input_to)

        if self.iteration ==1:
            self.mapper_interface_input.mappers["Wire_output" + '_to_' + "WALLOUTSIDE0_load_points"].mappers[1].first_iteration = True

        self.mapper_interface_input(self.interface_input_from, self.interface_input_to)

        if self.iteration ==2:
            for i in self.interface_input_to.parameters:
                mp = self.interface_input_to.get_model_part(i['model_part'])
                # print("y-coord interface input to after mapping")
                # print(mp.x0)
                # check2 = self.interface_input_to.get_variable_data(i['model_part'], i['variables'][0])
                # print('check2')
                # print(mp.y0,check2)

        self.interface_output_from = self.solver_wrapper.solve_solution_step(self.interface_input_to)

        # Creating an updated interface_output_from

        self.model_new_output_from = data_structure.Model()
        #get the point displacements of current calculation in the structural solver
        for item_output_from in self.interface_output_from.parameters:
            mp_output_from = self.interface_output_from.get_model_part(item_output_from['model_part'])
            # print("mp_output_from_y0")
            # print(mp_output_from.y0)
            varia = self.interface_output_from.get_variable_data(item_output_from['model_part'], item_output_from['variables'][0])
            x0_new_from = np.add(varia[:,0],mp_output_from.x0)
            y0_new_from = np.add(varia[:,1],mp_output_from.y0)
            # print("mp_output_from_y0" , self.iteration)
            # print(mp_output_from.y0)
                # print("mp_output_from_new_x0")
                # print(x0_new_from)
            z0_new_from = np.add(varia[:,2],mp_output_from.z0)
            ids = np.arange(0, mp_output_from.x0.size)

            #creating new mp
            self.model_new_output_from.create_model_part( item_output_from['model_part'], x0_new_from, y0_new_from, z0_new_from, ids)

        self.interface_output_from_new = data_structure.Interface(self.interface_output_from.parameters, self.model_new_output_from)

        self.tmp2 = self.interface_output_from.get_interface_data()
        self.interface_output_from_new.set_interface_data(self.tmp2)

        #store the displacements for following iteration

        # for i in self.interface_output_from.parameters:
        #     coord = self.interface_output_from.get_model_part(i['model_part'])
        #     print("output_from_x0", self.iteration)
        #     print(coord.x0)
        #     print("output_from_y0", self.iteration)
        #     print(coord.y0)

        for i in self.interface_output_from_new.parameters:
            coord = self.interface_output_from_new.get_model_part(i['model_part'])
            # print("output_from_new_x0", self.iteration)
            # # print(coord.x0)
            # print("output_from_new_y0", self.iteration)
            # print(coord.y0.size)
            # disp = self.interface_output_from_new.get_variable_data(i['model_part'], i['variables'][0])
            # y = disp[:,0]
            # print("disp")
            # print(y)
            # plt.scatter(coord.y0, y, color = 'r', label= "output_from")
            # plt.xlabel('wire position')
            # plt.ylabel('radial displacement')


        self.mapper_interface_output = create_instance(self.settings["mapper_interface_output"])
        #todo self.interface_output_to van naam veranderen
        self.mapper_interface_output.initialize(self.interface_output_from_new, self.interface_output_to)
        self.mapper_interface_output(self.interface_output_from, self.interface_output_to)
        # plt.show()


        # for item_output_to in self.interface_output_to.parameters:
        #     mp_output_to = self.interface_output_to.get_model_part(item_output_to['model_part'])
        #     print("mp_output_to_x0", self.iteration)
        #     print(mp_output_to.x0)
        #     print("mp_output_to_y0", self.iteration)
        #     print(mp_output_to.y0)
        #     print("mp_output_to_z0", self.iteration)
        #     print(mp_output_to.z0)
        #
        #     varia = self.interface_output_to.get_variable_data(item_output_to['model_part'], item_output_to['variables'][0])
        #     print("displacement", self.iteration)
        #     print(varia)

        return self.interface_output_to.copy()

    def finalize_solution_step(self):
        super().finalize_solution_step()

        self.solver_wrapper.finalize_solution_step()

    def finalize(self):
        super().finalize()

        self.solver_wrapper.finalize()
        self.mapper_interface_input.finalize()
        self.mapper_interface_output.finalize()
        self.mapper_interface_input_update_from.finalize()
        self.mapper_interface_input_update_to.finalize()

    def output_solution_step(self):
        super().output_solution_step()

        self.solver_wrapper.output_solution_step()
        self.mapper_interface_input.output_solution_step()
        self.mapper_interface_output.output_solution_step()
        self.mapper_interface_input_update_from.output_solution_step()
        self.mapper_interface_input_update_to.output_solution_step()

    def get_interface_input(self):
        # does not contain most recent data
        return self.interface_input_from

    def get_iteration(self):
        return self.iteration

    def get_interface_output(self):
        interface_output_from = self.solver_wrapper.get_interface_output()
        self.mapper_interface_output(interface_output_from, self.interface_output_to)
        return self.interface_output_to

    def print_components_info(self, pre):
        tools.print_info(pre, "The component ", self.__class__.__name__, " maps the following solver wrapper:")
        pre = tools.update_pre(pre)
        self.solver_wrapper.print_components_info(pre + '├─')
        tools.print_info(pre, '├─', "Input mapper:")
        self.mapper_interface_input.print_components_info(pre + '│ └─')
        tools.print_info(pre, '└─', "Output mapper:")
        self.mapper_interface_output.print_components_info(pre + '  └─')
