# Tube case with Fluent2D and TubeStructure

This example calculates the flow inside and the deformation and stresses of a straight flexible tube, where a pressure pulse is applied at the inlet.
This done by using Fluent (axisymmetric) and the Python solver TubeStructure.

## Coupling algorithm

The coupling technique used is the *interface quasi-Newton algorithm with an approximation for the inverse of the Jacobian from a least-squares model* (IQNI-LS).

## Predictor

The initial guess in every time step is done using the linear predictor.

## Convergence criterion

Two convergence criteria have been specified:

-   The number of iterations in every time step is larger than 15.
-   The residual norm on the displacement is a factor $10^{-6}$ lower than the initial value.
 
When either criterion is satisfied the simulation stops.
 
## Solvers

The flow solver is Fluent, used to solve an axisymmetric representation of the tube,
with 100 cells on the fluid-structure interface. 
When setting up the case, the mesh is build based on the file `mesh.jou` using Gambit.
The displacements are applied in the nodes, of which there are 101. 
In contrast, the loads (pressure and traction) are calculated in the cell centers, of which there are 100.
The axial direction is along the x-axis,
the radial direction along the y-axis.

The structure solver is the Python solver TubeStructure, which implements a 1D model of the tube wall,
with 100 elements on the fluid-structure interface.
The parameters for this model are specified in the setup folder by the file `solver_parameter.json`.
The loads, in fact only pressure for this 1D case, are applied on the cell centers.
The displacements are calculated in the cell centers as well.
Only the radial displacement is different from zero.
The axial direction is along the z-axis,
the radial direction along the y-axis.

Whereas for Fluent the origin is situated axially in the center of the tube, for TubeStructure the origin is located at the start.
Therefore, the parameter `axial_offset` is used in its `solver_parameter.json` file to correct for this.

The difference in reference frames and number of cells on the fluid-structure interface requires the use of mappers.
In the structure solver wrapper, a permutation mapper is introduced to match the coordinate frames, flipping the x- and z-axis of the input.
Thereafter, a linear interpolation mapper is used to interpolate in the y- and z-direction from the 100 cell centers of Fluent to the 100 cell centers of TubeStructure.
For the output the same is done in the opposite order: first interpolating and then flipping the axes.
