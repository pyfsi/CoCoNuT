from coconut.coupling_components.mappers.interpolator import MapperInterpolator

import numpy as np


def Create(parameters):
    return MapperNearest(parameters)


# Class MapperNearest: nearest-neighbour interpolation.
class MapperNearest(MapperInterpolator):
    def __init__(self, parameters):
        super().__init__(parameters)

        self.n_nearest = 1

    def Initialize(self, model_part_from, model_part_to):
        super().Initialize(model_part_from, model_part_to)

        # self.nearest = self.nearest.reshape(-1, 1)
        self.coeffs = np.ones((self.n_to, 1))
