# OpenFOAM

This is the documentation for all OpenFOAM solver wrappers.
Currently only FSI simulations are supported, no other multiphysics problems.


## Parameters

This section describes the parameters in the JSON file, listed in alphabetical order.

parameter|type|description
---:|:---:|---
`application`|string|Name of the (adapted) OpenFOAM-solver to be used for the flow problem. This name should start with `CoCoNuT_`.
`boundary_names`|list| List of names of the patches corresponding to the interface. These names should match the patch names defined in the OpenFOAM-case (e.g.`["boundary1", "boundary2",...] `).
`cores`|int|Number of cores on which the OpenFOAM-solver can run. This variable will be replaced in the raw `decomposeParDict`-file, after which the case is decomposed of the given number of cores.
`decomposeMethod`|string|Name of the mesh decomposition method to be used in OpenFOAM (e.g. `simple`,`scotch`...).
`delta_t`|double|Fixed timestep size in flow solver. This parameter is usually specified in a higher `Component`.
`density`|int|The applied density of the fluid in an incompressible case. The density will be applied if `"is_incompressible` is set on `true`. 
`diffusivity`|string |Name of the diffusivity constant used in the mesh motion solver in OpenFOAM (e.g. `inverseDistance`...). 
`dimensions`|int|Dimension used in flow solver: 2 for 2D and axisymmetric, 3 for 3D. 
`end_time`|double|Physical end time of the simulation.
`interface_input`|dict| List of `ModelPart` names and `Variables` pairs that provides interface boundary conditions for the OpenFOAM solver. Each entry in the list has two keys: `model_part` and `variables` with values as name of the `ModelPart` and list of input variables available in `variables.py`. The `ModelPart` name must be the concatenation of an entry from `boundary_names` and "_input" (e.g. `{ "model_part": boundary1_input", "variables": ["displacement"]}`).
`interface_output`|dict| Analogous to `interface_input`, but here the name must be the concatenation of an entry from `boundary_names` and "_output". The entries in the list provides boundary conditions for the other solver(s) participating in the coupled simulation (e.g. `{ "model_part": boundary1_output", "variables": ["pressure", "traction"]}`).
`is_incompressible`|boolean| Indicates if the fluid film is behaving under incompressible or compressible conditions.
`meshmotion_solver`|string|Name of the mesh motion solver to be used in OpenFOAM (e.g. `displacementLaplacian`...).
`start_time`|double|Physical start time of the simulation. This should correspond to the name of the time step folder in OpenFOAM from which the initial data and boundary conditions are read.
`time_precision`|int|Number of digits after the decimal sign to be used in the name of the time step directories which are made during execution. 
`write_interval`|double|Period between subsequent saves of the entire flow field.
`write_precision`|int|Number of digits after the decimal sign to be used when writing data to time step folders or the `postProcessing`-folder.
`working_directory`|string|Directory where the OpenFOAM-case is defined (and which contains the JSON-file).



## Overview of the OpenFOAM-wrapper

The solver wrapper can be found in the `solver_wrapper.openfoam.vX`-directory and consists of only one Python-file: `vX.py`, with `X`the identifier of the OpenFOAM-version (e.g. `v41` for OpenFOAM 4.1). Aside from this, the Python-file constructs a number of files such as `controlDict`, `pointDisplacement`, `dynamicMeshDict` and `decomposeParDict` by starting from the `_raw`-files in the solver wrapper directory and replacing the names of the settings with their user-defined values (listed in the table above). Finally, using an OpenFOAM-solver in CoCoNuT requires the adaptation of the solver to accomodate the internal messaging system used during the FSI-simulation. Currently, only `pimpleFoam` and `interFoam` have been adapted; the solvers called by the solver wrapper have the same name as the original OpenFOAM-solver but with `CoCoNuT_` added to the name. `CoCoNuT_pimpleFoam` treads FSI simulations whereas the fluid is approached as isothermal and incompressible in a laminar or turbulent transient case. `CoCoNuT_interFoam` is apllied for two incompressible, isothermal immiscible fluids. Upon using the OpenFOAM-wrapper, the solver to be used upon execution needs to be compiled using the default OpenFOAM-compilation method (loading the OpenFOAM-module and using `wmake` in the `solver_wrapper.CoCoNuT_xxxxFoam`-directory).

### The `__init__` method

During initialization, the case settings as defined in the JSON-file are read into the corresponding Python-variables. Afterwards, the required OpenFOAM-files are constructed and some checks are in place to verify whether the necessary (and correct) modules are loaded. Next, the interface names are loaded and the tool `writeCellCentres` is used to read in the points located on said interfaces. Finally, the variables on each interface are stored in the data-structure of CoCoNuT. 

### The `Initialize` method

The OpenFOAM-solver, which should be adapted to operation in CoCoNuT, is launched in a subprocess. Other variables, such as time step index and physical time, are initialized.

### The `InitializeSolutionStep` method

This function is called at the start of every time step. The time step index is increased by one, the iteration index is set to zero and the OpenFOAM file directory is made in which the time step data needs to be stored.

### The `SolveSolutionStep` method

The interface displacement is converted into an OpenFOAM-readable format (with the function `write_node_input`), after which the OpenFOAM-loop is called in a subprocess. After completion of the OpenFOAM-loop, the function `read_node_output` is called, which reads the interface loads from the corresponding OpenFOAM-directory (in the `postProcessing`-folder).

### The `FinalizeSolutionStep` method

In this method, it is checked whether the other flow variables need to be written in an OpenFOAM-directory. This save-option is done in OpenFOAM.

### The `Finalize` method

The OpenFOAM-subprocess, which was launched in the `Initialize` method, is killed.

## Comments

-   Files with extension `.coco` are used to pass messages between Python and OpenFOAM. After sending a message from Python to OpenFOAM, the Python-script is paused until it receives the corresponding message from OpenFOAM. The OpenFOAM-solver is operating in an infinite `while`-loop until it receives a message from Python. Upon receipt of this message, OpenFOAM executes the corresponding action after which it sends a response to Python and reverts into its infinite loop (waiting mode). 
-	The aforementioned messaging procedure implies that OpenFOAM is constantly running during execution of the CoCoNuT-simulation. It is closed by the Python-code only in the `Finalize` method, but if CoCoNuT crashes, the OpenFOAM-programme keeps running. The user should take care to kill that OpenFOAM-loop manually (using `kill` or `pkill` in the Linux-terminal, e.g. `pkill CoCoNuT_*`).
-	The interface displacement is stored in a `pointDisplacement`-field, which is read in by OpenFOAM in every iteration (this required some adaptation of the solver, see next section). The dynamic mesh motion is handled by OpenFOAM itself.
-	The interface loads are stored in the `postProcessing`-directory, under the names `PRESSURE` and `TRACTION`. These are constructed from a `controlDict`-file which is defined in the `_init_`-method of the solver wrapper in Python.

## Overview of an OpenFOAM-solver used in CoCoNuT

Default OpenFOAM-solvers cannot be used in the CoCoNuT-framework, but need to be adjusted. Adapted solvers are stored in the solverwrapper-directory and receive the name `CoCoNuT_X`, where `X` is the name of the original solver, e.g. `pimpleFoam`. If a new solver needs to be adapted to operation in CoCoNuT, one of the already established solvers can work as an example. In brief, the following steps should be undertaken:

-	Except for the initial `include`-statements, the entire solver code should be put in a loop that starts with `while(true)`.
-	Just before this while-loop, add the statement `runTime.run();`! This is important as it creates and initializes the functionObjects in the `controlDict`-file which will be used for storing the interface loads.
-	Due to the fact that the infinite loop is driven by `while(true)` and not the default OpenFOAM-expression `while(runTime.run())`, OpenFOAM does not check itself whether the final time step is reached. In proper CoCoNuT-operation, OpenFOAM is killed when the solver wrapper reaches the final time step, but this might not be the case if the OpenFOAM-solverwrapper is tested separately.
-	Inside the while-loop, a sleep-command is added such that the solver is not constantly checking the conditional statements. 
-	The while-loop contains several conditional statements, each of which check whether the Python-code in CoCoNuT has sent a message to the OpenFOAM-solver. This message is sent by creating an empty file with a specific name in the OpenFOAM-directory. The following file names should be checked by the OpenFOAM-solver: `next.coco`, `continue.coco`, `save.coco`, `stop.coco`. 	
-	If the file `next.coco` exists, the runTime-object should be increased by one. OpenFOAM should create a file `next_ready.coco` upon completion. Do not forget to delete the original `next.coco`-file, which is advised to do just before creating the `next_ready.coco`, so near the end of the `if`-clause.
-	If the file `continue.coco` exists, the flow equations need to be solved. This `if`-statement consequently contains most of the original solver definition, in which the flow equations are called in the same order as in the original CFD solver. OpenFOAM should create a file `continue_ready.coco` upon completion. Do not forget to delete the original `continue.coco`-file, which is advised to do just before creating the `continue_ready.coco`, so near the end of the `if`-clause.
-	If the file `save.coco` exists, OpenFOAM checks whether the flow variables should be stored in corresponding files, according to the user-defined save interval. OpenFOAM should create a file `save_ready.coco` upon completion. Do not forget to delete the original `save.coco`-file, which is advised to do just before creating the `save_ready.coco`, so near the end of the `if`-clause.
-	If the file `stop.coco` exists, a `break`-statement should end the infinite loop (the subprocess is also killed in the Python-code). OpenFOAM should create a file `stop_ready.coco` before breaking the `while`-loop. Do not forget to delete the original `stop.coco`-file, which is advised to do just before creating the `stop_ready.coco`, so near the end of the `if`-clause.


## Setting up a new case

Following items should be present in the OpenFOAM-directory prior to launching CoCoNuT:

-	The entire framework of the CFD-case in OpenFOAM which is to be used in the CoCoNuT simulation (so it should contain the `constant` and `system` directory as well as a time step directory). The working directory should be defined as if you would like to run it as a CFD case. The working directory is defined in a JSON-file and therefore the CoCoNuT-files do not need to be in the same folder as the OpenFOAM-case.
-	a JSON-file containing all of the settings stipulated above.

Following items are taken care of by CoCoNuT, and must therefore not be included in the original OpenFOAM-directory:

-   `controlDict`-file with the necessary function objects to define the interface pressure/traction
-	`dynamicMeshDict`-file which contains the settings for OpenFOAM's dynamic motion solver
-   `decomposeParDict`-file with the necessary decomposition of the fluid domain (if `cores`>1)

### Comments

-	It is probably best to derive a new case from a test case already present in the CoCoNuT-installation in order to copy its structure.
- 	If you do not use an OpenFOAM-solver which is already converted for operation in CoCoNuT, you will need to adapt the solver yourself. This can be done in a rather straightforward way by taking a look at already implemented solvers. You should compile the new solver BEFORE loading the CoCoNuT-modules as the overwriting of compiler modules can break the  `wmake`-command. Once the new solver is compiled, it works fine even after loading the CoCoNuT-modules.
-	OpenFOAM is known for generating a lot of files, which is not different in CoCoNuT-operation. Make sure you have sufficient storage space on your cluster and that you are able to write a large number of files (the latter is specifically important when storing data in your home-directory).


## Version specific documentation

### v41 (OpenFOAM 4.1)

This is currently the only version.

