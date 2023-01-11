from coconut.coupling_components.coupled_solvers.gauss_seidel import CoupledSolverGaussSeidel
from coconut.tools import print_info


def create(parameters):
    return CoupledSolverExplicit(parameters)


class CoupledSolverExplicit(CoupledSolverGaussSeidel):
    def __init__(self, parameters):
        super().__init__(parameters)
        print_info('Explicit solver is chosen; convergence criterion is not used.', layout='warning')

    def solve_solution_step(self):
        # initial value
        self.x = self.predictor.predict(self.x)
        # first coupling iteration
        self.y = self.solver_wrappers[0].solve_solution_step(self.x.copy()).copy()
        xt = self.solver_wrappers[1].solve_solution_step(self.y.copy()).copy()
        r = xt - self.x
        self.finalize_iteration(r)
        self.x = xt
