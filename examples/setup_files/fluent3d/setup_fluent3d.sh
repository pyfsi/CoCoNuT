#!/bin/bash

# make fluent case
ml ANSYS_CFD/2019R1
fluent 3ddp -g -i case.jou > setup_fluent.log 2>&1
ml -ANSYS_CFD
