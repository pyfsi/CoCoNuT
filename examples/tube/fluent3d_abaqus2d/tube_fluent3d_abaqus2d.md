# Tube case with Fluent3D and Abaqus2D

This example calculates the flow inside and the deformation and stresses of a straight flexible tube, where a pressure pulse is applied at the inlet.
This done by using Fluent (3D case) and Abaqus (axisymmetric case).

## Coupling algorithm

The coupling technique used is the *interface quasi-Newton algorithm with an approximation for the inverse of the Jacobian from a least-squares model* (IQNI-LS).

## Predictor

The initial guess in every time step is done using the linear predictor.

## Convergence criterion

Two convergence criteria have been specified:

- The number of iterations in every time step is larger than 20.
- The residual norm on the displacement is a factor $10^{-3}$ lower than the initial value.
 
When either criterion is satisfied the simulation stops.
 
## Solvers

The flow solver is Fluent, used to solve a fully 3D tube,
with 48 cells on the fluid-structure interface in the length direction and 8 in the circumferential direction.
When setting up the case, the mesh is build based on the file *`mesh.jou`* using Gambit.
The displacements are applied in the nodes. In contrast, the loads (pressure and traction) are calculated in the cell centers.
The axial direction is along the x-axis.
The setup script runs Fluent with the *`case.jou`* journal file to set up the case parameters, starting from the mesh file *`mesh_tube3d.msh`*.
This case is written to the *`case_tube3d.cas`* file, which serves as input for CoCoNuT. 
Additionally, a folder *`create_mesh`* is provided containing a script to create the mesh in Gambit using a journal file.
The mesh can be created by running the script *`create_mesh.sh`*, given that Gambit v2.4.6 is available.

The structure solver is Abaqus, used to solve an axisymmetric representation of the tube,
with 50 elements on the fluid-structure interface.
The Abaqus case is built when setting up the case starting from the file *`mesh_tube2d.inp`* containing nodes and elements. 
This is done by running Abaqus with the *`make_inp.py`* Python script to set all parameters, such as surface definitions, material parameters, boundary conditions and time step information.
The result of the setup is a completed input file *`case_tube2d.inp`*.
The Abaqus element type used is CAX8RH. These are continuum elements for axisymmetric calculations, for stress and displacement without twist. 
They are: 8-node biquadratic, reduced integration, hybrid with linear pressure. See the [Abaqus documentation](http://130.149.89.49:2080/v6.14/books/usb/default.htm?startat=book01.html#usb) for more information. 
The loads are applied on the faces in three points per element, which means on 150 load points in total. 
The displacement is calculated in the nodes. There are 101 nodes on the fluid-structure interface.
The axial direction is along the y-axis, the radial direction along the x-axis.

The difference in reference frames and number of cells on the fluid-structure interface, but also the difference in dimensions require the use of mappers,
In the structure solver wrapper, a permutation mapper is introduced to match the coordinate frames, flipping the x- and y-axis of the input.
Thereafter, a radial basis mapper is used to interpolate in the x-, y- and z-direction from the loads coming from Fluent to a temporary 3D interface corresponding to Abaqus.
Finally, a mapper is added to go from 3D to 2D. For the output the same is done in the opposite order: first going from 2D to 3D, then interpolating and finally flipping the axes.