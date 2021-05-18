from coconut.coupling_components.mappers.transformer import MapperTransformer
from coconut.data_structure import variables_dimensions

from scipy.spatial import cKDTree

import numpy as np


def create(parameters):
    return MapperRemoveAxialComponent(parameters)

# TODO: mention in docs that these mappers cannot handle singular points (i.e. with r = 0, e.g. balloon)

class MapperRemoveAxialComponent(MapperTransformer):
    def __init__(self, parameters):
        super().__init__(parameters)

        # get axial and radial directions
        dirs = ['x', 'y', 'z']
        if self.settings['direction_axial'] not in dirs:
            raise ValueError(f'invalid axial_direction {self.settings["direction_axial"]}')
        if self.settings['direction_axial'] not in dirs:
            raise ValueError(f'invalid radial_direction {self.settings["direction_radial"]}')
        self.dir_a = dirs.index(self.settings['direction_axial'])
        self.dir_r = dirs.index(self.settings['direction_radial'])
        self.dir_3d = ({0, 1, 2} - {self.dir_a, self.dir_r}).pop()

        self.radius = self.settings['dif_radius_wire']
        if type(self.radius) != float:
            raise TypeError('coords_max must be a float')


    def initialize(self, model, model_part_name_in, model_part_name_out, forward):
            super().initialize()

            if forward:
                mp_in = model.get_model_part(model_part_name_in)
                n_in = mp_in.size
                n_out = n_in

                self.coords_in = np.column_stack((mp_in.x0, mp_in.y0, mp_in.z0))

                coords_out = self.coords_in.copy()
                ids_out = np.arange(n_out)

                model.create_model_part(model_part_name_out, coords_out[:, 0],
                                    coords_out[:, 1], coords_out[:, 2], ids_out)

            else:
                raise NotImplementedError('Forward Initialization not implemented for MapperRemoveAxialComponent.')


    def __call__(self, args_from, args_to):
        super().__call__(args_from, args_to)

        interface_from, mp_name_from, var = args_from
        interface_to, mp_name_to, _ = args_to

        dimensions = variables_dimensions[var]
        data_from = interface_from.get_variable_data(mp_name_from, var)

        if dimensions == 3:
            data_to = np.tile(data_from, (1, 1))

            data_to[:,self.dir_r] = 0.0
            data_to[:, self.dir_a] = self.radius + data_to[:,self.dir_a]

        else:
            raise NotImplementedError(f'MapperRemoveAxialComponent not implemented for variable of dimension {dimensions}')

        interface_to.set_variable_data(mp_name_to, var, data_to)