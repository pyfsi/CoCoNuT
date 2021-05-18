
import matplotlib.pyplot as plt
import matplotlib
from coconut.coupling_components.component import Component
from coconut import data_structure

from subprocess import check_call
import numpy as np
import os
import sys
import time
import subprocess
import re



matplotlib.rcParams['font.size'] = 14
matplotlib.rcParams['axes.linewidth']=1
matplotlib.rcParams['lines.linewidth'] = 2
matplotlib.rcParams['axes.labelweight'] = 'bold'
matplotlib.rcParams['xtick.major.size'] = 4
matplotlib.rcParams['xtick.minor.size'] = 2.4
matplotlib.rcParams['ytick.major.size'] = 4
matplotlib.rcParams['ytick.minor.size'] = 2.4
matplotlib.rcParams['savefig.dpi'] = 300

X_name = os.path.join('CFD', '0/ccx')
Y_name = os.path.join('CFD', '0/ccy')
Z_name = os.path.join('CFD', '0/ccz')
pointDisplacement = os.path.join('CFD', '0.010000/cellDisplacement')
initial_load = np.genfromtxt ('initial_pressure.dat')
x = initial_load[:,0]
y = initial_load[:,1]
print(x)
print(y)
fX = open(X_name, 'r')
fY = open(Y_name, 'r')
fZ = open(Z_name, 'r')
fTemp = open(pointDisplacement, 'r')
fXLines = fX.readlines()
fYLines = fY.readlines()
fZLines = fZ.readlines()
fTempLines = fTemp.readlines()

for line in range(len(fXLines)):
    if "dieWall" in fXLines[line]:
        count = int(fXLines[line+4])
        array = np.zeros((count,3))
        for i in range(count):
            array[i,0] = float(fXLines[line+6+i])
            array[i,1] = float(fYLines[line+6+i])/(np.cos(2.5*np.pi/180))
            array[i,2] = 0

for line in range(len(fXLines)):
    if "Wire" in fXLines[line]:
        count = int(fXLines[line+4])
        array2 = np.zeros((count,3))
        for i in range(count):
            array2[i,0] = float(fXLines[line+6+i])
            array2[i,1] = float(fYLines[line+6+i])/(np.cos(2.5*np.pi/180))
            array2[i,2] = 0

array_filmthickness = (array[:,1] - array2[:,1])*1000000
# print(array_filmthickness)

for line in range(len(fTempLines)):
    if "Wire" in fTempLines[line]:
        count = int(fTempLines[line + 4])
        array_disp = np.zeros((count,3))
        for i in range(count):
            coor = (fTempLines[line + 6 + i])
            array_disp[i,0] = 0
            if coor[18:19]==' ':
                p = float(coor[3:18])
                array_disp[i,1] = p
            elif coor[19:20] == ' ':
                p = float(coor[3:19])
                array_disp[i, 1] = p
            elif coor[20:21]== ' ':
                p = float(coor[3:20])
                array_disp[i, 1] = p
            elif coor[21:22] == ' ':
                p = float(coor[3:21])
                array_disp[i, 1] = p
            elif coor[22:23] == ' ':
                p = float(coor[3:22])
                array_disp[i, 1] = p
            elif coor[23:24] == ' ':
                p = float(coor[3:23])
                array_disp[i, 1] = p
            elif coor[24:25] == ' ':
                p = float(coor[3:24])
                array_disp[i, 1] = p
            else:
                print(coor[3:25]+'check')
                p = float(coor[3:25])
                array_disp[i, 1] = p

        array_disp[i,1] = array_disp[i,1]/(np.cos(2.5*np.pi/180))

array_filmthickness2 = (array[:,1] - array2[:,1] - array_disp[:,1])*1000000
# print(array_filmthickness2)
fig, ax1 = plt.subplots()

fig.suptitle('film thickness', fontsize = 20)

ax1.set_xlabel('wire position(m)')

color2 = 'tab:blue'
ax1.set_ylabel("Initial load (Pa)")
ax1.plot(x,y, color=color2)
ax1.tick_params(axis='y', labelcolor=color2)

ax2 = ax1.twinx()

color = 'tab:red'
ax2.set_ylabel(" Film thickness at 1.5 iterations (µm)")
ax2.plot(array[:,0], array_filmthickness2, color=color)
ax2.tick_params(axis='y', labelcolor=color)

fig.tight_layout()
plt.show()