from coconut.coupling_components.component import Component

import numpy as np


def Create(parameters):
    return ConvergenceCriterionRelativeNorm(parameters)


class ConvergenceCriterionRelativeNorm(Component):
    def __init__(self, parameters):
        super().__init__()

        settings = parameters["settings"]
        self.tolerance = settings["tolerance"].GetDouble()
        self.order = settings["order"].GetInt()



        self.initial_norm = 0.0
        self.last_norm = 0.0
        self.is_initial_norm_set = False

    def InitializeSolutionStep(self):
        super().InitializeSolutionStep()

        self.initial_norm = 0.0
        self.last_norm = 0.0
        self.is_initial_norm_set = False

    def Update(self, r):
        self.last_norm = np.linalg.norm(r.GetNumpyArray(), self.order)
        if not self.is_initial_norm_set:
            self.initial_norm = self.last_norm
            self.is_initial_norm_set = True
            if self.initial_norm < np.finfo(type(self.initial_norm)).eps:
                raise Exception("Initial norm is too small")

    def IsSatisfied(self):
        # tools.PrintInfo("Norm: " + str(self.last_norm))
        if not self.is_initial_norm_set:
            return False
        else:
            return self.last_norm/self.initial_norm < self.tolerance
