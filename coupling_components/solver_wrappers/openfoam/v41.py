from coconut import data_structure
from coconut.coupling_components.component import Component
from coconut.data_structure.interface import Interface
from coconut import tools
from coconut.coupling_components.solver_wrappers.openfoam import openfoam_io as of_io

from subprocess import check_call
import numpy as np
import os
import sys
import time
import subprocess
import re


def create(parameters):
    return SolverWrapperOpenFOAM_41(parameters)


class SolverWrapperOpenFOAM_41(Component):
    def __init__(self, parameters):
        super().__init__()

        # Settings
        self.settings = parameters['settings']
        self.working_directory = self.settings['working_directory']
        # adapted application from openfoam ('coconut_<application name>')
        self.application = self.settings['application']
        self.delta_t = self.settings['delta_t']
        self.time_precision = self.settings['time_precision']
        self.start_time = self.settings['timestep_start']
        # boundary_names is the set of boundaries in OpenFoam used for coupling
        self.boundary_names = self.settings['boundary_names']
        self.version = '4.1'

        # set on True to save copy of input and output files in every iteration
        self.debug = True

        # check interface names in 'interface_input' and 'interface_output' with boundary names provided in boundary_names
        self.check_interfaces()

        # Check that the correct modules have been loaded
        self.check_software()

        # Remove possible CoCoNuT-message from previous interrupt
        self.remove_all_messages()

        # obtain number of cores from self.working_directory/system/decomposeParDict
        self.cores = 1
        if self.settings['parallel']:
            file_name = os.path.join(self.working_directory, 'system/decomposeParDict')
            if not os.path.isfile(file_name):
                raise RuntimeError(
                    f'In the parameters:\n{self.settings}\n key "parallel" is set to {True} but {file_name} does not exist.')
            else:
                with open(file_name, 'r') as file:
                    decomposedict_string = file.read()
                self.cores = of_io.get_int(input_string=decomposedict_string, keyword='numberOfSubdomains')

        # Modify controlDict file to add  pressure and wall shear stress functionObjects for all the boundaries in self.settings["boundary_names"]
        self.read_modify_controldict()

        # Creating Model
        self.model = data_structure.Model()

        # writeCellcentres writes cellcentres in internal field and face centres in boundaryField
        check_call(f'writeCellCentres -time {self.start_time} &> log.writeCellCentres;', cwd=self.working_directory,
                   shell=True)
        boundary_filename = os.path.join(self.working_directory, 'constant/polyMesh/boundary')

        for boundary in self.boundary_names:
            with open(boundary_filename, 'r') as boundary_file:
                boundary_file_string = boundary_file.read()
            boundary_dict = of_io.get_dict(input_string=boundary_file_string, keyword=boundary)
            # get point ids and coordinates for all the faces in the boundary
            node_ids, node_coords = of_io.get_boundary_points(case_directory=self.working_directory, time_folder='0',
                                                              boundary_name=boundary)
            nfaces = of_io.get_int(input_string=boundary_dict, keyword='nFaces')
            start_face = of_io.get_int(input_string=boundary_dict, keyword='startFace')

            # create input model part
            self.model.create_model_part(f'{boundary}_input', node_coords[:, 0], node_coords[:, 1], node_coords[:, 2],
                                         node_ids)

            filename_x = os.path.join(self.working_directory, '0/ccx')
            filename_y = os.path.join(self.working_directory, '0/ccy')
            filename_z = os.path.join(self.working_directory, '0/ccz')

            x0 = of_io.get_boundary_field(file_name=filename_x, boundary_name=boundary, size=nfaces,
                                          is_scalar=True)
            y0 = of_io.get_boundary_field(file_name=filename_y, boundary_name=boundary, size=nfaces,
                                          is_scalar=True)
            z0 = of_io.get_boundary_field(file_name=filename_z, boundary_name=boundary, size=nfaces,
                                          is_scalar=True)
            ids = np.arange(0, nfaces)

            # create output model part
            mp_output = self.model.create_model_part(f'{boundary}_output', x0, y0, z0, ids)
            mp_output.start_face = start_face
            mp_output.nfaces = nfaces

        # Create CoSimulationInterfaces
        self.interface_input = Interface(self.settings['interface_input'], self.model)
        self.interface_output = Interface(self.settings['interface_output'], self.model)

        # run time
        self.run_time = 0.0

        self.plot_of_residuals = True  # TODO: add in the parameters
        self.residual_variables = self.settings.get('residual_variables', None)
        self.res_filepath = os.path.join(self.working_directory, 'residuals.dat')
        self.step = 1
        if not self.residual_variables is None:
            self.write_residuals_fileheader()
        elif self.plot_of_residuals:
            tools.print_info('No openfoam variables in the parameters key "residual_variables". Cannot plot residuals.',
                             layout='warning')

    def initialize(self):
        super().initialize()

        # Define timestep and physical time
        self.timestep = 0
        self.physical_time = self.start_time

        ##Copy zero folder to folder with correctly named timeformat
        if self.physical_time == 0:
            timestamp = '{:.{}f}'.format(self.physical_time, self.time_precision)
            path_orig = os.path.join(self.working_directory, '0')
            path_new = os.path.join(self.working_directory, timestamp)
            os.system(f'cp -r {path_orig} {path_new}')

        ## If parallell do a decomposition and establish a remapping for the output based on the faceProcAddressing
        '''Note concerning the sequence: The file ./processorX/constant/polyMesh/pointprocAddressing contains a list of 
        indices referring to the original index in the ./constant/polyMesh/points file, these indices go from 0 to nPoints -1
        However, mesh faces can be shared between processors and it has to be tracekd whether these are inverted or not
        This inversion is indicated by negative indices. However, as minus 0 is not a thing, the indices are first incremented by 1 before inversion
        Therefore to get the correct index one should use |index|-1!!
        Normally no doubles should be encountered on an interface as these faces are not shared by processors
        '''
        if self.settings['parallel']:
            check_call(f'decomposePar -force -time {self.start_time}&> log.decomposePar', cwd=self.working_directory,
                       shell=True)
            for boundary in self.boundary_names:
                mp_output = self.model.get_model_part(f'{boundary}_output')
                mp_output.sequence = []
                for p in range(self.cores):
                    path = os.path.join(self.working_directory, f'processor{p}/constant/polyMesh/faceProcAddressing')
                    with open(path, 'r') as f:
                        face_proc_add_string = f.read()
                    face_proc_add = np.abs(of_io.get_scalar_array(input_string=face_proc_add_string, is_int=True))
                    face_proc_add -= 1

                    mp_output.sequence += (face_proc_add[(face_proc_add >= mp_output.start_face) & (
                            face_proc_add < mp_output.start_face + mp_output.nfaces)] - mp_output.start_face).tolist()

                np.savetxt(os.path.join(self.working_directory, f'sequence_{boundary}.txt'),
                           np.array(mp_output.sequence), fmt='%i')

                if len(mp_output.sequence) != mp_output.nfaces:
                    print(f'sequence: {mp_output.sequence.size}')
                    print(f'nNodes: {mp_output.size}')
                    raise ValueError('Number of face indices in sequence does not correspond to number of faces')

        # Don't forget to start OpenFOAM-loop!
        if not self.settings['parallel']:
            cmd = self.application + '&> log.' + self.application
        else:
            cmd = 'mpirun -np ' + str(self.cores) + ' ' + self.application + ' -parallel &> log.' + self.application

        self.openfoam_process = subprocess.Popen(cmd, cwd=self.working_directory, shell=True)

    def initialize_solution_step(self):
        super().initialize_solution_step()

        # For parallel runs need to create a folder with the correct time stamp for decomposition of pointDisplacement_Next
        # For serial runs, this folder will normally be present
        timestamp = '{:.{}f}'.format(self.physical_time, self.time_precision)
        path = os.path.join(self.working_directory, timestamp)
        if self.cores > 1:
            os.system('mkdir -p ' + path)
        elif self.physical_time == 0:  # for serial also need to make a folder 0.0000 with specified precision
            os.system('mkdir -p ' + path)

        # Prepare new time step folder and reset the number of iterations
        self.timestep += 1
        self.iteration = 0
        self.physical_time += self.delta_t

        self.prev_timestamp = timestamp
        self.cur_timestamp = f'{self.physical_time:.{self.time_precision}f}'

        if not self.settings['parallel']:  # if serial
            new_path = os.path.join(self.working_directory, self.cur_timestamp)
            if os.path.isdir(new_path):
                print('\n\n\n Warning! In 5s, CoCoNuT will overwrite existing time step folder: ' + str(
                    new_path) + '. \n\n\n')
                time.sleep(5)
                os.system('rm -rf ' + new_path)
            os.system('mkdir -p ' + new_path)
        else:
            for i in np.arange(self.cores):
                new_path = os.path.join(self.working_directory, 'processor' + str(i), self.cur_timestamp)
                if os.path.isdir(new_path):
                    if i == 0:
                        print('\n\n\n Warning! In 5s, CoCoNuT will overwrite existing time step folder in '
                              'processor-subfolders. \n\n\n')
                        time.sleep(5)
                    os.system('rm -rf ' + new_path)
                os.system('mkdir -p ' + new_path)

        self.send_message('next')
        self.wait_message('next_ready')

    @tools.time_solve_solution_step
    def solve_solution_step(self, interface_input):
        self.iteration += 1

        # store incoming displacements
        self.interface_input.set_interface_data(interface_input.get_interface_data())

        # write interface data to OpenFOAM-file
        self.write_node_input()

        # copy output data for debugging
        if self.debug:
            if self.cores > 1:
                for i in range(0, self.cores):
                    path = os.path.join(self.working_directory, 'processor' + str(i), self.prev_timestamp,
                                        'pointDisplacement_Next')
                    path2 = os.path.join(self.working_directory, 'processor' + str(i), self.prev_timestamp,
                                         'pointDisplacement_Next_Iter' + str(self.iteration))
                    cmd = f'cp {path} {path2}'
                    os.system(cmd)
            else:
                path = os.path.join(self.working_directory, self.prev_timestamp, 'pointDisplacement_Next')
                path2 = os.path.join(self.working_directory, self.prev_timestamp,
                                     'pointDisplacement_Next_Iter' + str(self.iteration))
                cmd = f'cp {path} {path2}'
                os.system(cmd)

        self.delete_prev_iter_output()

        self.send_message('continue')
        self.wait_message('continue_ready')

        # copy output data for debugging
        if self.debug:
            for boundary in self.boundary_names:
                # specify location of pressure and traction
                traction_name = 'TRACTION_' + boundary
                pressure_name = 'PRESSURE_' + boundary
                mp_name = f'{boundary}_output'
                mp = self.model.get_model_part(mp_name)
                nfaces = mp.size
                wss_filepath = os.path.join(self.working_directory, 'postProcessing', traction_name, 'surface',
                                            self.cur_timestamp, f'wallShearStress_patch_{boundary}.raw')
                pres_filepath = os.path.join(self.working_directory, 'postProcessing', pressure_name, 'surface',
                                             self.cur_timestamp, f'p_patch_{boundary}.raw')
                wss_iter_filepath = os.path.join(self.working_directory, 'postProcessing', traction_name, 'surface',
                                                 self.cur_timestamp, f'wallShearStress_patch_{boundary}_{self.iteration}.raw')
                pres_iter_filepath = os.path.join(self.working_directory, 'postProcessing', pressure_name, 'surface',
                                                  self.cur_timestamp, f'p_patch_{boundary}_{self.iteration}.raw')
                cmd = f'cp {wss_filepath} {wss_iter_filepath} && cp {pres_filepath} {pres_iter_filepath}'
                os.system(cmd)

        # read data from OpenFOAM
        self.read_node_output()

        # return interface_output object
        return self.interface_output

    def finalize_solution_step(self):
        super().finalize_solution_step()

        prev_timestep = self.timestep - 1
        # remove the folder that was used for pointDisplacement_Next if not in writeInterval
        if self.settings['parallel']:
            dir_pointdisp_next = os.path.join(self.working_directory, self.prev_timestamp)
            os.system('rm -rf ' + dir_pointdisp_next)

            if prev_timestep % self.write_interval:
                for p in range(self.cores):
                    prev_timestep_dir = os.path.join(self.working_directory, f'processor{p}/{self.prev_timestamp}')
                    os.system('rm -rf ' + prev_timestep_dir)
        else:
            if prev_timestep % self.write_interval:
                dir_pointdisp_next = os.path.join(self.working_directory, self.prev_timestamp)
                os.system('rm -rf ' + dir_pointdisp_next)

        if not (self.timestep % self.write_interval):
            self.send_message('save')
            self.wait_message('save_ready')

        if not self.residual_variables is None:
            self.write_and_plot_of_residuals()

    def finalize(self):
        super().finalize()

        self.send_message('stop')
        self.wait_message('stop_ready')
        os.system(f'pkill -f {self.application}')
        self.openfoam_process.kill()

    def get_interface_input(self):
        return self.interface_input

    def get_interface_output(self):
        return self.interface_output

    def delete_prev_iter_output(self):
        # pressure and wall shear stress files are removed to avoid openfoam to append data in the new iteration
        for boundary in self.boundary_names:
            # specify location of pressure and traction
            traction_name = 'TRACTION_' + boundary
            pressure_name = 'PRESSURE_' + boundary
            wss_file = os.path.join(self.working_directory, 'postProcessing', traction_name, 'surface',
                                    self.cur_timestamp, 'wallShearStress_patch_' + boundary + '.raw')
            pres_file = os.path.join(self.working_directory, 'postProcessing', pressure_name, 'surface',
                                     self.cur_timestamp, 'p_patch_' + boundary + '.raw')
            if os.path.isfile(wss_file):
                os.system(f'rm -rf {wss_file}')
            if os.path.isfile(pres_file):
                os.system(f'rm -rf {pres_file}')

    def read_node_output(self):

        # Default value is 1.0 for compressible case. When the solver is incompressible, the pressure and shear stress are
        # kinematic; therefore multiply with the fluid density.
        density = 1.0
        if self.settings['is_incompressible']:
            density = self.settings['density']

        for boundary in self.boundary_names:
            # specify location of pressure and traction
            traction_name = 'TRACTION_' + boundary
            pressure_name = 'PRESSURE_' + boundary
            mp_name = f'{boundary}_output'
            mp = self.model.get_model_part(mp_name)
            nfaces = mp.size
            wss_filename = os.path.join(self.working_directory, 'postProcessing', traction_name, 'surface',
                                        self.cur_timestamp, 'wallShearStress_patch_' + boundary + '.raw')
            pres_filepath = os.path.join(self.working_directory, 'postProcessing', pressure_name, 'surface',
                                         self.cur_timestamp, 'p_patch_' + boundary + '.raw')

            # check if the pressure and wall shear stress files completed by openfoam and read data
            if self.check_output_file(wss_filename, nfaces):
                wss_tmp = np.loadtxt(wss_filename, comments='#')[:, 3:]

            if self.check_output_file(pres_filepath, nfaces):
                pres_tmp = np.loadtxt(pres_filepath, comments='#')[:, 3]

            if self.settings['parallel']:
                pos_list = mp.sequence
            else:
                pos_list = [pos for pos in range(0, nfaces)]

            wall_shear_stress = np.empty(wss_tmp.shape)
            pressure = np.empty((pres_tmp.size, 1))

            wall_shear_stress[pos_list,] = wss_tmp[:, ]
            pressure[pos_list, 0] = pres_tmp[:]

            self.interface_output.set_variable_data(mp_name, 'traction', wall_shear_stress * -1 * density)
            self.interface_output.set_variable_data(mp_name, 'pressure', pressure * density)

    # writeFooter: to write OpenFOAM-footer in file at location 'file_loc'
    def write_footer(self, file_name):
        f = open(file_name, 'a')
        f.write('\n')
        f.write(r'// ************************************************************************* //' + '\n')
        f.close()

    def write_node_input(self):
        # The displacement of the FSI interface is passed through the file 'pointDisplacement_Next'
        # This function will prepare that file in a 'serial format' and then decompose it for parallel operation

        pointdisp_filename_ref = os.path.join(self.working_directory, '0', 'pointDisplacement')

        pointdisp_filename = os.path.join(self.working_directory, self.prev_timestamp, 'pointDisplacement_Next')

        with open(pointdisp_filename_ref, 'r') as ref_file:
            pointdisp_string = ref_file.read()

        for boundary in self.boundary_names:
            mp_name = f'{boundary}_input'
            displacement = self.interface_input.get_variable_data(mp_name, 'displacement')
            boundary_dict = of_io.get_dict(input_string=pointdisp_string, keyword=boundary)
            boundary_dict_new = of_io.update_vector_array_dict(dict_string=boundary_dict, vector_array=displacement)
            pointdisp_string = pointdisp_string.replace(boundary_dict, boundary_dict_new)

        with open(pointdisp_filename, 'w') as f:
            f.write(pointdisp_string)

        if self.settings['parallel']:
            check_call(f'decomposePar -fields -time {self.prev_timestamp} &> log.decomposePar;',
                       cwd=self.working_directory, shell=True)

    def check_output_file(self, filename, nfaces):
        counter = 0
        nlines = 0
        lim = 1000
        while (nlines < nfaces + 2) and counter < lim:
            if os.path.isfile(filename):
                with open(filename, 'r') as f:
                    nlines = sum(1 for line in f)
            time.sleep(0.01)
            counter += 1
        if counter == lim:
            raise RuntimeError(f'Timed out waiting for file: {filename}.')
        else:
            return True

    def send_message(self, message):
        file = os.path.join(self.working_directory, message + '.coco')
        open(file, 'w').close()
        return

    def wait_message(self, message):
        wait_time_lim = 10 * 60  # 10 minutes maximum waiting time for a single flow solver iteration
        cumul_time = 0
        file = os.path.join(self.working_directory, message + '.coco')
        while not os.path.isfile(file):
            time.sleep(0.01)
            cumul_time += 0.01
            if cumul_time > wait_time_lim:
                os.system('pkill ' + self.application)
                sys.exit('CoCoNuT timed out in the OpenFOAM solver_wrapper, waiting for message: ' + message + '.coco.')
        os.remove(file)
        return

    def check_message(self, message):
        file = os.path.join(self.working_directory, message + '.coco')
        if os.path.isfile(file):
            os.remove(file)
            return True
        return False

    def remove_all_messages(self):
        for file_name in os.listdir(self.working_directory):
            if file_name.endswith('.coco'):
                file = os.path.join(self.working_directory, file_name)
                os.remove(file)

    def check_software(self):
        if os.system(self.application + ' -help &> checkSoftware') != 0:
            raise RuntimeError(f'OpenFOAM not loaded properly. You should perform the following steps:\n'
                               f'-\tLoad the module for OpenFOAM-{self.version},\n'
                               f'-\tSource $FOAM_BASH,\n'
                               f'-\tCompile {self.application}')

        # check version
        with open('checkSoftware', 'r') as f:
            lastLine = f.readlines()[-2]  # Second last line contains 'Build: XX' with XX the version number
        f.close()
        os.system('rm checkSoftware')
        versionNr = lastLine.split(' ')[-1]
        if versionNr[:-1] != self.version:
            raise RuntimeError(
                f'OpenFOAM-{self.version} should be loaded! Currently, OpenFOAM-{versionNr[:-1]} of OpenFOAM is loaded')

    def check_interfaces(self):
        input_interface_model_parts = [param['model_part'] for param in self.settings['interface_input']]
        output_interface_model_parts = [param['model_part'] for param in self.settings['interface_output']]
        boundary_names = self.settings['boundary_names']

        for boundary_name in boundary_names:
            if f'{boundary_name}_input' not in input_interface_model_parts:
                raise RuntimeError(
                    f'Error in json file: {boundary_name}_input not listed in "interface_input": '
                    f'{self.settings["interface_input"]}.\n. <boundary> in the "boundary_names" in json file should '
                    f'have corresponding <boundary>_input in "interface_input" list. ')

            if f'{boundary_name}_output' not in output_interface_model_parts:
                raise RuntimeError(
                    f'Error in json file: {boundary_name}_output not listed in "interface_output": '
                    f'{self.settings["interface_output"]}.\n. <boundary> in the "boundary_names" in json file should '
                    f'have corresponding <boundary>_output in "interface_output" list.')

    def read_modify_controldict(self):

        file_name = os.path.join(self.working_directory, 'system/controlDict')
        with open(file_name, 'r') as control_dict_file:
            control_dict = control_dict_file.read()
            self.write_interval = of_io.get_int(input_string=control_dict, keyword='writeInterval')
            time_format = of_io.get_string(input_string=control_dict, keyword='timeFormat')
            self.write_precision = of_io.get_int(input_string=control_dict, keyword='writePrecision')
            if not time_format == 'fixed':
                msg = f'timeFormat:{time_format} in controlDict not implemented. Changed to "fixed"'
                tools.print_info(msg, layout='warning')
                control_dict = re.sub(r'timeFormat' + of_io.delimter + r'\w+', f'timeFormat    fixed',
                                      control_dict)

            control_dict = re.sub(r'application' + of_io.delimter + r'\w+', f'application    {self.application}',
                                  control_dict)
            control_dict = re.sub(r'startTime' + of_io.delimter + of_io.float_pattern,
                                  f'startTime    {self.start_time}', control_dict)
            control_dict = re.sub(r'deltaT' + of_io.delimter + of_io.float_pattern, f'deltaT    {self.delta_t}',
                                  control_dict)
            control_dict = re.sub(r'timePrecision' + of_io.delimter + of_io.int_pattern,
                                  f'timePrecision    {self.time_precision}',
                                  control_dict)
            control_dict = re.sub(r'endTime' + of_io.delimter + of_io.float_pattern, f'endTime    0.01', control_dict)

            # delete previously defined coconut functions
            coconut_start_string = '// CoCoNuT function objects'
            control_dict = re.sub(coconut_start_string + r'.*', '', control_dict, flags=re.S)

        with open(file_name, 'w') as control_dict_file:
            control_dict_file.write(control_dict)

        with open(file_name, 'a') as control_dict_file:
            control_dict_file.write(coconut_start_string + '\n')
            control_dict_file.write('boundary_names (')

            for boundary_name in self.boundary_names:
                control_dict_file.write(boundary_name + ' ')

            control_dict_file.write(');\n\n')
            control_dict_file.write('functions\n{\n')

            for boundary_name in self.boundary_names:
                control_dict_file.write(f'PRESSURE_{boundary_name}\n'
                                        f'{{\n'
                                        f'type  	 surfaceRegion;\n'
                                        f'libs 	 ("libfieldFunctionObjects.so");\n'
                                        f'executeControl 	 timeStep;\n'
                                        f'executeInterval 	 1;\n'
                                        f'writeControl 	 timeStep;\n'
                                        f'writeInterval 	 1;\n'
                                        f'timeFormat 	 fixed;\n'
                                        f'timePrecision 	 {self.time_precision};\n'
                                        f'operation 	 none;\n'
                                        f'writeFields 	 true;\n'
                                        f'surfaceFormat 	 raw;\n'
                                        f'regionType 	 patch;\n'
                                        f'name 	 {boundary_name};\n'
                                        f'fields (p);\n'
                                        f'}}\n')
                control_dict_file.write(f'wallShearStress\n'
                                        f'{{\n'
                                        f'type  	 wallShearStress;\n'
                                        f'libs 	 ("libfieldFunctionObjects.so");\n'
                                        f'executeControl 	 timeStep;\n'
                                        f'executeInterval 	 1;\n'
                                        f'writeControl 	 timeStep;\n'
                                        f'writeInterval 	 1;\n'
                                        f'timeFormat 	 fixed;\n'
                                        f'timePrecision 	 {self.time_precision};\n'
                                        f'log 	 false;\n'
                                        f'}}\n')
                control_dict_file.write(f'TRACTION_{boundary_name}\n'
                                        f'{{\n'
                                        f'type  	 surfaceRegion;\n'
                                        f'libs 	 ("libfieldFunctionObjects.so");\n'
                                        f''f'executeControl 	 timeStep;\n'
                                        f'executeInterval 	 1;\n'
                                        f'writeControl 	 timeStep;\n'
                                        f'writeInterval 	 1;\n'
                                        f'timeFormat 	 fixed;\n'
                                        f'timePrecision 	 {self.time_precision};\n'
                                        f'operation 	 none;\n'
                                        f'writeFields 	 true;\n'
                                        f'surfaceFormat 	 raw;\n'
                                        f'regionType 	 patch;\n'
                                        f'name 	 {boundary_name};\n'
                                        f'fields ( wallShearStress);\n'
                                        f'}}\n')
            control_dict_file.write('}')
        self.write_footer(file_name)

    def write_residuals_fileheader(self):
        header = '#  Step'
        for var in self.residual_variables:
            header += ' ' * self.write_precision + var
        with open(self.res_filepath, 'w') as f:
            f.write('# Residuals\n')
            f.write(header + '\n')

    def write_and_plot_of_residuals(self):
        log_filepath = os.path.join(self.working_directory, f'log.{self.application}')
        if os.path.isfile(log_filepath):
            with open(log_filepath, 'r') as f:
                log_string = f.read()
            time_start_string = f'Time = {self.prev_timestamp}'
            time_end_string = f'Time = {self.cur_timestamp}'
            match = re.search(time_start_string + r'(.*)' + time_end_string, log_string, flags=re.S)
            if not match is None:
                time_block = match.group(1)
                iteration_block_list = re.findall(
                    r'Coupling iteration = \d+' + r'(.*?)' + r'Coupling iteration \d+ end', time_block, flags=re.S)
                for iteration_block in iteration_block_list:
                    with open(self.res_filepath, 'a') as f:
                        f.write(str(self.step) + ' ' * self.write_precision)
                    for variable in self.residual_variables:
                        search_string = f'Solving for {variable}, Initial residual = ' + r'(' + of_io.float_pattern + r')'
                        var_residual_list = re.findall(search_string, iteration_block)
                        if var_residual_list:
                            # last initial residual of pimple loop
                            var_residual = float(var_residual_list[-1])
                        else:
                            raise RuntimeError(f'Variable: {variable} equation is not solved in {self.application}')

                        with open(self.res_filepath, 'a') as f:
                            f.write(str(var_residual) + ' ' * self.write_precision)
                    with open(self.res_filepath, 'a') as f:
                        f.write('\n')
                    self.step += 1
                if self.plot_of_residuals:
                    self.plot_of_residuals_process = subprocess.Popen('foamMonitor -l residuals.dat',
                                                                      cwd=self.working_directory, shell=True)
                    self.plot_of_residuals = False
