from coconut.data_structure import KratosUnittest
from coconut.tests.solver_wrappers.fluent.test_v2019R3 import TestSolverWrapperFluent2019R3


class TestSolverWrapperFluent2020R1(TestSolverWrapperFluent2019R3):
    """
    Only 1 Fluent version can be tested at a time,
    because the correct software version must be
    preloaded.

    Another consequence is that this version cannot
    be tested independentely (i.e. in this folder),
    because of inheritance.
    """

    version = '2020R1'

    def test_solver_wrapper_fluent_2020R1(self):
        self.test_solver_wrapper_fluent_2019R1_tube2d()
        self.test_solver_wrapper_fluent_2019R3_tube3d()


if __name__ == '__main__':
    KratosUnittest.main()
