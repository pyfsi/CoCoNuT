[![CoCoNuT banner](https://raw.githubusercontent.com/pyfsi/coconut/master/docs/images/coconut-banner.svg)](https://github.com/pyfsi/coconut)

hallo
# Coupling Code for Numerical Tools


CoCoNuT is a light-weight Python package for efficient partitioned multi-physics simulations, with a focus on fluid-structure interaction. 
Thanks to its fully modular approach, the package is versatile and easy to extend. It is available under the GPL-3.0 license. 


## Introduction

The *Coupling Code for Numerical Tools* &mdash; *CoCoNuT* in short &mdash; follows a partitioned approach to solve multi-physics problems: existing single-physics solvers are coupled through a Python interface. 
This has the advantage that dedicated, highly-optimized single-physics solvers can be used. 
To use the code with a new solver (open source or commercial), a so-called *solver wrapper* is written to take care of the communication with CoCoNuT. 
All other CoCoNuT components, such as mapping for non-conformal meshes, are solver-independent and are easily swapped thanks to CoCoNuT's modular architecture. 

CoCoNuT is under active development by the [Fluid Mechanics research team](https://www.ugent.be/ea/eemmecs/en/research/stfes/flow) at Ghent University. 
Our specialization is partitioned fluid-structure interaction. 
We develop high-performance quasi-Newton algorithms to accelerate convergence of the coupled problem, and apply these techniques to diverse fluid-structure interaction applications such as wind turbines, tube bundles and flexible aircraft. 

The full documentation of the CoCoNuT package can be found at the [documentation website](https://pyfsi.github.io/coconut/).


## Installation

These instructions describe the setup of CoCoNuT on Linux. The package has not been tested on Windows or macOS, so compatibility is not guaranteed, although we do not expect major issues. 


### Requirements

-   `python>=3.6` 
-   `numpy>=1.16.4`
-   `scipy>=1.3.0`
-   `pandas>=0.24.2` (required for [Kratos solver wrapper](coupling_components/solver_wrappers/kratos.md))
-   `matplotlib=3.1.0` (recommended)

We recommend Anaconda 2019.07 or newer.


### Installation procedure

CoCoNuT does not need to be compiled, hence installation is straightforward. 
The source code can be downloaded as a zip file, or cloned directly from GitHub. For users that have no experience with Git or GitHub, we recommend the first option. The second option makes it easier to update the software and contribute to the code. 

*Option 1: download zip*

-   Download the source code from [GitHub](https://github.com/pyfsi/coconut).
-   Unzip to a folder *`coconut`*. If the folder is unzipped in Windows, some of the file permissions may change and some tests or examples may not run out of the box. 

*Option 2: clone source*

-   Choose or create a directory to install CoCoNuT. 
-   Move to this directory. 
-   Clone the GitHub repository with SSH or HTTPS by executing one of the following commands. 

    -   With SSH:
    
    ```
    git clone git@github.com:pyfsi/coconut.git
    ```
   
    -   With HTTPS:
         
    ```
    git clone https://github.com/pyfsi/coconut.git
    ```

After the code has been downloaded or cloned, the *`coconut`* folder must be added to the user's Python path. 
For example, with a folder structure like

```
/some/absolute/path/
    coconut/
        coupling_components/
        data_structure/
        ...
        README.md
```

*`coconut`* can be added to your Python path by executing the following line:

```bash
export PYTHONPATH=/some/absolute/path:$PYTHONPATH
```

This line can also be added to your *`.bashrc`* file.

### Checking the solver modules 

Before using CoCoNuT, it is necessary to adapt some system specific commands in the *`solver_modules.py`* file in the *`coconut`* folder.
This file has the commands to load solver modules in separate environments when running a case, to avoid conflicts. As these commands are system specific, it is important to check this file before testing CoCoNuT. 
The file contains a nested dictionary `solver_load_cmd_dict`, which has keys such as `ugent_cluster_SL6.3` or `ugent_cluster_CO7` denoting the machine on which CoCoNuT is installed.
In their turn, each of these dictionaries contains keys for all solvers that are available on that machine and can be used in CoCoNuT. 
The values are strings containing terminal commands to load the software, thus setting the environment which allows running the solver. 
For example, on the UGent cluster, the [Lmod system](https://lmod.readthedocs.io/en/latest/) is used, but there is no general guideline on how to make the solvers' software available as long as it is compatible with your system's command-line-interface. 
If multiple commands are needed, they should appropriately be separated within the string. For example in a Linux terminal the semi-colon (;) or double ampersand (&&) can be used.
Since `machine_name` is set to `ugent_cluster_SL6.3`, this dictionary is used by default.
In case your system differs from the `ugent_cluster_SL6.3` settings, it is advised to add your own internal dictionary to `solver_load_cmd_dict` and provide this key to `machine_name`.
If a solver module is not present on your system the key should be removed. If a solver module is always present, i.e. no module load command or similar action is needed, an empty string should be given as value.
When CoCoNuT tries to use a solver module that is not present in the `solver_load_cmd_dict` or that has the wrong value, an error will be raised.

### Quick test

We recommend to run the unit tests at the end of the installation, to make sure that everything works. 

-   Ensure that *`coconut`* is included in your Python path.
-   Move to the *`coconut/tests`* directory. 
-   Run the unit tests by executing the following line:

```bash
python -m unittest -b
```


## Getting started

Once the CoCoNuT package has been successfully installed, it is time to run a first coupled simulation. For this purpose, we give a step-by-step guide of an example case included in the source code.

In this example the fluid-structure interaction (FSI) problem of a pressure wave propagating through an elastic tube in incompressible flow is calculated [[1](#1), [2](#2)]. For both the flow and structure solver, we use 1D Python-solvers that are included in CoCoNuT. This has the advantage that no external single-physics solvers must be installed for this example. Furthermore, the 1D solvers are very fast, so that a full transient FSI calculation can be done in this example. Other example cases in the source code solve the same FSI problem with ANSYS Fluent or OpenFOAM as flow solver and Abaqus or Kratos as structure solver. 

We start by creating a variable `COCO` in which we can store the path to the folder in which CoCoNuT is installed. We will use this variable to avoid any confusion about relative or absolute paths in this tutorial. Using the example installation location from above:

```bash
COCO=/some/absolute/path
```

We can now navigate to the folder of the example we will simulate. 
```bash
cd $COCO/coconut/examples/tube_tube_flow_tube_structure/
```
This folder serves as main directory to set up and run the FSI simulation from in CoCoNuT. The file *`parameters.json`* will be used to run the actual FSI simulation, but we will come back to that later. 
First we must set up both single-physics solvers separately. This setup is typically done outside of CoCoNuT by the user, as it is solver and case specific. 
In this case we provide a script *`setup_case.py`* that sets up both solvers using the files in the folder *`../setup_files`*. When the script is run with

```bash
python3 setup_case.py
```

new folders *`CFD`* and *`CSM`* appear, as well as the file *`run_simulation.py`*. The *`CFD`* folder contains all files required to start a simulation of the flow in the tube. 
Analogously, the *`CSM`* folder contains all files required to start a simulation of the tube structure.

We can now start the FSI simulation in CoCoNuT by running the Python file *`run_simulation.py`*:

```bash
python3 run_simulation.py
```

The simulation should start, first printing the CoCoNuT ASCII-banner and some information about the settings of the FSI simulation. Then the simulation itself starts: in each time step, the residual is given for every coupling iteration. When the simulation has finished, a summary about the computational effort is printed.

Let us now take a closer look at the two files that are used to run CoCoNuT. 
The Python file *`run_simulation.py`* typically does not have to be adapted by the user. Its task is to read in the settings file *`parameters.json`* and launch a simulation using those settings. 
The file *`parameters.json`* is a collection of settings that is written in [JSON format](https://www.json.org/json-en.html). JSON is a language-independent text format that is easy to read and write, and is used for data-exchange. 
It consists mainly of key-value pairs, and can hence be easily converted to a (nested) Python dictionary. While the keys are always strings, the values can be strings, numbers, arrays, booleans or nested JSON objects (nested dictionaries).
Before you read on, it can be useful to familiarize yourself with the JSON syntax. In what follows, we will use Python terminology (dictionary, list, boolean, etc...) to refer to the structure and the values in the JSON file. 

The JSON file is built up in a hierarchical way that represents the objects created in the CoCoNuT simulation. At the highest level, the dictionary contains two keys: `settings` and `coupled_solver`. 
The value given to the `settings` key is a nested dictionary, which contains a single key-value pair that sets the number of time steps to be simulated. 
The value given to the `coupled_solver` key is a special dictionary, because it has the `type` key. CoCoNuT will generate an object of the specified type, namely `coupled_solvers.iqni`. This refers to the class defined in the file *`$COCO/coconut/coupling_components/coupled_solvers/iqni.py`*: the `CoupledSolverIQNI` class. 
Note that the value in `type` always refers to a file located in *`$COCO/coconut/coupling_components`*. 
The dictionary under `settings` is used to initialize an instance of this class. In this case the initial time `timestep_start`, the time step `delta_t` and some other parameters must be given. The coupled solver is the main class that determines how the two single-physics solvers are coupled. 
The dictionary that is given to the `coupled_solver` key contains next to `type` and `settings` three other key-value pairs. These will generate other objects: the fact that they are given in the `coupled_solver` dictionary means that these objects will be created by the coupled solver object.

`predictor` will generate an object of the `PredictorLinear` class found in the file *`$COCO/coconut/coupling_components/predictors/linear.py`*. This class requires no additional settings for its initialization. The predictor object is used to extrapolate the solution to the next time step. 

`convergence_criterion` will generate an object of the `ConvergenceCriterionOr` class found in the file *`$COCO/coconut/coupling_components/convergence_criteria/or.py`*, using the given `settings` for its initialization. The convergence criterion is used to determine when CoCoNuT should move to the next time step. In this case the *or* criterion is used, which signals convergence when one or both underlying criteria are satisfied. These underlying criteria are instances of the `ConvergenceCriterionIterationLimit` and `ConvergenceCriterionRelativeNorm` classes defined in respectively *`$COCO/coconut/coupling_components/convergence_criteria/iteration_limit.py`* and *`$COCO/coconut/coupling_components/convergence_criteria/relative_norm.py`*. 
This means that CoCoNuT will move to the next time step after 15 iterations or when the 2-norm of the residual has decreased six orders of magnitude.

`solver_wrappers` is a list of two solver wrapper objects, which will communicate with the two single-physics solvers, in this case the 1D flow solver and the 1D structure solver. The first dictionary in the list will generate an instance of the `SolverWrapperTubeFlow` class found in *`$COCO/coconut/coupling_components/solver_wrappers/python/tube_flow_solver.py`*. An important setting to generate this object is the `working_directory`, which refers to the folder *`CFD`* that we created with the case files of the flow solver. All files written by the flow solver will also appear in this folder.
We would now expect the second dictionary to generate a solver wrapper to communicate with the structure solver, i.e. an instance of the `SolverWrapperTubeStructure` class found in *`$COCO/coconut/coupling_components/solver_wrappers/python/tube_structure_solver.py`*. This is not the case however: the flow and structure solvers typically use a different geometrical discretization (computational grid or mesh), hence they cannot readily be coupled in CoCoNuT. To overcome this issue, we put a layer of mapping around one of the solver wrappers. This is done with the `SolverWrapperMapped` class found in *`$COCO/coconut/coupling_components/solver_wrappers/mapped.py`*. The *mapped* solver wrapper interpolates all data flowing between the coupled solver and the real solver wrapper. The mapped solver wrapper itself contains three objects: the actual solver wrapper (`SolverWrapperTubeStructure` class), and mappers for respectively the input and the output of the solver wrapper (both `MapperInterface` class, found in *`$COCO/coconut/coupling_components/mappers/interface.py`*). 

The concept of the mapped solver wrapper illustrates the modularity of CoCoNuT. As far as the coupled solver is concerned, the mapped solver wrapper acts exactly as a real solver wrapper. The real solver wrapper does not know about the mapping at all: it acts as if it directly communicates with the coupled solver. Furthermore, the interpolation method can be easily changed by swapping the mappers in the mapped solver wrapper: the current linear interpolation scheme can for example be replaced by a radial basis scheme by changing `mappers.linear` to `mappers.radial_basis`. 

Now try to change some of the settings in the JSON file, such as the mappers, the time step or the maximum number of coupling iterations, and rerun the coupled simulation.

After a simulation is finished, it can be useful to visualize the output quantities (i.e. displacement, pressure and in general also shear). For the FSI-simulation we have just performed, post-processing has already been implemented in the file *`$COCO/coconut/examples/post_processing/`*. It requires the `save_results` setting in the `coupled_solver` part of the JSON-file to be set on `true`, which is for all examples done by default. As an example, we will generate an animation by running the *`animate_example.py`* file:

```bash
python $COCO/coconut/examples/post_processing/animate_example.py
```

Animations of the displacement and pressure will be shown.

<p align="center">
  <img alt="Pressure animation" src="https://raw.githubusercontent.com/pyfsi/coconut/master/docs/images/pressure.gif" width="49%">
  <img alt="Displacement animation" src="https://raw.githubusercontent.com/pyfsi/coconut/master/docs/images/displacement.gif" width="49%">
</p>


[//]: # (TODO: also refer to explanation of animate class once that documentation has been finished)


## Overview of the code

The CoCoNuT package consists of 5 main folders: *`coupling_components`*, *`data_structure`*, *`docs`*, *`examples`* and *`tests`*. To give a general understanding of how the code is structured, we give a brief description of the purpose of each folder. The documentation website mirrors this folder structure and the folder names below link to the corresponding page.


### [*`coupling_components`*](coupling_components/coupling_components.md)

This folder contains the basic building blocks of CoCoNuT, which can be used to set up a coupled simulation. This includes among others the solver wrappers, to communicate with single-physics solvers, and the mappers, which provide interpolation between non-conforming meshes present in the different single-physics solvers.

### [*`data_structure`*](data_structure/data_structure.md)

This folder contains the data structure that is used internally in CoCoNuT to store and pass around information obtained from the single-physics solvers. The data structure relies on NumPy arrays for efficient storage and manipulation of data.


### [*`docs`*](docs/docs.md)

This folder serves to automatically generate the documentation website, based on the MarkDown documentation files that are present throughout the code. 


### [*`examples`*](examples/examples.md)

This folder contains examples of several fluid-structure interaction cases, which can serve as starting point for settings up the user's own simulation. They also provide insight into the capabilities of CoCoNuT.


### [*`tests`*](tests/tests.md)

This folder contains the unit tests. These are created for each piece of code that is added to CoCoNuT and are run regularly, to avoid bugs. 

## References
<a id="1">[1]</a> 
[Degroote J., Annerel S. and Vierendeels J., "Stability analysis of Gauss-Seidel iterations in a partitioned simulation of fluid-structure interaction", Computers & Structures, vol. 88, no. 5-6, pp. 263, 2010.](http://hdl.handle.net/1854/LU-940283)

<a id="2">[2]</a> 
[Delaissé N., Demeester T., Fauconnier D. and Degroote J., "Surrogate-based acceleration of quasi-Newton techniques for fluid-structure interaction simulations", Computers & Structures, vol. 260, pp. 106720, 2022.](http://hdl.handle.net/1854/LU-8728347)

# Installation of the structural solver

The structural solver is developped by Philip Cardiff and adapt to achieve FSI calculations for this wire drawing case with black box approach.
The modified  structural solver can be found on the directory: coconut/coupling_components/
solver_wrappers/openfoam_extend/v41. The structural calculation makes use of a layering technique in order
to reduce the computational cost. Unfortunally, this code can't be shared as this is developped by the company where the structural
solver is applied and is classified.

## source_code_structure_wire_drawing

OpenFOAM code repository for wire drawing and wire rolling simulation

### Important information
This code for structural calculation is a reduced version of the original one. The solver can be find in the coconut_plasticNonLinSolidFoam-directory The most important reduction is the absence to apply the layering technique which is described in the artikel. The layering technique is developed inside the Bekaert N.V. company and is classified. To let an FSI simulation run, use a wire which is longer without applying layering. To get the complete code, please contact philip.cardiff@ucd.ie

### Installation
First install and compile foam-extend-4.1/foam-extend on your system.
Then compile source_code_structure_wire_drawing using the included Allwmake script.

### Systems and Compilers
The compilaltion has been checked on with systems and compilers, for example:

- macOS 10.12.6 : gcc (GCC) 4.9.2 20141029 (prerelease)  
- Ubuntu 16.04.3 LTS : gcc (Ubuntu 4.9.3-13ubuntu2) 4.9.3  
- Ubuntu 16.04.3 LTS : icc (ICC) 18.0.2 20180210  
- Red Hat Enterprise Linux Server release 6.9 (Santiago) : gcc (GCC) 4.9.2  
- SUSE Linux Enterprise Server 11 (x86_64) : icc (ICC) 15.0.3 20150407
- CO7: GCC/8.3.0   

### All packages loaded to let foam-Extend/4.1 run on local cluster:
  1) Java/1.8.0_281               
  2) PyCharm/2019.1.3              
  3) Anaconda3-python/2020.07     
  4) GCCcore/8.3.0                
  5) zlib/1.2.11-GCCcore-8.3.0    
  6) binutils/2.32-GCCcore-8.3.0  
  7) GCC/8.3.0                    
  8) numactl/2.0.12-GCCcore-8.3.0     
  9) XZ/5.2.4-GCCcore-8.3.0           
  10) libxml2/2.9.9-GCCcore-8.3.0      
  11) libpciaccess/0.14-GCCcore-8.3.0  
  12) hwloc/1.11.12-GCCcore-8.3.0      
  13) OpenMPI/3.1.4-GCC-8.3.0          
  14) OpenBLAS/0.3.7-GCC-8.3.0         
  15) gompi/2019b                 
  16) FFTW/3.3.8-gompi-2019b       
  17) ScaLAPACK/2.0.2-gompi-2019b  
  18) foss/2019b                  
  19) ParMETIS/4.0.3-gompi-2019b   
  20) METIS/5.1.0-GCCcore-8.3.0    
  21) SCOTCH/6.0.9-gompi-2019b     
  22) Mesquite/2.3.0-GCCcore-8.3.0  
  23) ParMGridGen/1.0-gompi-2019b    
  24) bzip2/1.0.8-GCCcore-8.3.0      
  25) ncurses/6.1-GCCcore-8.3.0      
  26) libreadline/8.0-GCCcore-8.3.0
  27) Tcl/8.6.9-GCCcore-8.3.0
  28) SQLite/3.29.0-GCCcore-8.3.0
  29) GMP/6.1.2-GCCcore-8.3.0
  30) libffi/3.2.1-GCCcore-8.3.0
  31) Python/2.7.16-GCCcore-8.3.0
  32) OpenFOAM-Extend/4.1-20200408-foss-2019b-Python-2.7.16

# Installation of the fluid solver
In following list the packages are displayed, which are loaded to execute the fluid calculations during the FSI calculations. 
  1) Java/1.8.0_281                    
  2) PyCharm/2019.1.3                  
  3) Anaconda3-python/2020.07          
  4) GCCcore/10.2.0                   
  5) zlib/1.2.11-GCCcore-10.2.0        
  6) binutils/2.35-GCCcore-10.2.0      
  7) GCC/10.2.0                        
  8) numactl/2.0.13-GCCcore-10.2.0     
  9) XZ/5.2.5-GCCcore-10.2.0           
 10) libxml2/2.9.10-GCCcore-10.2.0          
 11) libpciaccess/0.16-GCCcore-10.2.0  
 12) hwloc/2.2.0-GCCcore-10.2.0       
 13) libevent/2.1.12-GCCcore-10.2.0    
 14) UCX/1.9.0-GCCcore-10.2.0          
 15) libfabric/1.11.0-GCCcore-10.2.0   
 16) PMIx/3.1.5-GCCcore-10.2.0         
 17) OpenMPI/4.0.5-GCC-10.2.0          
 18) OpenBLAS/0.3.12-GCC-10.2.0        
 19) gompi/2020b                    
 20) FFTW/3.3.8-gompi-2020b          
 21) ScaLAPACK/2.1.0-gompi-2020b    
 22) foss/2020b                      
 23) ncurses/6.2-GCCcore-10.2.0      
 24) libreadline/8.0-GCCcore-10.2.0  
 25) METIS/5.1.0-GCCcore-10.2.0      
 26) SCOTCH/6.1.0-gompi-2020b        
 27) bzip2/1.0.8-GCCcore-10.2.0      
 28) Tcl/8.6.10-GCCcore-10.2.0      
 29) SQLite/3.33.0-GCCcore-10.2.0    
 30) GMP/6.2.0-GCCcore-10.2.0        
 31) libffi/3.3-GCCcore-10.2.0       
 32) Python/3.8.6-GCCcore-10.2.0    
 33) Boost/1.74.0-GCC-10.2.0        
 34) MPFR/4.1.0-GCCcore-10.2.0       
 35) gzip/1.10-GCCcore-10.2.0       
 36) lz4/1.9.2-GCCcore-10.2.0        
 37) zstd/1.4.5-GCCcore-10.2.0              
 38) expat/2.2.9-GCCcore-10.2.0              
 39) libpng/1.6.37-GCCcore-10.2.0            
 40) freetype/2.10.3-GCCcore-10.2.0          
 41) util-linux/2.36-GCCcore-10.2.0          
 42) fontconfig/2.13.92-GCCcore-10.2.0       
 43) xorg-macros/1.19.2-GCCcore-10.2.0       
 44) X11/20201008-GCCcore-10.2.0            
 45) libdrm/2.4.102-GCCcore-10.2.0           
 46) libglvnd/1.3.2-GCCcore-10.2.0           
 47) libunwind/1.4.0-GCCcore-10.2.0         
 48) LLVM/11.0.0-GCCcore-10.2.0              
 49) Mesa/20.2.1-GCCcore-10.2.0         
 50) libGLU/9.0.1-GCCcore-10.2.0            
 51) double-conversion/3.1.5-GCCcore-10.2.0  
 52) gettext/0.21-GCCcore-10.2.0             
 53) PCRE/8.44-GCCcore-10.2.0               
 54) GLib/2.66.1-GCCcore-10.2.0              
 55) PCRE2/10.35-GCCcore-10.2.0          
 56) DBus/1.13.18-GCCcore-10.2.0        
 57) NASM/2.15.05-GCCcore-10.2.0         
 58) libjpeg-turbo/2.0.5-GCCcore-10.2.0  
 59) NSPR/4.29-GCCcore-10.2.0            
 60) NSS/3.57-GCCcore-10.2.0             
 61) snappy/1.1.8-GCCcore-10.2.0         
 62) JasPer/2.0.14-GCCcore-10.2.0        
 63) Qt5/5.14.2-GCCcore-10.2.0           
 64) CGAL/5.2-gompi-2020b               
 65) pybind11/2.6.0-GCCcore-10.2.0       
 66) SciPy-bundle/2020.11-foss-2020b     
 67) Szip/2.1.1-GCCcore-10.2.0           
 68) HDF5/1.10.7-gompi-2020b             
 69) cURL/7.72.0-GCCcore-10.2.0
 70) netCDF/4.7.4-gompi-2020b
 71) x264/20201026-GCCcore-10.2.0
 72) LAME/3.100-GCCcore-10.2.0
 73) x265/3.3-GCCcore-10.2.0
 74) 74) FriBidi/1.0.10-GCCcore-10.2.0
 75) FFmpeg/4.3.1-GCCcore-10.2.0
 76) ParaView/5.8.1-foss-2020b-mpi
 77) pixman/0.40.0-GCCcore-10.2.0
 78) cairo/1.16.0-GCCcore-10
 79) libgd/2.3.0-GCCcore-10.2.0.2.0
 80) ICU/67.1-GCCcore-10.2.0
 81) HarfBuzz/2.6.7-GCCcore-10.2.0
 82) Pango/1.47.0-GCCcore-10.2.0
 83) libcerf/1.14-GCCcore-10.2.0
 84) Lua/5.4.2-GCCcore-10.2.0
 85) gnuplot/5.4.1-GCCcore-10.2.0
 86) OpenFOAM/8-foss-2020b

#    Wire drawing case: the simulation itself

Results for the FSI case can be found on directory:
coconut/examples/wire_drawing

Directory implemented boundary condition sliding FSI interface:
coconut/coupling_components/solver_wrappers/openfoam_extend/v41/coconut_src/boundaryConditions

Directory implemented boundary condition no-slip (synchronizing drawing velocity):
coconut/coupling_components/solver_wrappers/openfoam/v8/coconut_src/boundaryConditions

Directory mappers:
coconut/coupling_components/mappers

H-file synchronizing processors during parallel running:
coconut/coupling_components/solver_wrappers/openfoam/waitForSync.H

Directory fluid solver during FSI calculations:
coconut/coupling_components/solver_wrappers/openfoam/v8/coconut_pimpleFoam

Fluid solver wrapper for FSI calculations in OpenFOAM:
coconut/coupling_components/solver_wrappers/openfoam/openfoam.py

Directory fluid solver during FSI calculations:
coconut/coupling_components/solver_wrappers/openfoam/v8/coconut_pimpleFoam

Structural solver wrapper for FSI calculations in OpenFOAM:
coconut/coupling_components/solver_wrappers/openfoam_extend/openfoam_extend.py

Directory structural solver during FSI calculations:
coconut/coupling_components/solver_wrappers/openfoam_extend/v41/coconut_plasticNonLinSolidFoam

Directory library source code structural calculations:
coconut/coupling_components/solver_wrappers/openfoam_extend/v41/source_code_structure_wire_drawing

To install CoCoNuT, instructions can be found on top of this document
The  "wire_drawing" branch is used for this simulation, with corresponding modified solver wrappers and mappers.
The wrappers are made for OpenFOAM 8 and foam-extend 4.1 and modified to let it run a wire drawing case with sliding interface and no-slip
condition at the FSI interface (see wrappers directory).

The parameter.json file includes the settings of the FSI case
The setup_openfoam and setup_foamExtend directories contain the initial case for the fluid as the structural calculations respectively.
To start the simulation. Go to the directory case of "wire_drawing" (coconut/examples/wire_drawing)

### execute following commands:

"./Allrun"

For this case, the debug switches of the fluid and structure solver are set on "false" to save space, meaning that only results are saved at
every 10th time steps.

After the simulation has been ran, the results at steady state are obtained by executing the command:

"python postProcess.py"

Different graphs with the distribution of different parameters will appear at steady state.

The results can also been seen at paraFoam.

