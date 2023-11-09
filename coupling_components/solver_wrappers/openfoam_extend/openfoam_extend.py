from coconut import data_structure
from coconut.coupling_components.component import Component
from coconut.data_structure.interface import Interface
from coconut import tools
from coconut.coupling_components.solver_wrappers.openfoam import openfoam_io as of_io
from scipy.interpolate import interp1d
from scipy import interpolate

from subprocess import check_call
import numpy as np
import os
import shutil
import time
import subprocess
import re
import copy
from glob import glob
import matplotlib.pyplot as plt


#TODO:wrappper is not adapted to run in parallel

def create(parameters):
    return SolverWrapperOpenFOAMExtend(parameters)


class SolverWrapperOpenFOAMExtend(Component):
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
        self.number_of_timesteps = self.settings['number_of_timesteps']
        self.application = self.settings['application']
        self.delta_t = self.settings['delta_t']
        self.time_precision = self.settings['time_precision']
        # self.save_restart = self.settings['save_restart']
        self.start_time = self.settings['timestep_start'] * self.delta_t
        self.die_min = self.settings['axial_coordinate_die_min']
        self.die_max = self.settings['axial_coordinate_die_max']
        self.slot = self.settings['slot_start_FSI']
        self.timestep = self.physical_time = self.iteration = self.cur_timestamp = self.prev_timestamp = None
        self.openfoam_extend_process = None
        self.write_interval = self.write_precision = None
        # boundary_names is the set of boundaries in Foam-Extend used for coupling
        self.boundary_names = self.settings['boundary_names']
        self.cores = None
        self.model = None
        self.interface_input = None
        self.interface_output = None
        # print(self.working_directory)
        # set on True to save copy of input and output files in every iteration
        self.debug = self.settings.get('debug', False)

        # set on True if you want to clean the adapted application and compile.
        self.compile_clean = self.settings.get('compile_clean', False)

        # remove possible CoCoNuT-message from previous interrupt
        self.remove_all_messages()

        # time
        self.init_time = self.init_time
        self.run_time = 0.0

        # residual variables
        self.residual_variables = ['res','rel res', 'material res']
        self.res_filepath = os.path.join(self.working_directory, 'residuals.csv')
        self.mp_in_decompose_seq_dict = {}
        self.mp_out_reconstruct_seq_dict = {}

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

        # if self.save_restart % self.write_interval:
        #     raise RuntimeError(
        #         f'self.save_restart (= {self.save_restart}) should be an integer multiple of writeInterval '
        #         f'(= {self.write_interval}). Modify the controlDict accordingly.')

        # creating Model
        self.model = data_structure.Model()

        # writeCellcentres writes cellcentres in internal field and face centres in boundaryField
        self.write_cell_centres()

        postProcess_path = os.path.join(self.working_directory, 'postProcessing')
        if not os.path.exists(postProcess_path):
            os.mkdir(postProcess_path)

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
            mp_input = self.model.create_model_part(f'{boundary}_input', x0, y0, z0, ids)
            mp_input.start_face = start_face
            mp_input.nfaces = nfaces

            # create output model part
            self.model.create_model_part(f'{boundary}_output', node_coords[:, 0], node_coords[:, 1], node_coords[:, 2],
                                         node_ids)

        # create interfaces
        self.interface_input = Interface(self.settings['interface_input'], self.model)
        self.interface_output = Interface(self.settings['interface_output'], self.model)
        self.test = copy.deepcopy(self.interface_output)

        # for item_output in self.interface_output.parameters:
        #     mp_output = self.interface_input.get_model_part(item_output['model_part'])
        # print("mp_output")
        # print(mp_output.x0,mp_output.y0,mp_output.z0)

        # Initialize timeVaryingMappedSolidTraction boundary condition
        for boundary in self.boundary_names:
            mp_name = f'{boundary}_input'
            mp = self.model.get_model_part(mp_name)
            x0, y0, z0 = mp.x0, mp.y0, mp.z0

            self.x0 = x0
            self.size_BC = self.x0.size
            angle = 1.25

            x = np.zeros( 2 * self.x0.size)
            y = np.zeros( 2 * self.x0.size)
            z = np.zeros( 2 * self.x0.size)

            j = 0

            for i in range(len(x)):
                if i < self.x0.size:
                    x[j] = self.x0[i]
                    y[j] = y0[i]*np.cos(angle*np.pi/180)
                    z[j] = y0[i] * - np.sin(angle * np.pi / 180)
                else:
                    x[j]= self.x0[i -self.x0.size]
                    y[j] = y0[i - self.x0.size] * np.cos(angle * np.pi / 180)
                    z[j] = y0[i - self.x0.size] * np.sin(angle * np.pi / 180)
                j+=1

            boundary_data_path = os.path.join(self.working_directory,'constant/boundaryData')
            if not os.path.exists(boundary_data_path):
                 os.mkdir(boundary_data_path)
            boundary_path = os.path.join(boundary_data_path, boundary)
            shutil.rmtree(boundary_path, ignore_errors = True)
            os.mkdir(boundary_path)
            data_folder = os.path.join(boundary_path,'0')
            os.mkdir(data_folder)

            with open(os.path.join(boundary_path, 'points'), 'w') as f:
                 f.write("""
            FoamFile
            {
                 version   2.0;
                 format    ascii;
                 class     vectorField;
                 object    points;
            }
            //*************************************************************************//\n""")
                 f.write('(\n')
                 for point in range(x.size):
                      f.write(f'({x[point]} {y[point]} {z[point]})\n')
                 f.write(')')


            with open(os.path.join(data_folder, 'pressure'), 'w') as g:
                g.write("""
            FoamFile
            {
                 version   2.0;
                 format    ascii;
                 class     scalarField;
                 object    pressure;
            }
            //*************************************************************************//\n""")
                g.write(f'{x.size}\n')
                g.write('(\n')
                for i in range(x.size):
                    g.write(f'{0}\n')
                g.write(')')

            with open(os.path.join(data_folder, 'traction'), 'w') as h:
                h.write("""
            FoamFile
            {
                 version   2.0;
                 format    ascii;
                 class     vectorField;
                 object    traction;
            }
            //*************************************************************************//\n""")
                h.write(f'{x.size}\n')
                h.write('(\n')
                for i in range(x.size):
                    h.write(f'({0} {0} {0} )\n')
                h.write(')')

            point_disp_data_path = os.path.join(self.working_directory)
            if not os.path.exists(point_disp_data_path):
                 os.mkdir(point_disp_data_path)

            with open(os.path.join(point_disp_data_path, 'dispPoint'), 'w') as f:
                 f.write("""
            FoamFile
            {
                 version   2.0;
                 format    ascii;
                 class     vectorField;
                 object    points;
            }
            //*************************************************************************//\n""")
                 f.write('(\n')
                 for point in range(x.size):
                      f.write(f'({x[point]} {y[point]} {z[point]})\n')
                 f.write(')')

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
                # number_of_timesteps + 1 to avoid problems with hi label in timeVaryingMappedSolidTraction boundary condition @ the end the simulation. This has no influence on the result.
                for i in range(self.number_of_timesteps + 1):
                    timestamp_i = self.delta_t *(i +1)
                    format_i = '{:.{}f}'.format(timestamp_i, self.time_precision)
                    str_i = str(format_i)
                    path_new_boundaryData_i = os.path.join(self.working_directory,'constant/boundaryData', boundary, str_i)
                    shutil.copytree(path_new_boundaryData, path_new_boundaryData_i)


        # if parallel do a decomposition and establish a remapping for the output based on the faceProcAddressing
        """Note concerning the sequence: The file ./processorX/constant/polyMesh/pointprocAddressing contains a list of 
        indices referring to the original index in the ./constant/polyMesh/points file, these indices go from 0 to 
        nPoints -1
        However, mesh faces can be shared between processors and it has to be tracked whether these are inverted or not
        This inversion is indicated by negative indices
        However, as minus 0 is not a thing, the indices are first incremented by 1 before inversion
        Therefore to get the correct index one should use |index|-1!!
        """

        if self.settings['parallel']:
            if self.start_time == 0:
                subprocess.check_call(f'decomposePar -force  &> log.decomposePar',
                                      cwd=self.working_directory, shell=True, env=self.env)

                for boundary in self.boundary_names:
                    mp_in_name = f'{boundary}_input'
                    mp_input = self.model.get_model_part(f'{boundary}_input')
                    nfaces = mp_input.size
                    b_file_name = os.path.join(self.working_directory, 'constant/polyMesh/boundary')
                    with open(b_file_name, 'r') as f:
                        b_lines = f.read()
                        b_dict = of_io.get_dict(b_lines, boundary)
                    start_face = of_io.get_int(input_string=b_dict, keyword='startFace')
                    self.mp_out_reconstruct_seq_dict[mp_in_name] = []
                    for p in range(self.cores):
                        path = os.path.join(self.working_directory,
                                            f'processor{p}/constant/polyMesh/faceProcAddressing')
                        with open(path, 'r') as f:
                            face_proc_add_string = f.read()
                        face_proc_add = np.abs(of_io.get_scalar_array(input_string=face_proc_add_string, is_int=True))
                        face_proc_add -= 1  # in openfoam face ids are incremented by 1
                        # print("face_proc_add")
                        # print(face_proc_add)
                        self.mp_out_reconstruct_seq_dict[mp_in_name] += (
                                    face_proc_add[(face_proc_add >= start_face) & (
                                            face_proc_add < start_face + nfaces)] - start_face).tolist()

                    if len(self.mp_out_reconstruct_seq_dict[mp_in_name]) != nfaces:
                        print(f'sequence: {len(mp_input.sequence)}')
                        print(f'nNodes: {mp_input.size}')
                        raise ValueError('Number of face indices in sequence does not correspond to number of faces')

                #initialize the different processors for the timeVaryingMappedSolidTraction BC
                mp_out_name = f'{boundary}_output'
                mp_output = self.model.get_model_part(mp_out_name)
                self.mp_in_decompose_seq_dict[mp_out_name] = {}
                # get the point sequence in the boundary for points in different processors
                for p in range(self.cores):
                    proc_dir = os.path.join(self.working_directory, f'processor{p}')
                    point_ids, points = of_io.get_boundary_points(proc_dir, '0', boundary)

                    if point_ids.size:
                        with open(os.path.join(proc_dir, 'constant/polyMesh/pointProcAddressing'), 'r') as f:
                            point_proc_add = np.abs(of_io.get_scalar_array(input_string=f.read(), is_int=True))
                        sorter = np.argsort(mp_output.id)
                        self.mp_in_decompose_seq_dict[mp_out_name][p] = sorter[
                            np.searchsorted(mp_output.id, point_proc_add[point_ids], sorter=sorter)]
                    else:
                        self.mp_in_decompose_seq_dict[mp_out_name][p] = None

                    path_working_directory_processor = os.path.join(self.working_directory, f'processor{p}')

                    self.write_cell_centres_parallel_timeVaryingMappedSolidTraction(path_working_directory_processor)

                    boundary_filename = os.path.join(self.working_directory, f'processor{p}/constant/polyMesh/boundary')
                    for boundary in self.boundary_names:
                        with open(boundary_filename, 'r') as boundary_file:
                            boundary_file_string = boundary_file.read()
                        boundary_dict = of_io.get_dict(input_string=boundary_file_string, keyword=boundary)
                        # get point ids and coordinates for all the faces in the boundary
                        # node_ids, node_coords = of_io.get_boundary_points(case_directory=self.working_directory/ f'processor{p}',
                        #                                                   time_folder='0',
                        #                                                   boundary_name=boundary)
                        nfaces = of_io.get_int(input_string=boundary_dict, keyword='nFaces')

                    x0, y0, z0 = self.read_face_centres_parallel_timeVaryingMappedSolidTraction(boundary, nfaces, p)

                    x_p = np.zeros(2 * x0.size)
                    y_p = np.zeros(2 * x0.size)
                    z_p = np.zeros(2 * x0.size)
                    index = int(len(x_p) / 2)

                    j = 0
                    for i in range(len(x_p)):
                        if i < len(x0):
                            x_p[j] = x0[i]
                            y_p[j] = y0[i] * np.cos(angle * np.pi / 180)
                            z_p[j] = - y0[i] * np.sin(angle * np.pi / 180)

                        else:
                            x_p[j] = x0[i - index]
                            y_p[j] = y0[i - index] * np.cos(angle * np.pi / 180)
                            z_p[j] = y0[i - index] * np.sin(angle * np.pi / 180)
                        j += 1

                    boundary_data_path = os.path.join(self.working_directory, f'processor{p}/constant/boundaryData')
                    if not os.path.exists(boundary_data_path):
                        os.mkdir(boundary_data_path)
                    boundary_path = os.path.join(boundary_data_path, boundary)
                    shutil.rmtree(boundary_path, ignore_errors=True)
                    os.mkdir(boundary_path)
                    data_folder = os.path.join(boundary_path, '0')
                    os.mkdir(data_folder)

                    with open(os.path.join(boundary_path, 'points'), 'w') as f:
                        f.write("""
                        FoamFile
                        {
                             version   2.0;
                             format    ascii;
                             class     vectorField;
                             object    points;
                        }
                        //*************************************************************************//\n""")

                        f.write('(\n')
                        for point in range(x_p.size):
                            f.write(f'({x_p[point]} {y_p[point]} {z_p[point]})\n')
                        f.write(')')

                    with open(os.path.join(data_folder, 'pressure'), 'w') as g:
                        g.write("""
                                  FoamFile
                                  {
                                       version   2.0;
                                       format    ascii;
                                       class     scalarField;
                                       object    pressure;
                                  }
                                  //*************************************************************************//\n""")

                        g.write(f'{x_p.size}\n')
                        g.write('(\n')
                        for i in range(x_p.size):
                            g.write(f'{0}\n')
                        g.write(')')

                    with open(os.path.join(data_folder, 'traction'), 'w') as h:
                        h.write("""
                                FoamFile
                                {
                                     version   2.0;
                                     format    ascii;
                                     class     vectorField;
                                     object    traction;
                                }
                                //*************************************************************************//\n""")
                        h.write(f'{x_p.size}\n')
                        h.write('(\n')
                        for i in range(x_p.size):
                            h.write(f'({0} {0} {0} )\n')
                        h.write(')')

                    timestamp = '{:.{}f}'.format(self.physical_time, self.time_precision)
                    path_orig_boundaryData = os.path.join(self.working_directory,
                                                          f'processor{p}/constant/boundaryData', boundary, '0')


                    # os.makedirs(path_orig_boundaryData)
                    path_new_boundaryData = os.path.join(self.working_directory,
                                                         f'processor{p}/constant/boundaryData', boundary,
                                                         timestamp)
                    shutil.rmtree(path_new_boundaryData, ignore_errors=True)
                    shutil.copytree(path_orig_boundaryData, path_new_boundaryData)
                    for i in range(self.number_of_timesteps + 1):
                        time = self.delta_t * (i + 1)
                        timestamp = '{:.{}f}'.format(time, self.time_precision)
                        new_path_boundaryData = os.path.join(self.working_directory,
                                                             f'processor{p}/constant/boundaryData',
                                                             boundary,
                                                             timestamp)
                        shutil.copytree(path_orig_boundaryData, new_path_boundaryData)

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

                if os.path.isdir(new_path):
                    if i == 0:
                        tools.print_info(f'Overwrite existing time step folder: {new_path}', layout='warning')
                    subprocess.check_call(f'rm -rf {new_path}', shell=True)

                for boundary in self.boundary_names:
                    new_path_boundaryData = os.path.join(self.working_directory, f'processor{i}/constant/boundaryData',
                                                         boundary,
                                                         self.cur_timestamp)
                if os.path.isdir(new_path):
                    if i == 0:
                        tools.print_info(f'Overwrite existing time step folder: {new_path}', layout='warning')
                    check_call(f'rm -rf {new_path}', shell=True)

                if os.path.isdir(new_path_boundaryData):
                    if i == 0:
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
        if True: #self.debug:
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

        # read data from OpenFOAM
        self.read_node_output()

        # copy output data for debugging
        if True: #self.debug:
            for boundary in self.boundary_names:
                # specify location of displacement
                disp_name = 'DISP_' + boundary
                pointDisp_name = 'POINT_DISP_' + boundary
                disp_filepath = os.path.join(self.working_directory, self.cur_timestamp, 'U')
                disp_iter_filepath = os.path.join(self.working_directory, 'postProcessing', disp_name, 'surface',
                                                  self.cur_timestamp, f'U_{self.iteration}')
                if not os.path.exists(disp_iter_filepath):
                    os.makedirs(disp_iter_filepath)
                shutil.copy(disp_filepath, disp_iter_filepath)

                mp_name = f'{boundary}_output'
                mp = self.model.get_model_part(mp_name)
                point_disp_name_path = os.path.join(self.working_directory, 'dispPoint')
                point_disp_iter = os.path.join(
                    os.path.join(self.working_directory, 'postProcessing', pointDisp_name, 'surface',
                                 self.cur_timestamp, f'dispPoint_{self.iteration}'))
                if not os.path.exists(point_disp_iter):
                    os.makedirs(point_disp_iter)
                shutil.copy(point_disp_name_path, point_disp_iter)
                disp = self.interface_output.get_variable_data(mp_name, 'displacement')

                with open(os.path.join(point_disp_iter, 'dispPoint'), 'w') as f:
                    f.write('')
                    for point in range(mp.x0.size):
                        f.write(f'{mp.x0[point]} {disp[point, 1]} {disp[point, 2]}\n')

                # specify location of yield
                # yield_name = 'YIELD_' + boundary
                # sigmaY_name = 'sigma_Y_' + boundary
                # yield_filepath = os.path.join(self.working_directory, self.cur_timestamp, 'sigmaY')
                # yield_iter_filepath = os.path.join(self.working_directory, 'postProcessing', yield_name,
                #                                   'surface',
                #                                   self.cur_timestamp, f'sigmaY_{self.iteration}')
                # if not os.path.exists(yield_iter_filepath):
                #     os.makedirs(yield_iter_filepath)
                # shutil.copy(yield_filepath, yield_iter_filepath)

                velocity_name = 'VELOCITY_' + boundary
                velocity_filepath = os.path.join(self.working_directory, self.cur_timestamp, 'Velocity')
                velocity_iter_filepath = os.path.join(self.working_directory, 'postProcessing', velocity_name,
                                                   'surface',
                                                   self.cur_timestamp, f'Velocity_{self.iteration}')
                if not os.path.exists(velocity_iter_filepath):
                    os.makedirs(velocity_iter_filepath)
                shutil.copy(velocity_filepath, velocity_iter_filepath)

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

        # if self.residual_variables is not None:
        #     self.write_of_residuals()

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
        solver_dir = os.path.join(os.path.dirname(__file__), f'v{self.version.replace(".", "")}', self.application)
        boundary_cond_dir = os.path.join(os.path.dirname(__file__), f'v{self.version.replace(".", "")}', 'coconut_src',
                                         'boundaryConditions')
        try:
            if self.compile_clean:
                subprocess.check_call(f'wmake {solver_dir} &> log.wmake', cwd=self.working_directory, shell=True, env=self.env)
                subprocess.check_call(
                    f'wclean {boundary_cond_dir} && wmake libso {boundary_cond_dir} &> log.wmake_libso',
                    cwd=self.working_directory, shell=True,
                    env=self.env)

            else:
                subprocess.check_call(f'wmake {solver_dir} &> log.wmake', cwd=self.working_directory, shell=True,
                                      env=self.env)
                subprocess.check_call(f'wmake libso {boundary_cond_dir} &> log.wmake_libso',
                                      cwd=self.working_directory, shell=True,
                                      env=self.env)

        except subprocess.CalledProcessError:
            raise RuntimeError(
                f'Compilation of {self.application} or coconut_src failed. Check {os.path.join(self.working_directory, "log.wmake or CSM/log.wmake_libso")}')

    # def write_cell_centres(self):
    #     raise NotImplementedError('Base class method is called, should be implemented in derived class')

    # def read_face_centres(self, boundary_name, nfaces):
    #     raise NotImplementedError('Base class method is called, should be implemented in derived class')

    def delete_prev_iter_output(self):
        # displacement file is removed to avoid foam-Extend to append data in the new iteration
        for boundary in self.boundary_names:
            # specify location of displacement
            # displacement_name = 'DISPLACEMENT_' + boundary
            # disp_file = os.path.join(self.working_directory, 'postProcessing', displacement_name, 'surface',
            #                         self.cur_timestamp, f'DU_patch_{boundary}.raw')
            # if os.path.isfile(disp_file):
            #     os.remove(disp_file)
            displacement_name = os.path.join(self.working_directory, self.cur_timestamp, 'U')
            # velocity_name = os.path.join(self.working_directory, self.timestep, 'Velocity')
            if os.path.isfile(displacement_name):
                os.remove(displacement_name)
            # if os.path.isfile(velocity_name):
            #     os.remove(velocity_name)


    def read_node_output(self):
        """
        This wrapper is initial written for a sliding FSI interface. The read node output function consist for now out of 2 variables.
        1 collomn is velocity in axial direction. colomn 2 and 3 consist of displacement. Modificiactions will be executed in the future.
        :return:
        """

        # specify location of displacement
        for boundary in self.boundary_names:
            mp_name = f'{boundary}_output'
            mp = self.model.get_model_part(mp_name)
            nfaces = mp.size

            if self.settings['parallel']:
                check_call(f'reconstructPar -time {self.cur_timestamp}  -fields ' "'(U)'"' &> log.reconstructPar;',
                           cwd=self.working_directory, shell=True, env=self.env)
                check_call(f'reconstructPar -time {self.cur_timestamp}  -fields ' "'(Velocity)'"' &> log.reconstructPar;',
                           cwd=self.working_directory, shell=True, env=self.env)
                for p in range(self.cores):
                    path_working_directory_processor = os.path.join(self.working_directory, f'processor{p}')
                    self.write_cell_centres_parallel_timeVaryingMappedSolidTraction(path_working_directory_processor)
                    self.read_face_centres_parallel_timeVaryingMappedSolidTraction(boundary,nfaces,p)
                check_call(f'reconstructPar -time {self.cur_timestamp}  -fields ' "'(ccx)'"' &> log.reconstructPar;',
                    cwd=self.working_directory, shell=True, env=self.env)
                check_call(f'reconstructPar -time {self.cur_timestamp}  -fields ' "'(ccy)'"' &> log.reconstructPar;',
                           cwd=self.working_directory, shell=True, env=self.env)
                check_call(f'reconstructPar -time {self.cur_timestamp}  -fields ' "'(ccz)'"' &> log.reconstructPar;',
                           cwd=self.working_directory, shell=True, env=self.env)

            self.write_cell_centres()

            filename_displacement = os.path.join(self.working_directory, self.cur_timestamp, 'U')
            filename_velocity = os.path.join(self.working_directory, self.cur_timestamp, 'Velocity')

            disp_field = of_io.get_boundary_field(file_name = filename_displacement, boundary_name = boundary,
                                                     size = nfaces, is_scalar =False)
            velo_field = of_io.get_boundary_field(file_name=filename_velocity, boundary_name=boundary,
                                                       size=nfaces, is_scalar=False)

            x, y, z = self.read_face_centres(boundary, nfaces)

            arr_test = np.array([x,y,velo_field[:,0],disp_field[:,1]])
            sorted = arr_test[:, arr_test[0].argsort()]
            sorted = np.transpose(sorted)
            x_bis = sorted[:,0]
            y_bis = sorted[:,1]
            z_bis = sorted[:,1] * np.sin(np.radians(2.5))
            velo_axial = sorted[:,2]
            # As the timestep for the wiredrawing case is very small, it is hard to get the wire stable, which is detrimental for the FSI calculations.
            # This is the reason why a first amount of timesteps no displacements are transferred
            if (self.timestep > self.slot):
                disp_rad = sorted[:,3]
                disp_z = sorted[:,3]* np.sin(np.radians(2.5))
            else:
                disp_rad = sorted[:, 3] * 0
                disp_z = sorted[:, 3] * np.sin(np.radians(2.5)) * 0
            mp_out = np.zeros((len(x_bis) * 2, 3))
            displacement = np.zeros((len(x_bis) * 2, 3))

            #creating new mp for output
            j =0
            for i in range(len(x_bis)):
                for k in range(2):
                    if k == 0:
                        mp_out[j, 0] = x_bis[i]
                        mp_out[j, 1] = y_bis[i]
                        mp_out[j, 2] = - z_bis[i]
                        j+=1
                    else:
                        mp_out[j, 0] = x_bis[i]
                        mp_out[j, 1] = y_bis[i]
                        mp_out[j, 2] = z_bis[i]
                        j+=1

            ids_out = np.arange(len(x_bis) * 2)

            #creating modified velocity-displacement field to transfer towards fluid domain
            l = 0
            for m in range(len(x_bis)):
                for n in range(2):
                    if n == 0:
                        displacement[l, 0] = velo_axial[m]
                        displacement[l, 1] = disp_rad[m]
                        displacement[l, 2] = - disp_z[m]
                        l += 1
                    else:
                        displacement[l, 0] = velo_axial[m]
                        displacement[l, 1] = disp_rad[m]
                        displacement[l, 2] = disp_z[m]
                        l += 1

            mask = np.logical_and(mp_out[:, 0] > self.die_min, mp_out[:, 0] < self.die_max)
            filter_node_ids = ids_out[mask]
            filter_node_coords = mp_out[mask, :]
            displacement_mask = displacement[mask, :]

            displacement_mask[:, 0] = displacement_mask[:, 0] * 1e-5

            self.model.delete_model_part(mp_name)
            self.model.create_model_part(mp_name, filter_node_coords[:, 0], filter_node_coords[:, 1],
                                                  filter_node_coords[:, 2], filter_node_ids)

            self.interface_output = Interface(self.settings['interface_output'],self.model)
            self.interface_output.set_variable_data(mp_name, 'displacement', displacement_mask)


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
            mp_name = f'{boundary}_input'
            mp_name_out = f'{boundary}_output'

            mp = self.model.get_model_part(mp_name_out)
            self.x0_p, self.y0_p, self.z0_p = mp.x0, mp.y0, mp.z0

            pressure = self.interface_input.get_variable_data(mp_name, 'pressure')

            pressure = list(np.array(pressure).reshape(-1,))
            x = np.linspace(1,len(pressure),len(pressure))
            f =interp1d(x,pressure)
            # plt.scatter(x,pressure)

            xnew = np.linspace(1,len(pressure),self.size_BC)
            # print(xnew)
            pressure = f(xnew)
            #getting pressure for parallel running
            # x_proc = np.linspace(1, len(pressure), int(self.x0_p.size / 2))
            x_proc = np.linspace(1, len(pressure), int(246/ 2))# hard coded_MATHIEU
            pressure_in_para = f(x_proc)

            # plt.plot(x_proc,pressure_in_para)
            # plt.show()
            # print("pressure")
            # print(pressure)
            traction = self.interface_input.get_variable_data(mp_name, 'traction')
            g = interp1d(x,traction[:,0])
            h = interp1d(x,traction[:,1])
            k = interp1d(x,traction[:,2])
            traction_new = np.zeros([self.size_BC,3])
            traction_new[:,0] = g(xnew)
            traction_new[:,1] = h(xnew)
            traction_new[:,2] = k(xnew)

            # traction_in_para = np.zeros([int(self.x0_p.size / 2), 3])
            traction_in_para = np.zeros([int(246/ 2), 3]) #hard coded_MATHIEU
            traction_in_para[:, 0] = g(x_proc)
            traction_in_para[:, 1] = h(x_proc)
            traction_in_para[:, 2] = k(x_proc)

            data_folder_home = os.path.join(self.working_directory,'constant/boundaryData', boundary, self.cur_timestamp)
            os.makedirs(data_folder_home, exist_ok = True)

            pressure_in = np.zeros((2 * pressure.size))
            traction_in = np.zeros((2 * traction_new.shape[0],3))

            if (self.timestep > self.slot):

                k = 0
                for i in range(len(pressure_in)):
                    if i < pressure.size:
                        pressure_in[k] = pressure[i]

                    else:
                        pressure_in[k] = pressure[i - pressure.size]
                    k += 1

                l = 0
                for i in range(traction_in.shape[0]):
                    if i < traction_new.shape[0]:
                        traction_in[l] = traction_new[i]
                    else:
                        traction_in[l] = traction_new[i - traction_new.shape[0]]
                    l += 1

                with open(os.path.join(data_folder_home,'pressure'),'w') as f:
                    f.write("""
                    FoamFile
                    {
                         version   2.0;
                         format    ascii;
                         class     scalarField;
                         object    values;
                    }
                    //***********************************************************************// //\n
                    """)
                    f.write(f'{pressure_in.shape[0]}\n')
                    f.write('(\n')
                    for i in range(pressure_in.size):
                        f.write(f'{pressure_in[i]}\n')
                    f.write(')')

                with open(os.path.join(data_folder_home,'traction'),'w') as f:
                    f.write("""
                    FoamFile
                    {
                         version   2.0;
                         format    ascii;
                         class     vectorField;
                         object    values;
                    }
                    //***********************************************************************// //\n
                    """)
                    f.write(f'{traction_in.shape[0]}\n')
                    f.write('(\n')
                    for i in range(traction_in.shape[0]):
                        f.write(f'({traction_in[i,0]} {traction_in[i,1]} {traction_in[i,2]})\n')
                    f.write(')')
            else:
                with open(os.path.join(data_folder_home, 'pressure'), 'w') as g:
                    g.write("""
                FoamFile
                {
                     version   2.0;
                     format    ascii;
                     class     scalarField;
                     object    pressure;
                }
                //*************************************************************************//\n""")
                    g.write(f'{pressure_in.shape[0]}\n')
                    g.write('(\n')
                    for i in range(pressure_in.size):
                        g.write(f'{0}\n')
                    g.write(')')

                with open(os.path.join(data_folder_home, 'traction'), 'w') as h:
                    h.write("""
                FoamFile
                {
                     version   2.0;
                     format    ascii;
                     class     vectorField;
                     object    traction;
                }
                //*************************************************************************//\n""")
                    h.write(f'{traction_in.shape[0]}\n')
                    h.write('(\n')
                    for i in range(traction_in.shape[0]):
                        h.write(f'({0} {0} {0} )\n')
                    h.write(')')

            if self.settings['parallel']:
                pressure_input_para = np.zeros(2 * pressure_in_para.size)
                traction_input_para = np.zeros([2 * traction_in_para.shape[0],3])

                # print(pressure_in_para)
                if (self.timestep > self.slot):

                    k = 0
                    for i in range(len(pressure_input_para)):
                        if i < pressure_in_para.size:
                            pressure_input_para[k] = pressure_in_para[i]
                        else:
                            pressure_input_para[k] = pressure_in_para[i - pressure_in_para.size]
                        k += 1

                    l = 0
                    for i in range(traction_input_para.shape[0]):
                        if i < traction_in_para.shape[0]:
                            traction_input_para[l] = traction_in_para[i]
                        else:
                            traction_input_para[l] = traction_in_para[i - traction_in_para.shape[0]]
                        l += 1

                    with open(os.path.join(data_folder_home, 'pressure'), 'w') as f:
                        f.write("""
                        FoamFile
                        {
                             version   2.0;
                             format    ascii;
                             class     scalarField;
                             object    values;
                        }
                        //***********************************************************************// //\n
                        """)
                        f.write(f'{pressure_input_para.shape[0]}\n')
                        f.write('(\n')
                        for i in range(pressure_input_para.size):
                            f.write(f'{pressure_input_para[i]}\n')
                        f.write(')')

                    with open(os.path.join(data_folder_home, 'traction'), 'w') as f:
                        f.write("""
                        FoamFile
                        {
                             version   2.0;
                             format    ascii;
                             class     vectorField;
                             object    values;
                        }
                        //***********************************************************************// //\n
                        """)
                        f.write(f'{traction_input_para.shape[0]}\n')
                        f.write('(\n')
                        for i in range(traction_input_para.shape[0]):
                            f.write(f'({traction_input_para[i, 0]} {traction_input_para[i, 1]} {traction_input_para[i, 2]})\n')
                        f.write(')')

                for proc in range(self.cores):

                    seq = self.mp_in_decompose_seq_dict[mp_name_out][proc]

                    data_folder = os.path.join(self.working_directory, f'processor{proc}', 'constant/boundaryData',boundary, self.cur_timestamp)

                    pressure_input_proc = pressure_input_para[seq]
                    traction_input_proc = traction_input_para[seq]

                    with open(os.path.join(data_folder, 'pressure'), 'w') as f:
                        f.write("""
                                       FoamFile
                                       {
                                            version   2.0;
                                            format    ascii;
                                            class     scalarField;
                                            object    values;
                                       }
                                       //***********************************************************************// //\n
                                       """)
                        f.write(f'{pressure_input_proc.shape[0]}\n')
                        f.write('(\n')
                        for i in range(pressure_input_proc.size):
                            f.write(f'{pressure_input_proc[i]}\n')
                        f.write(')')

                    with open(os.path.join(data_folder, 'traction'), 'w') as f:
                        f.write("""
                                       FoamFile
                                       {
                                            version   2.0;
                                            format    ascii;
                                            class     vectorField;
                                            object    values;
                                       }
                                       //***********************************************************************// //\n
                                       """)
                        f.write(f'{traction_input_proc.shape[0]}\n')
                        f.write('(\n')
                        for i in range(traction_input_proc.shape[0]):
                            f.write(f'({traction_input_proc[i, 0]} {traction_input_proc[i, 1]} {traction_input_proc[i, 2]})\n')
                        f.write(')')

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
        wait_time_lim = 10000 * 60  # 10000 minutes maximum waiting time for a single flow solver iteration
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
        #TODO: Make it general for each foam-extend version
        if version_nr[:-10] != self.version:
            raise RuntimeError(
                f'Foam-Extend-{self.version} should be loaded! Currently, Foam-Extend-{version_nr[:-10]} is loaded')

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
            control_dict = re.sub(r'timeFormat' + of_io.delimter + r'\w+', f'timeFormat fixed',
                                  control_dict)
        control_dict = re.sub(r'application' + of_io.delimter + r'\w+', f'{"application":<16}{self.application}',
                              control_dict)
        control_dict = re.sub(r'startTime' + of_io.delimter + of_io.float_pattern,
                              f'{"startTime":<16}{self.start_time}', control_dict)
        control_dict = re.sub(r'deltaT' + of_io.delimter + of_io.float_pattern, f'{"deltaT":<16}{self.delta_t}',
                              control_dict)
        control_dict = re.sub(r'timePrecision' + of_io.delimter + of_io.int_pattern,
                              f'{"timePrecision":<16}{self.time_precision}',
                              control_dict)
        control_dict = re.sub(r'endTime' + of_io.delimter + of_io.float_pattern, f'{"endTime":<16}1e15', control_dict)

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

            # for boundary_name in self.boundary_names:
            #     control_dict_file.write(self.displacement_dict(boundary_name))
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
                    for i, residual_variable in enumerate(self.residual_variables):
                        search_string = f'{residual_variable} = ({of_io.float_pattern}))'
                        var_residual_list = re.findall(search_string, iteration_block)
                        if var_residual_list:
                            # last initial residual of pimple loop
                            var_residual = float(var_residual_list[-1])
                            residual_array[i] = var_residual
                        else:
                            raise RuntimeError(f'Variable: {residual_variable} equation is not solved in {self.application}')

                    with open(self.res_filepath, 'a') as f:
                        np.savetxt(f, [residual_array], delimiter=', ')

    def write_cell_centres(self):
        if self.timestep:
            check_call('writeCellCentres -time ' + self.cur_timestamp + ' &> log.writeCellCentres;',
                       cwd=self.working_directory, shell=True,
                       env=self.env)
        else:
            check_call('writeCellCentres -time 0' + ' &> log.writeCellCentres;',
                       cwd=self.working_directory, shell=True,
                       env=self.env)

    def write_cell_centres_parallel_timeVaryingMappedSolidTraction(self, processor_directory):
        if self.timestep:
            for p in range(self.cores):
                check_call('writeCellCentres -time ' + self.cur_timestamp + ' &> log.writeCellCentres;', cwd=processor_directory,
                           shell=True, env=self.env)

        else:
            for p in range(self.cores):
                check_call('writeCellCentres -time 0 &> log.writeCellCentres;', cwd=processor_directory,
                   shell=True, env=self.env)


    def read_face_centres(self, boundary_name, nfaces):
        if self.timestep:
            filename_ccx = os.path.join(self.working_directory, self.cur_timestamp,'ccx')
            filename_ccy = os.path.join(self.working_directory, self.cur_timestamp,'ccy')
            filename_ccz = os.path.join(self.working_directory, self.cur_timestamp,'ccz')

            x = of_io.get_boundary_field(file_name=filename_ccx, boundary_name=boundary_name, size=nfaces,
                                         is_scalar=True)
            y = of_io.get_boundary_field(file_name=filename_ccy, boundary_name=boundary_name, size=nfaces,
                                         is_scalar=True)
            z = of_io.get_boundary_field(file_name=filename_ccz, boundary_name=boundary_name, size=nfaces,
                                         is_scalar=True)

        else:
            filename_ccx = os.path.join(self.working_directory,'0/ccx')
            filename_ccy = os.path.join(self.working_directory,'0/ccy')
            filename_ccz = os.path.join(self.working_directory,'0/ccz')

            x = of_io.get_boundary_field(file_name=filename_ccx, boundary_name=boundary_name, size=nfaces,
                                         is_scalar=True)
            y = of_io.get_boundary_field(file_name=filename_ccy, boundary_name=boundary_name, size=nfaces,
                                         is_scalar=True)
            z = of_io.get_boundary_field(file_name=filename_ccz, boundary_name=boundary_name, size=nfaces,
                                         is_scalar=True)

        return x, y, z

    def read_face_centres_parallel_timeVaryingMappedSolidTraction(self, boundary_name, nfaces, processor):
        if self.timestep:
            filename_ccx = os.path.join(self.working_directory, f'processor{processor}',self.cur_timestamp,'ccx')
            filename_ccy = os.path.join(self.working_directory, f'processor{processor}', self.cur_timestamp,'ccy')
            filename_ccz = os.path.join(self.working_directory, f'processor{processor}', self.cur_timestamp,'ccz')

            x = of_io.get_boundary_field(file_name=filename_ccx, boundary_name=boundary_name, size=nfaces,
                                         is_scalar=True)
            y = of_io.get_boundary_field(file_name=filename_ccy, boundary_name=boundary_name, size=nfaces,
                                         is_scalar=True)
            z = of_io.get_boundary_field(file_name=filename_ccz, boundary_name=boundary_name, size=nfaces,
                                         is_scalar=True)
        else:
            filename_ccx = os.path.join(self.working_directory, f'processor{processor}/0.0000000/ccx')
            filename_ccy = os.path.join(self.working_directory, f'processor{processor}/0.0000000/ccy')
            filename_ccz = os.path.join(self.working_directory, f'processor{processor}/0.0000000/ccz')

            x = of_io.get_boundary_field(file_name=filename_ccx, boundary_name=boundary_name, size=nfaces, is_scalar=True)
            y = of_io.get_boundary_field(file_name=filename_ccy, boundary_name=boundary_name, size=nfaces, is_scalar=True)
            z = of_io.get_boundary_field(file_name=filename_ccz, boundary_name=boundary_name, size=nfaces, is_scalar=True)

        return x, y, z