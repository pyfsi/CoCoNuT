from coconut import data_structure
from coconut.coupling_components.component import Component
from coconut.data_structure.interface import Interface
from coconut import tools
from coconut.coupling_components.solver_wrappers.openfoam import openfoam_io as of_io
from scipy import interpolate

from subprocess import check_call
import numpy as np
import os
import shutil
import time
import subprocess
import re


#TODO:wrappper is not adapt to run in parallel

def create(parameters):
    return SolverWrapperopenfoamextend(parameters)


class SolverWrapperopenfoamextend(Component):
    version = None  # FOAM-Extend version with dot, e.g. 4.1 , set in sub-class

    @tools.time_initialize
    def __init__(self, parameters):
        super().__init__()

        if self.version is None:
            raise NotImplementedError(
                'Base class method called, class variable version needs to be set in the derived class')

        # settings
        self.settings = parameters['settings']
        self.working_directory = self.settings['working_directory']
        self.env = None  # environment in which correct version of OpenFOAM software is available, set in sub-class
        # adapted application from openfoam ('coconut_<application name>')
        self.application = self.settings['application']
        self.delta_t = self.settings['delta_t']
        self.time_precision = self.settings['time_precision']
        self.start_time = self.settings['timestep_start'] * self.delta_t
        self.timestep = self.physical_time = self.iteration = self.cur_timestamp = self.prev_timestamp = None
        self.openfoam_extend_process = None
        self.write_interval = self.write_precision = None
        # boundary_names is the set of boundaries in Foam-Extend used for coupling
        self.boundary_names = self.settings['boundary_names']
        self.cores = None
        self.model = None
        self.interface_input = None
        self.interface_output = None

        # set on True to save copy of input and output files in every iteration
        self.debug = False

        # remove possible CoCoNuT-message from previous interrupt
        self.remove_all_messages()

        # time
        self.init_time = self.init_time
        self.run_time = 0.0

        # residual variables
        self.residual_variables = self.settings.get('residual_variables', None)
        self.res_filepath = os.path.join(self.working_directory, 'residuals.csv')

        if self.residual_variables is not None:
            self.write_residuals_fileheader()

    @tools.time_initialize
    def initialize(self):
        super().initialize()

        # check interface names in 'interface_input' and 'interface_output' with boundary names provided in
        # boundary_names
        self.check_interfaces()

        # obtain number of cores from self.working_directory/system/decomposeParDict
        self.cores = 1
        if self.settings['parallel']:
            file_name = os.path.join(self.working_directory, 'system/decomposeParDict')
            if not os.path.isfile(file_name):
                raise RuntimeError(
                    f'In the parameters:\n{self.settings}\n key "parallel" is set to {True} but {file_name} '
                    f'does not exist')
            else:
                with open(file_name, 'r') as file:
                    decomposedict_string = file.read()
                self.cores = of_io.get_int(input_string=decomposedict_string, keyword='numberOfSubdomains')

        # modify controlDict file to add displacement functionObjects for all the boundaries in
        # self.settings["boundary_names"]
        self.read_modify_controldict()

        # creating Model
        self.model = data_structure.Model()

        # writeCellcentres writes cellcentres in internal field and face centres in boundaryField
        self.write_cell_centres()

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

            x0, y0, z0 = self.read_face_centres(boundary, nfaces)
            ids = np.arange(0, nfaces)

            # create input model part
            mp_output = self.model.create_model_part(f'{boundary}_input', x0, y0, z0, ids)
            mp_output.start_face = start_face
            mp_output.nfaces = nfaces

            # create output model part
            self.model.create_model_part(f'{boundary}_output', node_coords[:, 0], node_coords[:, 1], node_coords[:, 2],
                                         node_ids)

        # create interfaces
        self.interface_input = Interface(self.settings['interface_input'], self.model)
        self.interface_output = Interface(self.settings['interface_output'], self.model)

        # define timestep and physical time
        self.timestep = 0
        self.physical_time = self.start_time

        # copy zero folder to folder with correctly named timeformat. This is also done for the mapped spatial BC
        if self.start_time == 0:
            timestamp = '{:.{}f}'.format(self.physical_time, self.time_precision)
            path_orig = os.path.join(self.working_directory, '0')
            path_new = os.path.join(self.working_directory, timestamp)
            shutil.rmtree(path_new, ignore_errors=True)
            shutil.copytree(path_orig, path_new)
            for boundary in self.boundary_names:
                path_orig_boundaryData = os.path.join(self.working_directory, 'constant/boundaryData', boundary, '0')
                path_new_boundaryData = os.path.join(self.working_directory,'constant/boundaryData', boundary, timestamp )
                shutil.rmtree(path_new_boundaryData, ignore_errors=True)
                shutil.copytree(path_orig_boundaryData, path_new_boundaryData)


        # if parallel do a decomposition and establish a remapping for the output based on the faceProcAddressing
        """Note concerning the sequence: The file ./processorX/constant/polyMesh/pointprocAddressing contains a list of 
        indices referring to the original index in the ./constant/polyMesh/points file, these indices go from 0 to 
        nPoints -1
        However, mesh faces can be shared between processors and it has to be tracked whether these are inverted or not
        This inversion is indicated by negative indices
        However, as minus 0 is not a thing, the indices are first incremented by 1 before inversion
        Therefore to get the correct index one should use |index|-1!!
        """

        # if self.settings['parallel']:
        #     if self.start_time == 0:
        #         check_call(f'decomposePar -force -time {self.start_time} &> log.decomposePar',
        #                    cwd=self.working_directory,
        #                    shell=True, env=self.env)
        #
        #     for boundary in self.boundary_names:
        #         mp_output = self.model.get_model_part(f'{boundary}_output')
        #         mp_output.sequence = []
        #         for p in range(self.cores):
        #             path = os.path.join(self.working_directory, f'processor{p}/constant/polyMesh/faceProcAddressing')
        #             with open(path, 'r') as f:
        #                 face_proc_add_string = f.read()
        #             face_proc_add = np.abs(of_io.get_scalar_array(input_string=face_proc_add_string, is_int=True))
        #             face_proc_add -= 1
        #
        #             mp_output.sequence += (face_proc_add[(face_proc_add >= mp_output.start_face) & (
        #                     face_proc_add < mp_output.start_face + mp_output.nfaces)] - mp_output.start_face).tolist()
        #
        #         np.savetxt(os.path.join(self.working_directory, f'sequence_{boundary}.txt'),
        #                    np.array(mp_output.sequence), fmt='%i')
        #
        #         if len(mp_output.sequence) != mp_output.nfaces:
        #             print(f'sequence: {len(mp_output.sequence)}')
        #             print(f'nNodes: {mp_output.size}')
        #             raise ValueError('Number of face indices in sequence does not correspond to number of faces')

        # starting the FOAM-Extend infinite loop for coupling!
        if not self.settings['parallel']:
            cmd = self.application + '&> log.' + self.application
        else:
            cmd = 'mpirun -np ' + str(self.cores) + ' ' + self.application + ' -parallel &> log.' + self.application

        self.openfoam_extend_process = subprocess.Popen(cmd, cwd=self.working_directory, shell=True, env=self.env)

    def initialize_solution_step(self):
        super().initialize_solution_step()

        # for parallel: create a folder with the correct time stamp for decomposition of pressure and traction
        # for serial: folder will normally be present, except for time 0: make a folder 0.0000 with specified precision
        timestamp = '{:.{}f}'.format(self.physical_time, self.time_precision)
        path = os.path.join(self.working_directory, timestamp)
        for boundary in self.boundary_names:
            path_boundaryData = os.path.join(self.working_directory, 'constant/boundaryData', boundary, timestamp)
        if self.cores > 1 or self.physical_time == 0:
            os.makedirs(path, exist_ok=True)
            os.makedirs(path_boundaryData, exist_ok=True)

        # prepare new time step folder and reset the number of iterations
        self.timestep += 1
        self.iteration = 0
        self.physical_time += self.delta_t

        self.prev_timestamp = timestamp
        self.cur_timestamp = f'{self.physical_time:.{self.time_precision}f}'

        if not self.settings['parallel']:  # if serial
            new_path = os.path.join(self.working_directory, self.cur_timestamp)
            for boundary in self.boundary_names:
                new_path_boundaryData = os.path.join(self.working_directory, 'constant/boundaryData', boundary, self.cur_timestamp)
            if os.path.isdir(new_path):
                tools.print_info(f'Overwrite existing time step folder: {new_path}', layout='warning')
                check_call(f'rm -rf {new_path}', shell=True)
            if os.path.isdir(new_path_boundaryData):
                tools.print_info(f'Overwrite existing time step folder: {new_path_boundaryData}', layout='warning')
                check_call(f'rm -rf {new_path_boundaryData}', shell=True)
            check_call(f'mkdir -p {new_path}', shell=True)
            check_call(f'mkdir -p {new_path_boundaryData}', shell=True)

        #TODO: Parallel running isn't checked yet! A prelimanary implementation has been done.
        else:
            for i in np.arange(self.cores):
                new_path = os.path.join(self.working_directory, 'processor' + str(i), self.cur_timestamp)
                for boundary in self.boundary_names:
                    new_path_boundaryData = os.path.join(self.working_directory,
                                                     'constant/boundaryData', boundary, self.cur_timestamp)
                if os.path.isdir(new_path):
                    if i == 0:
                        tools.print_info(f'Overwrite existing time step folder: {new_path}', layout='warning')
                    check_call(f'rm -rf {new_path}', shell=True)
                if os.path.isdir(new_path_boundaryData):
                    tools.print_info(f'Overwrite existing time step folder: {new_path_boundaryData}', layout='warning')
                    check_call(f'rm -rf {new_path_boundaryData}', shell=True)
                check_call(f'mkdir -p {new_path}', shell=True)
                check_call(f'mkdir -p {new_path_boundaryData}', shell=True)

        self.send_message('next')
        self.wait_message('next_ready')

    @tools.time_solve_solution_step
    def solve_solution_step(self, interface_input):
        self.iteration += 1

        # store incoming displacements
        self.interface_input.set_interface_data(interface_input.get_interface_data())

        # write interface data to OpenFOAM-file
        self.write_node_input()

        # copy input data for debugging
        if self.debug:
            for boundary in self.boundary_names:
                path_from_pressure = os.path.join(self.working_directory, 'constant/boundaryData', boundary,
                                                  self.cur_timestamp, 'pressure')
                path_to_pressure = os.path.join(self.working_directory, 'constant/boundaryData', boundary,
                                                self.cur_timestamp, f'pressure_{self.iteration}')
                shutil.copy(path_from_pressure, path_to_pressure)

                path_from_traction = os.path.join(self.working_directory, 'constant/boundaryData', boundary,
                                                  self.cur_timestamp, 'traction')
                path_to_traction = os.path.join(self.working_directory, 'constant/boundaryData', boundary,
                                                self.cur_timestamp, f'traction_{self.iteration}')
                shutil.copy(path_from_traction, path_to_traction)

        #     if self.cores > 1:
        #         for i in range(0, self.cores):
        #             path_from = os.path.join(self.working_directory, 'processor' + str(i), self.prev_timestamp,
        #                                      'pointDisplacement_Next')
        #             path_to = os.path.join(self.working_directory, 'processor' + str(i), self.prev_timestamp,
        #                                    'pointDisplacement_Next_Iter' + str(self.iteration))
        #             shutil.copy(path_from, path_to)
        #     else:
        #         path_from = os.path.join(self.working_directory, self.prev_timestamp, 'pointDisplacement_Next')
        #         path_to = os.path.join(self.working_directory, self.prev_timestamp,
        #                                'pointDisplacement_Next_Iter' + str(self.iteration))
        #         shutil.copy(path_from, path_to)

        self.delete_prev_iter_output()
        self.send_message('continue')
        self.wait_message('continue_ready')

        # copy output data for debugging
        if self.debug:
            for boundary in self.boundary_names:
                # specify location of displacement
                disp_filepath = os.path.join(self.working_directory, self.cur.timestamp, 'U')
                disp_iter_filepath = os.path.join(self.working_directory, self.cur_timestamp, f'U_{self.iteration}')
                shutil.copy(disp_filepath, disp_iter_filepath)

        # read data from OpenFOAM
        self.read_node_output()

        # return interface_output object
        return self.interface_output

    def finalize_solution_step(self):
        super().finalize_solution_step()

        # prev_timestep = self.timestep - 1
        # Propability not necessary. remove the folder that was used for pointDisplacement_Next if not in writeInterval
        # if self.settings['parallel']:
        #     dir_pointdisp_next = os.path.join(self.working_directory, self.prev_timestamp)
        #     shutil.rmtree(dir_pointdisp_next)
        #
        #     if prev_timestep % self.write_interval:
        #         for p in range(self.cores):
        #             prev_timestep_dir = os.path.join(self.working_directory, f'processor{p}/{self.prev_timestamp}')
        #             shutil.rmtree(prev_timestep_dir)
        # else:
        #     if prev_timestep % self.write_interval:
        #         dir_pointdisp_next = os.path.join(self.working_directory, self.prev_timestamp)
        #         shutil.rmtree(dir_pointdisp_next)

        if not (self.timestep % self.write_interval):
            self.send_message('save')
            self.wait_message('save_ready')

        if self.residual_variables is not None:
            self.write_of_residuals()

    def finalize(self):
        super().finalize()

        self.send_message('stop')
        self.wait_message('stop_ready')
        self.openfoam_extend_process.wait()

    def get_interface_input(self):
        return self.interface_input

    def get_interface_output(self):
        return self.interface_output

    def compile_adapted_openfoam_extend_solver(self):
        # compile foam-Extend adapted solver
        solver_dir = os.path.join(os.path.dirname(__file__), f'vFE{self.version.replace(".", "")}', self.application)
        try:
            check_call(f'wmake {solver_dir} &> log.wmake', cwd=self.working_directory, shell=True, env=self.env)
        except subprocess.CalledProcessError:
            raise RuntimeError(
                f'Compilation of {self.application} failed. Check {os.path.join(self.working_directory, "log.wmake")}')

    def write_cell_centres(self):
        raise NotImplementedError('Base class method is called, should be implemented in derived class')

    def read_face_centres(self, boundary_name, nfaces):
        raise NotImplementedError('Base class method is called, should be implemented in derived class')

    def delete_prev_iter_output(self):
        # displacement file is removed to avoid foam-Extend to append data in the new iteration
        for boundary in self.boundary_names:
            # specify location of displacement
            # displacement_name = 'DISPLACEMENT_' + boundary
            # disp_file = os.path.join(self.working_directory, 'postProcessing', displacement_name, 'surface',
            #                         self.cur_timestamp, f'DU_patch_{boundary}.raw')
            # if os.path.isfile(disp_file):
            #     os.remove(disp_file)
            displacement_name = os.path.join(self.working_directory, self.timestep, 'U')
            # velocity_name = os.path.join(self.working_directory, self.timestep, 'Velocity')
            if os.path.isfile(displacement_name):
                os.remove(displacement_name)
            # if os.path.isfile(velocity_name):
            #     os.remove(velocity_name)


    def read_node_output(self):
        """
        reads the pointDisplacement from the <case directory>/time step folders for serial and parallel. In
        case of parallel, it uses mp.sequence (using faceProcAddressing) to map the values to the face centres.

        :return:
        """

        for boundary in self.boundary_names:
            # specify location of displacement
            mp_name = f'{boundary}_output'
            mp = self.model.get_model_part(mp_name)
            nfaces = mp.size

            self.write_cell_centres()

            filename_displacement = os.path.join(self.working_directory, self.timestep, 'U')
            # filename_velocity = os.path.join(self.working_directory, self.timestep, 'Velocity')

            disp_filename = of_io.get_boundary_field(file_name = filename_displacement, boundary_name = boundary,
                                                     size = nfaces, is_scalar =False)
            # velo_filename = of_io.get_boundary_field(file_name=filename_velocity, boundary_name=boundary,
            #                                          size=nfaces, is_scalar=False)


            x, y, z = self.read_face_centres(boundary, nfaces)

            f = interpolate.interp1d(x,disp_filename[:,1])
            g = interpolate.interp1d(x, disp_filename[:,2])

            node_ids, node_coords = of_io.get_boundary_points(case_directory = self.working_directory,
                                                                                time_folder = self.timestep,
                                                          boundary_name = boundary)

            mask = np.logical_and(node_coords[:, 0] > -0.003, node_coords[:, 0] < 0.0005)
            filter_node_ids = node_ids[mask]
            filter_node_coords = node_coords[mask, :]


            displacement = np.zeros((len(filter_node_ids),3))

            displacement[:,1] = f(filter_node_coords[:,0])
            displacement[:,2] = g(filter_node_coords[:,0])

            self.model.delete_model_part(mp)

            self.model.create_model_part(mp_name, filter_node_coords[:, 0], filter_node_coords[:, 1],
                                                  filter_node_coords[:, 2], filter_node_ids)

            # check if the displacement file completed by foam-Extend and read data
            # self.check_output_file(disp_filename, nfaces)
            # disp_tmp = np.loadtxt(disp_filename, comments='#')[:, 3:]

            if self.settings['parallel']:
                pos_list = mp.sequence
            else:
                pos_list = [pos for pos in range(0, nfaces)]
            #
            # displacement = np.empty_like(disp_tmp)
            #
            # displacement[pos_list, ] = disp_tmp[:, ]

            self.interface_output.set_variable_data(mp_name, 'displacement', displacement)

    # noinspection PyMethodMayBeStatic
    def write_footer(self, file_name):
        # write OpenFOAM-footer at the end of file
        with open(file_name, 'a') as f:
            f.write('\n// ************************************************************************* //\n')

    def write_node_input(self):
        """
        creates pressure and traction files for supplying the pressure and traction fields in the FSI coupling. These files are created
        from constant/boundaryData/"boundary"/0/pressure or traction, specified by the timeVaryingMappedSolidTraction boundary condition. The boundary field for boundaries participating in the FSI coupling is modified to
        supply the boundary pressure and traction fields from fluid solver. If the foam-Extend solver is run in parallel,
        the field is subsequently decomposed using the command: decomposePar.
       :return:
       """
        for boundary in self.boundary_names:
            pressure_filename_ref = os.path.join(self.working_directory, 'constant/boundaryData', boundary, '0',
                                                 'pressure')
            traction_filename_ref = os.path.join(self.working_directory, 'constant/boundaryData', boundary, '0',
                                                 'traction')


            pressure_filename = os.path.join(self.working_directory, 'constant/boundaryData', boundary,
                                             self.cur_timestamp, 'pressure')
            traction_filename = os.path.join(self.working_directory, 'constant/boundaryData', boundary,
                                             self.cur_timestamp, 'traction')

            shutil.copy(pressure_filename_ref, pressure_filename)
            shutil.copy(traction_filename_ref, traction_filename)

            with open(pressure_filename_ref, 'r') as ref_file:
                pressure_string = ref_file.read()

            with open(traction_filename_ref, 'r') as ref_file:
                traction_string = ref_file.read()

            mp_name = f'{boundary}_input'
            pressure = self.interface_input.get_variable_data(mp_name, 'pressure')
            boundary_dict = of_io.get_dict(input_string=pressure_string, keyword=boundary)
            boundary_dict_new = of_io.update_vector_array_dict(dict_string=boundary_dict, vector_array=pressure)
            pressure_string = pressure_string.replace(boundary_dict, boundary_dict_new)

            traction = self.interface_input.get_variable_data(mp_name, 'traction')
            boundary_dict = of_io.get_dict(input_string=traction_string, keyword=boundary)
            boundary_dict_new = of_io.update_vector_array_dict(dict_string=boundary_dict, vector_array=traction)
            traction_string = traction_string.replace(boundary_dict, boundary_dict_new)

            with open(pressure_filename, 'w') as f:
                f.write(pressure_string)

            with open(traction_filename, 'w') as f:
                f.write(traction_string)

            # if self.settings['parallel']:
            #     check_call(f'decomposePar -fields -time {self.cur_timestamp} &> log.decomposePar;',
            #                cwd=self.working_directory, shell=True, env=self.env)

    # noinspection PyMethodMayBeStatic
    def check_output_file(self, filename, nfaces):
        counter = 0
        nlines = 0
        lim = 1000
        while (nlines < nfaces + 2) and counter < lim:
            if os.path.isfile(filename):
                with open(filename, 'r') as f:
                    nlines = sum(1 for _ in f)
            time.sleep(0.01)
            counter += 1
        if counter == lim:
            raise RuntimeError(f'Timed out waiting for file: {filename}')
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
                self.openfoam_extend_process.kill()
                self.openfoam_extend_process.wait()
                raise RuntimeError(f'CoCoNuT timed out in the OpenFOAM solver_wrapper, waiting for message: '
                                   f'{message}.coco')
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
        if check_call(self.application + ' -help &> checkSoftware', shell=True, env=self.env) != 0:
            raise RuntimeError(f'Foam-Extend not loaded properly. Check if the solver load commands for the "machine_name" are correct.')

        # check version
        with open('checkSoftware', 'r') as f:
            last_line = f.readlines()[-2]  # second last line contains 'Build: XX' with XX the version number
        os.remove('checkSoftware')
        version_nr = last_line.split(' ')[-1]
        if version_nr[:-1] != self.version:
            raise RuntimeError(
                f'Foam-Extend-{self.version} should be loaded! Currently, Foam-Extend-{version_nr[:-1]} is loaded')

    def check_interfaces(self):
        """
        checks the dictionaries from 'interface_input' and 'interface_output' in parameters.json file. The model part
        name must be the concatenation of an entry from `boundary_names` and the string `_input`, for 'interface_input'
        and for 'interface_output' it must be the concatenation of an entry from `boundary_names` and the string
        `_output`.
        :return:
        """
        input_interface_model_parts = [param['model_part'] for param in self.settings['interface_input']]
        output_interface_model_parts = [param['model_part'] for param in self.settings['interface_output']]
        boundary_names = self.settings['boundary_names']

        for boundary_name in boundary_names:
            if f'{boundary_name}_input' not in input_interface_model_parts:
                raise RuntimeError(
                    f'Error in json file: {boundary_name}_input not listed in "interface_input": '
                    f'{self.settings["interface_input"]}.\n. <boundary> in the "boundary_names" in json file should '
                    f'have corresponding <boundary>_input in "interface_input" list')

            if f'{boundary_name}_output' not in output_interface_model_parts:
                raise RuntimeError(
                    f'Error in json file: {boundary_name}_output not listed in "interface_output": '
                    f'{self.settings["interface_output"]}.\n. <boundary> in the "boundary_names" in json file should '
                    f'have corresponding <boundary>_output in "interface_output" list')

    def read_modify_controldict(self):
        """
        reads the controlDict file in the case-directory and modifies some entries required by the coconut_pimpleFoam.
        The values of these entries are taken from paramters.json file.
        :return:
        """

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
        control_dict = re.sub(r'endTime' + of_io.delimter + of_io.float_pattern, f'endTime    1e15', control_dict)

        # delete previously defined coconut functions
        coconut_start_string = '// CoCoNuT function objects'
        control_dict = re.sub(coconut_start_string + r'.*', '', control_dict, flags=re.S)

        with open(file_name, 'w') as control_dict_file:
            control_dict_file.write(control_dict)
            control_dict_file.write(coconut_start_string + '\n')
            control_dict_file.write('boundary_names (')

            for boundary_name in self.boundary_names:
                control_dict_file.write(boundary_name + ' ')

            control_dict_file.write(');\n\n')
            control_dict_file.write('functions\n{\n')

            for boundary_name in self.boundary_names:
                control_dict_file.write(self.displacement_dict(boundary_name))
            control_dict_file.write('}')
            self.write_footer(file_name)

    def displacement_dict(self, boundary_name):
        raise NotImplementedError('Base class method is called, should be implemented in derived class')

    def write_residuals_fileheader(self):
        header = ''
        sep = ', '
        with open(self.res_filepath, 'w') as f:
            f.write('# Residuals\n')
            for variable in self.residual_variables:
                header += variable + sep
            f.write(header.strip(sep) + '\n')

    def write_of_residuals(self):
        """
        it reads the log file generated by coconut_pimpleFoam solver and writes the last initial residual of the fields
        in the pimple iterations, for every coupling iteration. The fields should be given in the parameters.json file
        with the key-'residual_variables' and values-list(Foam-Extend variables), e.g. 'residual_variables': ['U', 'p']
        :return:
        """
        log_filepath = os.path.join(self.working_directory, f'log.{self.application}')
        if os.path.isfile(log_filepath):
            with open(log_filepath, 'r') as f:
                log_string = f.read()
            time_start_string = f'Time = {self.prev_timestamp}'
            time_end_string = f'Time = {self.cur_timestamp}'
            match = re.search(time_start_string + r'(.*)' + time_end_string, log_string, flags=re.S)
            if match is not None:
                time_block = match.group(1)
                iteration_block_list = re.findall(
                    r'Coupling iteration = \d+(.*?)Coupling iteration \d+ end', time_block, flags=re.S)
                for iteration_block in iteration_block_list:
                    residual_array = np.empty(len(self.residual_variables))
                    for i, variable in enumerate(self.residual_variables):
                        search_string = f'Solving for {variable}, Initial residual = ({of_io.float_pattern})'
                        var_residual_list = re.findall(search_string, iteration_block)
                        if var_residual_list:
                            # last initial residual of pimple loop
                            var_residual = float(var_residual_list[-1])
                            residual_array[i] = var_residual
                        else:
                            raise RuntimeError(f'Variable: {variable} equation is not solved in {self.application}')

                    with open(self.res_filepath, 'a') as f:
                        np.savetxt(f, [residual_array], delimiter=', ')

    def write_cell_centres(self):
        if self.timestep:
            check_call('writeCellCentres -time' + self.cur_timestamp + ' &> log.writeCellCentres;',
                       cwd=self.working_directory, shell=True,
                       env=self.env)
        else:
            check_call('writeCellCentres -time 0' + ' &> log.writeCellCentres;',
                       cwd=self.working_directory, shell=True,
                       env=self.env)


    def read_face_centres(self, boundary_name, nfaces):
        if self.timestep:
            filename_ccx = os.path.join(self.cur_timestamp,'ccx')
            filename_ccy = os.path.join(self.cur_timestamp,'ccy')
            filename_ccz = os.path.join(self.cur_timestamp,'ccz')

            x = of_io.get_boundary_field(file_name=filename_ccx, boundary_name=boundary_name, size=nfaces,
                                         is_scalar=True)
            y = of_io.get_boundary_field(file_name=filename_ccy, boundary_name=boundary_name, size=nfaces,
                                         is_scalar=True)
            z = of_io.get_boundary_field(file_name=filename_ccz, boundary_name=boundary_name, size=nfaces,
                                         is_scalar=True)

        else:
            filename_ccx = os.path.join('0/ccx')
            filename_ccy = os.path.join('0/ccy')
            filename_ccz = os.path.join('0/ccz')

            x = of_io.get_boundary_field(file_name=filename_ccx, boundary_name=boundary_name, size=nfaces,
                                         is_scalar=True)
            y = of_io.get_boundary_field(file_name=filename_ccy, boundary_name=boundary_name, size=nfaces,
                                         is_scalar=True)
            z = of_io.get_boundary_field(file_name=filename_ccz, boundary_name=boundary_name, size=nfaces,
                                         is_scalar=True)



        return x, y, z
