from coconut import data_structure
from coconut.coupling_components.component import Component
from coconut.coupling_components.interface import Interface
from coconut.coupling_components import tools

import os
from os.path import join
import subprocess
import time
import numpy as np
import re


def Create(parameters):
    return SolverWrapperAbaqus614(parameters)



class SolverWrapperAbaqus614(Component):
    def __init__(self, parameters):
        super().__init__()
        # settings
        """
               settings of solver_wrappers.abaqus.614:

                    working_directory       Absolute path to working directory
                                            or relative path w.r.t current directory
                    cores                   Number of cpus to be used by Abaqus
                    input_file              Name of the Abaqus input file (located in the directory where Python is 
                                            launched)
                    dimensions              dimensionality of the problem (2 or 3)
                    arraysize               declare a sufficiently large array size for load array in FORTRAN
                    CSM_dir                 relative path to directory for the files and execution of the structural 
                                            solver 
                    ramp                    Boolean: 0 for step load, 1 for ramp load in Abaqus
                    delta_t                 Time step size
                    timestep_start          Time step from which is to be started (initial = 0)
                    surface_IDS             List of the names of the surfaces that take part in the FSI, as they are 
                                            known by Abaqus
                    interface_input         Interface for the load points and their corresponding variables (pressure,
                                            traction).
                    interface_output        Interface for the output nodes and their corresponding variable(s)
                                            displacements)
                    mp_mode                 Mode of the parallel computing (currently only THREADS is accepted)
                    save_iterations         number of time steps between consecutive saves of Abaqus-files
        """

        self.settings = parameters['settings']
        self.dir_csm = join(os.getcwd(), self.settings['working_directory'].GetString())  # *** alternative for getcwd?
        path_src = os.path.realpath(os.path.dirname(__file__))

        self.cores = self.settings['cores'].GetInt()  # number of cpus Abaqus has to use
        self.dimensions = self.settings['dimensions'].GetInt()
        if self.dimensions == 2:
            tools.Print("Warning for Axisymmetric cases:\n\tIn Abaqus these have to be constructed around the y-axis. \n\tSwitching of x and y-coordinates might be necessary but should be accomplished by using an appropriate mapper.", layout='warning')
        self.array_size = self.settings["arraysize"].GetInt()
        self.delta_t = self.settings["delta_t"].GetDouble()
        self.timestep_start = self.settings["timestep_start"].GetDouble()
        self.surfaceIDs = [_.GetString() for _ in self.settings['surfaceIDs'].list()]
        self.n_surfaces = len(self.surfaceIDs)
        self.thread_ids = [i for i in range(0, self.n_surfaces)]  # list(range(self.n_surfaces))?
        self.mp_mode = self.settings["mp_mode"].GetString()
        self.input_file = self.settings["input_file"].GetString()
        self.timestep = self.timestep_start
        self.iteration = None

        if "subcycling" in self.settings.keys():
            self.subcycling = self.settings["subcycling"].GetInt()
            if self.subcycling:
                self.minInc = self.settings["minInc"].GetDouble()
                self.initialInc = self.settings["initialInc"].GetDouble()
                self.maxNumInc = self.settings["maxNumInc"].GetInt()
                self.maxInc = self.settings["maxInc"].GetInt()
                self.ramp = self.settings["ramp"].GetInt()
            else:
                self.maxNumInc = 1
                self.maxInc = self.delta_t
                self.ramp = 0
        else:
            self.subcycling = 0
            self.maxNumInc = 1
            self.ramp = 0

        # Upon (re)starting Abaqus needs to run USRInit.f
        # A restart requires Abaqus to be booted with a restart file

        # prepare abaqus_v6.env
        self.hostnames = []
        self.hostnames_unique = []
        with open(join(self.dir_csm, "AbaqusHosts.txt"), "r") as hostfile:
            for line in hostfile:
                self.hostnames.append(line.rstrip())
                if not line.rstrip() in self.hostnames_unique:
                    self.hostnames_unique.append(line.rstrip())
        self.hostname_replace = ""
        for hostname in self.hostnames_unique:
            self.hostname_replace += "[\'" + hostname + "\', " + str(self.hostnames.count(hostname)) + "], "
        self.hostname_replace = self.hostname_replace.rstrip(", ")
        with open(join(path_src, "abaqus_v6.env"), "r") as infile:
            with open(join(self.dir_csm, "abaqus_v6.env"), "w") as outfile:
                for line in infile:
                    line = line.replace("|HOSTNAME|", self.hostname_replace)
                    line = line.replace("|MP_MODE|", self.mp_mode)
                    line = line.replace("|PID|", str(os.getpid()))
                    line = line.replace("|PWD|", os.path.abspath(os.path.join(self.dir_csm, os.pardir)))
                    line = line.replace("|CSM_dir|", self.settings["working_directory"].GetString())
                    if "|" in line:
                        raise ValueError(f"The following line in abaqus_v6.env still contains a \"|\" after substitution: \n \t{line} \n Probably a parameter was not subsituted")
                    outfile.write(line)

        # Create start and restart file
        self.write_start_and_restart_inp(join(self.dir_csm, self.input_file), self.dir_csm + "/CSM_Time0.inp", self.dir_csm + "/CSM_Restart.inp")

        # Prepare Abaqus USRInit.f
        usr = "USRInit.f"
        with open(join(path_src, usr), "r") as infile:
            with open(join(self.dir_csm, "usrInit.f"), "w") as outfile:
                for line in infile:
                    line = line.replace("|dimension|", str(self.dimensions))
                    line = line.replace("|surfaces|", str(self.n_surfaces))
                    line = line.replace("|cpus|", str(self.cores))

                    # if PWD is too long then FORTRAN code can not compile so this needs special treatment
                    line = self.FORT_replace(line, "|PWD|", os.path.abspath(os.getcwd()))
                    line = self.FORT_replace(line, "|CSM_dir|", self.settings["working_directory"].GetString())
                    if "|" in line:
                        raise ValueError(f"The following line in USRInit.f still contains a \"|\" after substitution: \n \t{line} \n Probably a parameter was not subsituted")
                    outfile.write(line)

        # Compile Abaqus USRInit.f
        path_libusr = join(self.dir_csm, "libusr/")
        os.system("rm -rf " + path_libusr)
        os.system("mkdir " + path_libusr)
        cmd = "abaqus make library=usrInit.f directory=" + path_libusr + " >> AbaqusSolver.log 2>&1"
        commands = [cmd]
        self.run_shell(self.dir_csm, commands, name='Compile_USRInit')

        # Get loadpoints from usrInit.f
        if self.timestep_start == 0:
            cmd1 = f"export PBS_NODEFILE=AbaqusHosts.txt && unset SLURM_GTIDS"  # To get this to work on HPC?
            cmd2 = f"rm -f CSM_Time{self.timestep_start}Surface*Faces.dat CSM_Time{self.timestep_start}Surface*FacesBis.dat"
            # The output files will have a name with a higher time step  ("job=") than the input file ("input=")
            cmd3 = f"abaqus job=CSM_Time{self.timestep_start+1} input=CSM_Time{self.timestep_start} cpus=1 user=usrInit.f" \
                f" output_precision=full interactive >> AbaqusSolver.log 2>&1"
            commands = [cmd1, cmd2, cmd3]
            self.run_shell(self.dir_csm, commands, name='Abaqus_USRInit_Time0')
        else:
            cmd1 = f"export PBS_NODEFILE=AbaqusHosts.txt && unset SLURM_GTIDS"  # To get this to work on HPC?
            cmd2 = f"rm -f CSM_Time{self.timestep_start}Surface*Faces.dat CSM_Time{self.timestep_start}Surface*FacesBis.dat"
            cmd3 = f"abaqus job=CSM_Time{self.timestep_start+1} oldjob=CSM_Time{self.timestep_start} input=CSM_Restart cpus=1 user=usrInit.f" \
                f" output_precision=full interactive >> AbaqusSolver.log 2>&1"
            commands = [cmd1, cmd2, cmd3]
            self.run_shell(self.dir_csm, commands, name=f'Abaqus_USRInit_Restart')

        # prepare GetOutput.cpp
        get_output = "GetOutput.cpp"
        temp_str = ""
        for j in range(0, self.n_surfaces - 1):
            temp_str += f"\"{self.surfaceIDs[j]}\", "
        temp_str += f"\"{self.surfaceIDs[self.n_surfaces-1]}\""

        with open(join(path_src, get_output), "r") as infile:
            with open(join(self.dir_csm, get_output), "w") as outfile:
                for line in infile:
                    line = line.replace("|surfaces|", str(self.n_surfaces))
                    line = line.replace("|surfaceIDs|", temp_str)
                    line = line.replace("|dimension|", str(self.dimensions))
                    if "|" in line:
                        raise ValueError(f"The following line in GetOutput.cpp still contains a \"|\" after substitution: \n \t{line} \n Probably a parameter was not subsituted")
                    outfile.write(line)

        # compile GetOutput.cpp
        cmd = "abaqus make job=GetOutput user=GetOutput.cpp >> AbaqusSolver.log 2>&1"
        commands = [cmd]
        self.run_shell(self.dir_csm, commands, name='Compile_GetOutput')

        # Get node positions (not load points) at startTimeStep
        cmd = f"abaqus ./GetOutput.exe CSM_Time{self.timestep_start+1} 0 >> AbaqusSolver.log 2>&1"  # 0 is an argument to GetOutput.exe
        commands = [cmd]
        self.run_shell(self.dir_csm, commands, name='GetOutput_Start')

        for i in range(0, self.n_surfaces):
            path_output = f"CSM_Time{self.timestep_start+1}Surface{i}Output.dat"
            path_nodes = f"CSM_Time{self.timestep_start}Surface{i}Nodes.dat"
            cmd = f"mv {path_output} {path_nodes}"
            commands = [cmd]
            self.run_shell(self.dir_csm, commands, name='Move_Output_File_To_Node')

            # Create elements file per surface
            face_file = os.path.join(self.dir_csm, f"CSM_Time{self.timestep_start}Surface{i}Cpu0Faces.dat")
            output_file = os.path.join(self.dir_csm, f"CSM_Time{self.timestep_start}Surface{i}Elements.dat")
            self.makeElements(face_file, output_file)

        # prepare Abaqus USR.f
        usr = "USR.f"
        with open(join(path_src, usr), "r") as infile:
            with open(join(self.dir_csm, "usr.f"), "w") as outfile:
                for line in infile:
                    line = line.replace("|dimension|", str(self.dimensions))
                    line = line.replace("|arraySize|", str(self.array_size))
                    line = line.replace("|surfaces|", str(self.n_surfaces))
                    line = line.replace("|cpus|", str(self.cores))
                    line = line.replace("|ramp|", str(self.ramp))
                    line = line.replace("|deltaT|", str(self.delta_t))

                    # if PWD is too long then FORTRAN code can not compile so this needs special treatment
                    line = self.FORT_replace(line, "|PWD|", os.path.abspath(os.getcwd()))
                    line = self.FORT_replace(line, "|CSM_dir|", self.settings["working_directory"].GetString())
                    if "|" in line:
                        raise ValueError(f"The following line in USR.f still contains a \"|\" after substitution: \n \t{line} \n Probably a parameter was not subsituted")
                    outfile.write(line)

        # compile Abaqus USR.f
        os.system("rm -r " + path_libusr)  # remove libusr containing compiled USRInit.f
        os.system("mkdir " + path_libusr)
        cmd = "abaqus make library=usr.f directory=" + path_libusr + " >> AbaqusSolver.log 2>&1"
        commands = [cmd]
        self.run_shell(self.dir_csm, commands, name='Compile_USR')

### --- Create Model --- ###
        self.model = data_structure.Model()

        # create ModelParts
        for key, value in (self.settings['interface_input'].items() +
                           self.settings['interface_output'].items()):
            # add ModelPart to Model
            self.model.CreateModelPart(key)  # Can those two lines be combined in mp = self.model.CreateModelPart(key)?
            mp = self.model[key]

            # add historical variables to ModelPart
            for var_name in value.list():
                var = vars(data_structure)[var_name.GetString()]
                mp.AddNodalSolutionStepVariable(var)

            # add information to ModelPart
            bool_found = 0
            for i in range(self.n_surfaces):
                if self.surfaceIDs[i] in key:
                    mp.thread_name = self.surfaceIDs[i]
                    mp.thread_id = self.thread_ids[i]  # This is just a number from 0 to n_surfaces
                    if 'thread_id' not in dir(mp):
                        raise AttributeError(f'Could not find thread id corresponding to {key}')
                    bool_found = 1
            if bool_found == 0:
                raise AttributeError(f'Could not identify surfaceID corresponding to key {key}. Check parameter file.')

        # add Nodes to input ModelParts (load_points)
        # elements line 1 contains number of elements
        # elements line 2 contains number of load points per element
        # elements remainder contains element numbers involved in interface

        geom_min = np.array([np.Inf, np.Inf, np.Inf])
        geom_max = np.array([np.NINF, np.NINF, np.NINF])

        for key in self.settings['interface_input'].keys():
            mp = self.model[key]

            # read in elements file
            tmp = f'CSM_Time{self.timestep_start}Surface{mp.thread_id}Elements.dat'
            elem_file = join(self.dir_csm, tmp)
            elements = np.loadtxt(elem_file)

            if self.timestep_start > 0:
                tmp0 = f'CSM_Time0Surface{mp.thread_id}Elements.dat'
                elem0_file = join(self.dir_csm, tmp0)
                elements0 = np.loadtxt(elem0_file)
            elif self.timestep_start == 0:
                elements0 = elements

            n_elem = int(elements[0])
            n_lp = int(elements[1])
            if elements.shape[0]-2 != int(n_elem):
                raise ValueError(f"Number of lines ({elements.shape[0]}) in {elem_file} does not correspond with the number of elements ({n_elem})")

            if int(elements0[0]) != n_elem or int(elements0[1]) != n_lp:
                raise ValueError(f"Number of load points has changed for {key}")

            # read in Faces file for load points and also file at time 0 for original positions for the mappers
            tmp = f'CSM_Time{self.timestep_start}Surface{mp.thread_id}Cpu0Faces.dat'
            faces_file = join(self.dir_csm, tmp)
            faces = np.loadtxt(faces_file)

            if self.timestep_start > 0:
                tmp0 = f'CSM_Time0Surface{mp.thread_id}Cpu0Faces.dat'
                faces0_file = join(self.dir_csm, tmp0)
                faces0 = np.loadtxt(faces0_file)
            elif self.timestep_start == 0:
                faces0 = faces

            if faces.shape[1] != self.dimensions + 2:
                raise ValueError(f'given dimension does not match coordinates')

            # get load point coordinates and ids of load points
            prev_elem = 0
            prev_lp = 0
            ids_tmp = np.zeros(n_elem*n_lp).astype(str)  # create string ids element_loadpoint
            coords_tmp = np.zeros((n_elem*n_lp, 3)).astype(float)  # Framework also requires z-coordinate which is 0.0 for 2D
            coords0_tmp = np.zeros((n_elem * n_lp, 3)).astype(float)
            for i in range(0, n_elem*n_lp):
                elem = int(faces0[i, 0])
                lp = int(faces0[i, 1])
                if elem < prev_elem:
                    raise ValueError(f"Element sequence is wrong ({elem}<{prev_elem})")
                elif elem == prev_elem and lp != prev_lp+1:
                    raise ValueError(f"Next line for same element ({elem}) does not contain next load point")
                elif elem > prev_elem and lp != 1:
                    raise ValueError(f"First line for Element ({elem}) does not contain its first load point")
                if lp > n_lp:
                    raise ValueError(f"lp ({lp}) exceeds the number of load points per element {n_lp}")

                ids_tmp[i] = f"{elem}_{lp}"
                coords0_tmp[i, :self.dimensions] = faces0[i, -self.dimensions:]  # extract last "dimensions" columns from the file
                coords_tmp[i, :self.dimensions] = faces[i, -self.dimensions:]

                prev_elem = elem
                prev_lp = lp

            # create Nodes for load points
            # Also keep track of min and max of the nodes to verify that surfaces are consistent
            mp.min = np.array([np.Inf, np.Inf, np.Inf])
            mp.max = np.array([np.NINF, np.NINF, np.NINF])  # -np.inf == np.NINF
            for i in range(ids_tmp.size):
                node = mp.CreateNewNode(ids_tmp[i],
                                 coords0_tmp[i, 0], coords0_tmp[i, 1], coords0_tmp[i, 2])  # Stores node.X0, node.Y0 and node.Z0 for mappers
                # Set the node coordinates to the correct values at the current timestep_start
                node.X = coords_tmp[i, 0]
                node.Y = coords_tmp[i, 1]
                node.Z = coords_tmp[i, 2]

                if coords0_tmp[i, 0] < mp.min[0]: mp.min[0] = coords0_tmp[i, 0]
                if coords0_tmp[i, 1] < mp.min[1]: mp.min[1] = coords0_tmp[i, 1]
                if coords0_tmp[i, 2] < mp.min[2]: mp.min[2] = coords0_tmp[i, 2]
                if coords0_tmp[i, 0] > mp.max[0]: mp.max[0] = coords0_tmp[i, 0]
                if coords0_tmp[i, 1] > mp.max[1]: mp.max[1] = coords0_tmp[i, 1]
                if coords0_tmp[i, 2] > mp.max[2]: mp.max[2] = coords0_tmp[i, 2]

            # Find the bounding box of the complete structure based on the interface_input
            if mp.min[0] < geom_min[0]: geom_min[0] = mp.min[0]
            if mp.min[1] < geom_min[1]: geom_min[1] = mp.min[1]
            if mp.min[2] < geom_min[2]: geom_min[2] = mp.min[2]
            if mp.max[0] > geom_max[0]: geom_max[0] = mp.max[0]
            if mp.max[1] > geom_max[1]: geom_max[1] = mp.max[1]
            if mp.max[2] > geom_max[2]: geom_max[2] = mp.max[2]

        # add Nodes to output ModelParts (surface_points)
        # first line is a header, remaining lines are x, y (and z) coordinates
        # Abaqus does not use node ids but maintains the output order
        for key in self.settings['interface_output'].keys():
            mp = self.model[key]
            # read in Nodes0 file for mapper and Nodes file for surface node positions
            tmp = f'CSM_Time{self.timestep_start}Surface{mp.thread_id}Nodes.dat'
            nodes_file = join(self.dir_csm, tmp)
            nodes = np.loadtxt(nodes_file, skiprows=1)
            if self.timestep_start > 0:
                tmp0 = f'CSM_Time0Surface{mp.thread_id}Nodes.dat'
                nodes0_file = join(self.dir_csm, tmp0)
                nodes0 = np.loadtxt(nodes0_file, skiprows=1)
            elif self.timestep_start == 0:
                nodes0 = nodes

            if nodes.shape[1] != self.dimensions:
                raise ValueError(f'given dimension does not match coordinates')

            # get surface node coordinates and ids
            n_nodes = nodes.shape[0]
            n_nodes0 = nodes0.shape[0]
            if n_nodes != n_nodes0:
                raise ValueError(f"Number of interface nodes has changed for {key}")

            ids_tmp = np.zeros(n_nodes).astype(str)

            coords_tmp = np.zeros((n_nodes, 3)).astype(float)  # Framework also requires z-coordinate which is 0.0 for 2D
            coords0_tmp = np.zeros((n_nodes, 3)).astype(float)

            for i in range(0, n_nodes):
                ids_tmp[i] = str(i)
                coords_tmp[i, :self.dimensions] = nodes[i, :]
                coords0_tmp[i, :self.dimensions] = nodes0[i, :]

            # create Nodes for surface points
            # Also keep track of min and max of the nodes to verify that surfaces are consistent
            mp.min = np.array([np.Inf, np.Inf, np.Inf])
            mp.max = np.array([np.NINF, np.NINF, np.NINF])
            for i in range(ids_tmp.size):
                node = mp.CreateNewNode(ids_tmp[i], coords0_tmp[i, 0], coords0_tmp[i, 1], coords0_tmp[i, 2])
                node.X = coords_tmp[i, 0]
                node.Y = coords_tmp[i, 1]
                node.Z = coords_tmp[i, 2]

                if coords0_tmp[i, 0] < mp.min[0]: mp.min[0] = coords0_tmp[i, 0]
                if coords0_tmp[i, 1] < mp.min[1]: mp.min[1] = coords0_tmp[i, 1]
                if coords0_tmp[i, 2] < mp.min[2]: mp.min[2] = coords0_tmp[i, 2]
                if coords0_tmp[i, 0] > mp.max[0]: mp.max[0] = coords0_tmp[i, 0]
                if coords0_tmp[i, 1] > mp.max[1]: mp.max[1] = coords0_tmp[i, 1]
                if coords0_tmp[i, 2] > mp.max[2]: mp.max[2] = coords0_tmp[i, 2]

            # Check the bounding boxes for input interface versus output interface
            # This will be based on the original coordinates at time 0
            tol_center = 0.02
            tol_BB = 0.1
            tol_geom = 0.01
            AR_plane = 1e-08
            abs_tol_plane = 1e-06

            # Find corresponding Input modelpart based on thread_id
            bool_corresponds = 0
            for key_temp in self.settings['interface_input'].keys():
                mp_temp = self.model[key_temp]
                if mp_temp.thread_id == mp.thread_id:
                    mp_input = mp_temp
                    bool_corresponds = 1
                    break
            if bool_corresponds == 0:
                raise ValueError(f"Found no interface_input object corresponding to the interface_output object ({key})")
            else:
                diff_Out = mp.max - mp.min
                diff_In = mp_input.max - mp_input.min
                ref = np.array([max(diff_Out[0], diff_In[0]), max(diff_Out[1], diff_In[1]),
                                max(diff_Out[2], diff_In[2])])
                geom_diff = geom_max-geom_min
                for i in range(0, self.dimensions):
                    if self.dimensions == 3:
                        bool_A = ref[i] < AR_plane*ref[i-1] and ref[i] < AR_plane*ref[i-2]  # Identifies as plane perpendicular to coordinate direction
                        bool_B = (geom_diff[i] < AR_plane*geom_diff[i-1] and geom_diff[i] < AR_plane*geom_diff[i-2])
                    elif self.dimensions == 2:
                        bool_A = ref[i] < AR_plane*ref[(i+1) % 2]  # Identifies as plane perpendicular to coordinate direction
                        bool_B = geom_diff[i] < AR_plane*geom_diff[(i+1) % 2]

                    if bool_A:
                        if not bool_B:
                            if np.abs((mp.max[i]+mp.min[i])/2.0-(mp_input.max[i]+mp_input.min[i])/2.0) > tol_geom*geom_diff[i]:
                                tools.Print(f"Warning: The bounding box center of the input and output for the face {mp.thread_name} "
                                            f"differ by more than {tol_geom*100}% of the bounding box for the complete interface geometry in the {i}-direction", layout='red')
                                tools.Print(f"Input interface center: {(mp_input.max+mp_input.min)/2.0}")
                                tools.Print(f"Output interface center: {(mp.max + mp.min) / 2.0}")
                        else:
                            if np.abs((mp.max[i]+mp.min[i])/2.0-(mp_input.max[i]+mp_input.min[i])/2.0) > abs_tol_plane:
                                tools.Print(f"Warning: The bounding box center of the input and output for the face {mp.thread_name} "
                                            f"differ by more than {abs_tol_plane}m in the {i}-direction", layout='red')
                                tools.Print(f"Input interface center: {(mp_input.max+mp_input.min)/2.0}")
                                tools.Print(f"Output interface center: {(mp.max + mp.min) / 2.0}")
                    else:
                        if np.abs(mp.min[i]-mp_input.min[i]) > tol_BB*ref[i]:
                            tools.Print(
                                f"Warning: The minima of the bounding boxes of the input and output for {mp.thread_name} "
                                f"differ by more than {tol_BB*100}% of the corresponding bounding box in the {i}-direction", layout='red')
                            tools.Print(f"Input interface bounding box: {mp_input.min} to {mp_input.max}")
                            tools.Print(f"Output interface bounding box: {mp.min} to {mp.max}")
                        if np.abs(mp.max[i] - mp_input.max[i]) > tol_BB * ref[i]:
                            tools.Print(
                                f"Warning: The maxima of the bounding boxes of the input and output for {mp.thread_name} "
                                f"differ by more than {tol_BB*100}% of the corresponding bounding box in the {i}-direction", layout='red')
                            tools.Print(f"Input interface bounding box: {mp_input.min} to {mp_input.max}")
                            tools.Print(f"Output interface bounding box: {mp.min} to {mp.max}")
                        if np.abs((mp.max[i]+mp.min[i])/2.0 - (mp_input.max[i]+mp_input.min[i])/2.0) > tol_center * ref[i]:
                            tools.Print(
                                f"Warning: The geometric centers of the input and output for {mp.thread_name} "
                                f"differ by more than {tol_center*100}% of the corresponding bounding box in the {i}-direction", layout='red')
                            tools.Print(f"Input interface center: {(mp_input.max + mp_input.min) / 2.0}")
                            tools.Print(f"Output interface center: {(mp.max + mp.min) / 2.0}")
                            tools.Print(f"Input interface bounding box: {mp_input.min} to {mp_input.max}")
                            tools.Print(f"Output interface bounding box: {mp.min} to {mp.max}")

            # self.write_Nodes_test()  # This should be commented out in the final code

        # create Interfaces
        self.interface_input = Interface(self.model, self.settings['interface_input'])
        self.interface_output = Interface(self.model, self.settings['interface_output'])

        # create Variables
        self.pressure = vars(data_structure)['PRESSURE']
        self.traction = vars(data_structure)['TRACTION']
        self.displacement = vars(data_structure)['DISPLACEMENT']

        # debug
        self.debug = False  # set on True to save copy of input and output files in every iteration

    def Initialize(self):
        super().Initialize()

    def InitializeSolutionStep(self):
        super().InitializeSolutionStep()

        self.iteration = 0
        self.timestep += 1

    def SolveSolutionStep(self, interface_input):
        self.iteration += 1

        # store incoming loads
        self.interface_input.SetPythonList(interface_input.GetPythonList())

        # write loads (from interface data to a file that will be read by USR.f
        self.write_loads()

        # copy input data for debugging
        if self.debug:
            for key in self.settings['interface_input'].keys():
                mp = self.model[key]
                tmp = f"CSM_Time{self.timestep}Surface{mp.thread_id}Cpu0Input.dat"
                tmp2 = f"CSM_Time{self.timestep}Surface{mp.thread_id}Cpu0Input_Iter{self.iteration}.dat"
                cmd = f"cp {join(self.dir_csm, tmp)} {join(self.dir_csm, tmp2)}"
                os.system(cmd)

        # Run Abaqus and check for (licensing) errors
        bool_completed = 0
        attempt = 0
        while not bool_completed and attempt < 10000:
            attempt += 1
            if attempt > 1:
                tools.Print(f"Warning attempt {attempt-1} in AbaqusSolver failed, new attempt in one minute", layout='warning')
                time.sleep(60)
                tools.Print(f"Starting attempt {attempt}")
            if self.timestep == 1:
                cmd1 = f"export PBS_NODEFILE=AbaqusHosts.txt && unset SLURM_GTIDS"
                cmd2 = f"abaqus job=CSM_Time{self.timestep} input=CSM_Time{self.timestep - 1}" \
                    f" cpus={self.cores} user=usr.f output_precision=full interactive >> AbaqusSolver.log 2>&1"
                commands = [cmd1, cmd2]
                self.run_shell(self.dir_csm, commands, name='Abaqus_Calculate')
            else:
                cmd1 = f"export PBS_NODEFILE=AbaqusHosts.txt && unset SLURM_GTIDS"
                cmd2 = f"abaqus job=CSM_Time{self.timestep} oldjob=CSM_Time{self.timestep - 1} input=CSM_Restart" \
                    f" cpus={self.cores} user=usr.f output_precision=full interactive >> AbaqusSolver.log 2>&1"
                commands = [cmd1, cmd2]
                self.run_shell(self.dir_csm, commands, name='Abaqus_Calculate')

            # Check log for completion and or errors
            cmd = "tail -n 10 AbaqusSolver.log > Temp_log.coco"
            self.run_shell(self.dir_csm, [cmd], name='Temp_log')
            templog = os.path.join(self.dir_csm, "Temp_log.coco")
            bool_lic = 1
            with open(templog, "r") as fp:
                for line in fp:
                    if any(x in line for x in ["Licensing error", "license error", "Error checking out Abaqus license"]):
                        bool_lic = 0
            if not bool_lic:
                tools.Print("Abaqus licensing error", layout='fail')
            elif "COMPLETED" in line:  # Check final line for completed
                bool_completed = 1
            elif bool_lic:  # Final line did not contain "COMPLETED" but also no licensing error detected
                raise RuntimeError("Abaqus did not COMPLETE, unclassified error, see AbaqusSolver.log for extra information")

            # Append additional information to log file
            cmd = f"tail -n 23 CSM_Time{self.timestep}.msg | head -n 15 | sed -e \'s/^[ \\t]*//\' >> AbaqusSolver.log 2>&1"
            self.run_shell(self.dir_csm, [cmd], name='Append_log')

        # Write Abaqus output
        cmd = f"abaqus ./GetOutput.exe CSM_Time{self.timestep} 1 >> AbaqusSolver.log 2>&1"
        self.run_shell(self.dir_csm, [cmd], name='GetOutput')

        # Read Abaqus output data
        for key in self.settings['interface_output'].keys():
            mp = self.model[key]
            # read in Nodes file for surface nodes
            tmp = f"CSM_Time{self.timestep}Surface{mp.thread_id}Output.dat"
            disp_file = join(self.dir_csm, tmp)
            disp = np.loadtxt(disp_file, skiprows=1)

            # copy output data for debugging
            if self.debug:
                tmp2 = f"CSM_Time{self.timestep}Surface{mp.thread_id}Output_Iter{self.iteration}.dat"
                cmd = f"cp {disp_file} {join(self.dir_csm,tmp2)}"
                os.system(cmd)

            if disp.shape[1] != self.dimensions:
                raise ValueError(f"given dimension does not match coordinates")

            # get surface node displacements
            n_nodes = disp.shape[0]
            if n_nodes != mp.NumberOfNodes():
                raise ValueError("number of nodes does not match size of data")

            ids_tmp = np.array(range(0, n_nodes)).astype(int).astype(str)
            disp_tmp = np.zeros((n_nodes, 3))  # also require z-input for 2D cases
            disp_tmp[:, :self.dimensions] = disp

            index = 0
            for node in mp.Nodes:
                if ids_tmp[index] != node.Id:
                    raise ValueError(f"node IDs do not match: {ids_tmp[index]}, {node.Id}")

                node.SetSolutionStepValue(self.displacement, 0, disp_tmp[index, :].tolist())
                index += 1

        return self.interface_output

    def FinalizeSolutionStep(self):
        super().FinalizeSolutionStep()
        if self.timestep and (self.timestep-1) % self.settings['save_iterations'].GetInt():
            to_be_removed_suffix = [".com", ".dat", ".mdl", ".msg", ".odb", ".prt", ".res", ".sim", ".sta", ".stt",
                                    "Surface0Cpu0Input.dat", "Surface0Output.dat"]
            cmd = []
            for suffix in to_be_removed_suffix:
                cmd.append(f"rm CSM_Time{self.timestep - 1}{suffix}")
            self.run_shell(self.dir_csm, cmd, name="Remove_previous")

    def Finalize(self):
        super().Finalize()

    def GetInterfaceInput(self):
        return self.interface_input.deepcopy()

    def SetInterfaceInput(self):
        Exception("This solver interface provides no mapping.")

    def GetInterfaceOutput(self):
        return self.interface_output.deepcopy()

    def SetInterfaceOutput(self):
        Exception("This solver interface provides no mapping.")

    def makeElements(self, face_file, output_file):
        firstLoop = 1
        # element = 0
        element_prev = -1
        # point = 0
        point_prev = -1
        element_0 = -1
        point_0 = -1
        count = 0
        element_str = ""

        with open(face_file, 'r') as file:
            for line in file:
                values = line.strip().split()
                element = int(values[0])
                point = int(values[1])
                if element == element_0 and point == point_0:
                    break
                if element == element_prev:
                    if point == point_prev + 1:
                        point_prev = point
                    else:
                        raise ValueError(f"loadpoint number increases by more than one per line for element {element}")
                else:
                    if point == 1:
                        point_prev = point
                        element_prev = element
                        element_str += str(element) + "\n"
                        count += 1
                        if firstLoop:  # Faces contains all values multiple times, but we only want it once
                            element_0 = element
                            point_0 = point
                            firstLoop = 0
                    else:
                        raise ValueError(f"loadpoint number does not start at 1 for element {element}")

        element_str = f"{count}\n{point_prev}\n" + element_str
        with open(output_file, "w") as file:
            file.write(element_str)

    def run_shell(self, work_dir, commands, wait=True, name='script', delete=True):
        script = f'{work_dir}/{name}.sh'
        with open(script, 'w') as file:
            file.write('#!/bin/bash\n')
            file.write(f'cd {work_dir}\n')
            for line in commands:
                file.write(line + '\n')
        os.chmod(script, 0o700)
        if wait:
            p = subprocess.call(script, shell=True)
        else:
            p = subprocess.Popen(script, shell=True)
        if delete:
            os.system("rm " + script)
        return p

    def FORT_replace(self, line, orig, new):
        """The length of a line in FORTRAN 77 is limited, replacing working directories can exceed this limit.
        This functions splits these strings over multiple lines."""

        ampersand_location = 6
        char_limit = 72

        if "|" in line:
            temp = line.replace(orig, new)
            N = len(temp)

            if N > char_limit:
                count = 0
                line = ""
                line += temp[0:char_limit] + "\n"
                count += char_limit
                while count < N:
                    temp_string = temp[count:count + char_limit - ampersand_location]
                    n = len(temp_string)
                    count += n
                    if count < N:  # need to append an additional new line
                        line += "     &" + temp_string + "\n"
                    else:
                        line += "     &" + temp_string
            else:
                line = temp

        return line

    def write_start_and_restart_inp(self, input_file, output_file, restart_file):
        bool_restart = 0

        rf = open(restart_file, "w")
        of = open(output_file, "w")

        rf.write("*HEADING \n")
        rf.write("*RESTART, READ \n")

        with open(input_file) as f:
            line = f.readline()
            while line:
                if "*step" in line.lower():
                    contents = line.split(",")  # Split string on commas
                    line_new = ''
                    for s in contents:
                        if s.strip().startswith("inc="):
                            numbers = re.findall("\d+", s)
                            if (not self.subcycling) and int(numbers[0]) != 1:
                                raise NotImplementedError(f"inc={numbers[0]}: subcycling was not requested but maxNumInc > 1.")
                            else:
                                line_new += f" inc={self.maxNumInc},"
                        else:
                            line_new += s+","
                    line_new = line_new[:-1]+"\n"  # Remove the last added comma and add a newline

                    of.write(line_new)
                    if bool_restart:
                        rf.write(line_new)
                    line = f.readline()
                elif "*dynamic" in line.lower():
                    contents = line.split(",")
                    for s in contents:
                        if "application" in s.lower():
                            contents_B = s.split("=")
                            app = contents_B[1].lower().strip()
                            if app == "quasi-static" or app == "moderate dissipation":
                                if not self.subcycling:
                                    line_2 = f"{self.delta_t}, {self.delta_t},\n"
                                else:
                                    line_2 = f"{self.initialInc}, {self.delta_t}, {self.minInc}, {self.maxInc}\n"
                            else:
                                raise NotImplementedError(
                                    f"{contents_B[1]} not available: Currently only quasi-static and moderate dissipation are implemented for the Abaqus wrapper")
                    of.write(line)
                    if bool_restart:
                        rf.write(line)
                    line = f.readline()  # need to skip the next line
                    of.write(line_2)  # Change the time step in the Abaqus step
                    if bool_restart:
                        rf.write(line_2)  # Change the time step in the Abaqus step (restart-file)
                    line = f.readline()
                else:
                    of.write(line)
                    if bool_restart:
                        rf.write(line)
                    line = f.readline()
                if "** --"in line:
                    bool_restart = 1
        rf.close()
        of.close()

    def write_Nodes_test(self):
        for key in (self.settings['interface_input'].keys() + self.settings['interface_output'].keys()):
            mp = self.model[key]
            tmp = f'{key}_testNodes_thread{mp.thread_id}.dat'
            file_name = join(self.dir_csm, tmp)
            with open(file_name, 'w') as file:
                file.write(f'{mp.NumberOfNodes()}\n')
                for node in mp.Nodes:
                    if self.dimensions == 2:
                        file.write(f'{node.X:27.17e}{node.Y:27.17e}{node.Id:>27}\n')
                    else:
                        file.write(f'{node.X:27.17e}{node.Y:27.17e}{node.Z:27.17e}{node.Id:>27}\n')

    def write_loads(self):
        for key in self.settings['interface_input'].keys():
            mp = self.model[key]
            tmp = f'CSM_Time{self.timestep}Surface{mp.thread_id}Cpu0Input.dat'

            file_name = join(self.dir_csm, tmp)
            with open(file_name, 'w') as file:
                file.write(f'{mp.NumberOfNodes()}\n')
                for node in mp.Nodes:
                    pressure = node.GetSolutionStepValue(self.pressure)
                    traction = node.GetSolutionStepValue(self.traction)
                    if self.dimensions == 2:
                        file.write(f'{pressure:27.17e}{traction[0]:27.17e}{traction[1]:27.17e}\n')
                    else:
                        file.write(f'{pressure:27.17e}{traction[0]:27.17e}{traction[1]:27.17e}{traction[2]:27.17e}\n')

            # Start of a simulation with ramp, needs an initial load at time 0
            if self.iteration == 1 and self.timestep == 1 and self.ramp == 1:
                cmd = f"cp CSM_Time{self.timestep}Surface{mp.thread_id}Cpu0Input.dat CSM_Time{self.timestep-1}Surface{mp.thread_id}Cpu0Input.dat"
                self.run_shell(self.dir_csm, [cmd], name='GetOutput')
