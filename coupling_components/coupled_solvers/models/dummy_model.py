from coconut.coupling_components.component import Component
from coconut import tools


def create(parameters):
    return DummyModel(parameters)


class DummyModel(Component):
    provides_get_solution = True
    provides_set_solution = False

    @tools.time_initialize
    def __init__(self, _):
        super().__init__()

        self.solver_level = None

        # time
        self.init_time = 0.0
        self.run_time = 0.0

    @tools.time_solve_solution_step
    def get_solution(self):
        # surrogate information
        pre = ' │' * (self.solver_level - 1)
        out = f'{pre} ┌{(78 - len(pre)) * "─"}\n' \
              f'{pre} │\tSurrogate\n' \
              f'{pre} ├{(78 - len(pre)) * "─"}\n' \
              f'{pre} │{"Iteration":<16}{"Norm residual":<28}'
        tools.print_info(out)
        out = f'{pre} └{(78 - len(pre)) * "─"}\n' \
              f'{pre}{"Iteration":<16}{"Norm residual":<28}'
        tools.print_info(out)

    # noinspection PyMethodMayBeStatic
    def predict(self, dr, **_):
        return dr * 0

    def add(self, r, xt):
        pass

    # noinspection PyMethodMayBeStatic
    def is_ready(self):
        return False

    # noinspection PyMethodMayBeStatic
    def filter_q(self, dr):
        return dr

    def print_components_info(self, pre):
        tools.print_info(pre, 'The component ', self.__class__.__name__)
