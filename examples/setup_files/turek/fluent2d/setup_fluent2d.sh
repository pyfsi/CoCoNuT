#!/bin/bash

# make fluent case
#TODO remove module load command
ml ANSYS_CFD/2019R1
fluent 2ddp -g -i case.jou > setup_fluent.log 2>&1
ml -ANSYS_CFD
