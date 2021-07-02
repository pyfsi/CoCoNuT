from coconut.coupling_components.solver_wrappers.foam_Extend.foam_Extend import SolverWrapperFoamExtend
from coconut import tools
from coconut.coupling_components.solver_wrappers.foam_Extend import foam_Extend_io as fe_io

from subprocess import check_call
from os.path import join


def create(parameters):
    return SolverWrapperFoamExtend41(parameters)


class SolverWrapperFoamExtend41(SolverWrapperFoamExtend):
    version = 'fe4.1'

    def __init__(self, parameters):
        super().__init__(parameters)
        self.env = tools.get_solver_env(__name__, self.working_directory)

        # compile adapted openfoam software
        self.compile_adapted_foam_Extend_solver()

        # check that the correct software is available
        self.check_software()

    def write_cell_centres(self):
        check_call('writeCellCentres -time 0 &> log.writeCellCentres;', cwd=self.working_directory, shell=True,
                   env=self.env)

    def read_face_centres(self, boundary_name, nfaces):
        filename_x = join(self.working_directory, '0/ccx')
        filename_y = join(self.working_directory, '0/ccy')
        filename_z = join(self.working_directory, '0/ccz')

        x0 = fe_io.get_boundary_field(file_name=filename_x, boundary_name=boundary_name, size=nfaces,
                                      is_scalar=True)
        y0 = fe_io.get_boundary_field(file_name=filename_y, boundary_name=boundary_name, size=nfaces,
                                      is_scalar=True)
        z0 = fe_io.get_boundary_field(file_name=filename_z, boundary_name=boundary_name, size=nfaces,
                                      is_scalar=True)
        return x0, y0, z0

    def displacement_dict(self, boundary_name):
        dct = (f'Displacement_{boundary_name}\n'
               f'{{\n'
               f'type  	             surfaceRegion;\n'
               f'libs 	             ("libfieldFunctionObjects.so");\n'
               f'executeControl 	 timeStep;\n'
               f'executeInterval 	 1;\n'
               f'writeControl 	     timeStep;\n'
               f'writeInterval 	     1;\n'
               f'timeFormat 	     fixed;\n'
               f'timePrecision 	     {self.time_precision};\n'
               f'operation 	         none;\n'
               f'writeFields 	     true;\n'
               f'surfaceFormat 	     raw;\n'
               f'regionType 	     patch;\n'
               f'name 	             {boundary_name};\n'
               f'fields              (DU);\n'
               f'}}\n')
        return dct


