#!/bin/bash

# README: run this script to remove old data and setup case

# clean working directory
rm -rf ./CFD

# create new CFD folder
cp -r setup_openfoam CFD
cd CFD

# make blockmesh
ml OpenFOAM/4.1
source $FOAM_BASH
blockMesh > blockMesh_log

echo "Mesh created"
cd ../
