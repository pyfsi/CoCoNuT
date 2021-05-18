from coconut.coupling_components.mappers.transformer import MapperTransformer
from coconut.coupling_components.solver_wrappers.mapped_update import SolverWrapperMapped_update
from coconut.data_structure import variables_dimensions
from scipy import interpolate

import numpy as np

def create(parameters):
    return Mapper_initial_load(parameters)


class Mapper_initial_load(MapperTransformer):
    def __init__(self, parameters):
        super().__init__(parameters)

        self.v_min = self.settings['coords_min']
        if type(self.v_min) != float:
            raise TypeError('coords_min must be a float')

        self.first_iteration = False


    def initialize(self, model, model_part_name_in, model_part_name_out, forward):
        if forward:
            super().initialize()

            self.mp_input_to = model.get_model_part(model_part_name_in)

            n_in = self.mp_input_to.size
            n_out = n_in
            self.n_from = n_out
            self.n_to = n_in

            self.coords_in = np.column_stack((self.mp_input_to.x0, self.mp_input_to.y0, self.mp_input_to.z0))
            ids_out = np.arange(n_out)


            self.mp_out = model.create_model_part(model_part_name_out, self.coords_in[:, 0],
                                    self.coords_in[:, 1], self.coords_in[:, 2], ids_out)

        else:
            raise NotImplementedError('Forward Initialization not implemented for initial_load')

    def __call__(self, args_from, args_to):
        super().__call__(args_from, args_to)

        print(self.first_iteration)

        if self.first_iteration:
            interface_from, mp_name_from, var = args_from
            interface_to, mp_name_to, _ = args_to
            self.v_min = self.settings['coords_min']

            dimensions = variables_dimensions[var]
            self.data_from = interface_from.get_variable_data(mp_name_from, var)

            a = np.loadtxt('initial_pressure.dat')
            b = np.hsplit(a, 2)
            x = b[0]
            y = b[1]
            x_axis = x.flatten()
            pressure = y.flatten()

            f = interpolate.interp1d(x_axis, pressure, fill_value='extrapolate')

            if dimensions == 1:
                data_to = self.data_from
                # data_to = np.zeros((self.mp_input_to.size, 1))
                # for i in range(self.mp_input_to.size):
                #     if self.mp_input_to.x0[i] > self.v_min:
                #         data_to[i] = f(self.mp_input_to.x0[i])
                #     else:
                #         data_to[i] = 0

            elif dimensions == 3:

                # data_to = np.zeros((self.mp_input_to.size, 3))
                data_to = self.data_from
                # for j in range(self.mp_input_to.size):
                #     if self.mp_input_to.x0[j] < self.v_min:
                #         data_to[j, 0] = 0
                #         data_to[j, 1] = 0
                #         data_to[j, 2] = 0
                #     else:
                #         data_to[j, 0] = 0
                #         data_to[j, 1] = 0
                #         data_to[j, 2] = 0
            else:
                raise NotImplementedError(
                    f'MapperUpdateLoad not implemented for variable of dimension {dimensions}')
            interface_to.set_variable_data(mp_name_to, var, data_to)

        else:
            interface_from, mp_name_from, var = args_from
            interface_to, mp_name_to, _ = args_to

            dimensions = variables_dimensions[var]
            self.data_from = interface_from.get_variable_data(mp_name_from, var)

            if dimensions == 1:
                data_to = self.data_from

            elif dimensions == 3:

                data_to = self.data_from

            else:
                raise NotImplementedError(
                    f'MapperUpdateLoad not implemented for variable of dimension {dimensions}')
            interface_to.set_variable_data(mp_name_to, var, data_to)





