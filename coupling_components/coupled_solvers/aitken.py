from coconut.coupling_components.coupled_solvers.gauss_seidel import CoupledSolverGaussSeidel

import numpy as np


def Create(parameters):
    return CoupledSolverAITKEN(parameters)


class CoupledSolverAITKEN(CoupledSolverGaussSeidel):
    def __init__(self, parameters):
        super().__init__(parameters)

        self.settings = parameters["settings"]
        self.omega_max = self.settings["omega_max"].GetDouble()

        self.omega = self.omega_max
        self.added = False
        self.rcurr = None

    def Predict(self, r_in):
        r = r_in.GetNumpyArray()
        # Calculate return value if sufficient data available
        if not self.added:
            raise RuntimeError("No information to predict")
        dx = self.omega * r
        dx_out = r_in.deepcopy()
        dx_out.SetNumpyArray(dx)
        return dx_out

    def update(self, x_in, xt_in):
        x = x_in.GetNumpyArray().reshape(-1, 1)
        xt = xt_in.GetNumpyArray().reshape(-1, 1)
        r = xt - x
        rprev = self.rcurr
        self.rcurr = r
        if self.added:
            # Aitken Relaxation
            # Update omega
            self.omega *= -float(rprev.T @ (r - rprev) / np.linalg.norm(r - rprev, 2) ** 2)
        else:
            # Set first value of omega in a timestep
            self.omega = np.sign(self.omega) * min(abs(self.omega), self.omega_max)
            self.added = True

    def solve_solution_step(self):
        # Initial value
        self.x = self.predictor.Predict(self.x)
        # First coupling iteration
        self.y = self.solver_wrappers[0].solve_solution_step(self.x)
        xt = self.solver_wrappers[1].solve_solution_step(self.y)
        r = xt - self.x
        self.update(self.x, xt)
        self.finalize_Iteration(r)
        # Coupling iteration loop
        while not self.convergence_criterion.is_satisfied():
            self.x += self.Predict(r)
            self.y = self.solver_wrappers[0].solve_solution_step(self.x)
            xt = self.solver_wrappers[1].solve_solution_step(self.y)
            r = xt - self.x
            self.update(self.x, xt)
            self.finalize_Iteration(r)

    def IsReady(self):
        return self.added

    def initialize_solution_step(self):
        super().initialize_solution_step()

        self.added = False
        self.rcurr = None
