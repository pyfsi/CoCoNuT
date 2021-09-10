from coconut.tools import solver_available
from coconut.tests.solver_wrappers.abaqus import abaqus

import unittest

version = '2021'


@unittest.skipUnless(solver_available(f'abaqus.v{version}'), f'abaqus.v{version} not available')
class TestSolverWrapperAbaqus2021Tube2D(abaqus.TestSolverWrapperAbaqusTube2D):
    version = version
    setup_case = True


class TestSolverWrapperAbaqus2021Tube3D(abaqus.TestSolverWrapperAbaqusTube3D):
    version = version
    setup_case = True


if __name__ == '__main__':
    unittest.main()
