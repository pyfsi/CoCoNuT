import numpy as np
from os.path import dirname, join


def create_node_and_element_list(xp, yp, zp, bool_quadratic, bool_n1, name='nodes_elements.txt'):
    '''
    :param xp, yp, zp: nodes for linear elements
    :param bool_quadratic: boolean for quadratic elements
    :param bool_n1: boolean for orientations
    :param name: name of node and element list file (external source to .inp-file)
    :return: 0
    '''
    f = open(name, 'w')
    N = xp.shape[0]
    countN1 = 1

    if not bool_n1:
        # Node_list
        f.write('*Node\n')
        for i in range(0, N):
            f.write(f'\t{countN1},\t{xp[i]:f},\t{yp[i]:f},\t{zp[i]:f} \n')
            countN1 += 1
        countN2 = countN1
        if bool_quadratic:
            N2 = xp.shape[0]
            for i in range(0, N2 - 1):
                f.write(f'\t{countN2},\t{(xp[i] + xp[i + 1]) / 2.0:f},\t{(yp[i] + yp[i + 1]) / 2.0:f},\t'
                        f'{(zp[i] + zp[i + 1]) / 2.0:f} \n')
                countN2 += 1

        # Element_list
        count_elem = 1
        if not bool_quadratic:
            f.write('*Element, type=B31\n')
            for i in range(0, N - 1):
                f.write(f"\t{count_elem},\t{count_elem},\t{count_elem + 1}\n")
                count_elem += 1
        else:
            f.write('*Element, type=B32\n')
            for i in range(0, N - 1):
                f.write(f'\t{count_elem},\t{count_elem},\t{count_elem + countN1 - 1},\t{count_elem + 1}\n')
                count_elem += 1
    else:  # If orientations are desired
        xn, yn, zn = get_normals(xp, yp, zp)
        # Node_list
        f.write('*Node\n')
        for i in range(0, N):
            f.write(f'\t{countN1},\t{xp[i]:f},\t{yp[i]:f},\t{zp[i]:f} \n')
            countN1 += 1
        countN2 = countN1
        if bool_quadratic:
            N2 = xp.shape[0]
            for i in range(0, N2 - 1):
                f.write(f'\t{countN2},\t{(xp[i] + xp[i + 1]) / 2.0:f},\t{(yp[i] + yp[i + 1]) / 2.0:f},\t'
                        f'{(zp[i] + zp[i + 1]) / 2.0:f} \n')
                countN2 += 1
        countN3 = countN2
        for i in range(0, N - 1):
            f.write(f'\t{countN3},\t{xn[i]:f},\t{yn[i]:f},\t{zn[i]:f} \n')
            countN3 += 1

        # Element_list
        count_elem = 1
        if not bool_quadratic:
            f.write('*Element, type=B31\n')
            for i in range(0, N - 1):
                f.write(f'\t{count_elem},\t{count_elem},\t{count_elem + 1},\t{count_elem + countN2 - 1}\n')
                count_elem += 1
        else:
            f.write('*Element, type=B32\n')
            for i in range(0, N - 1):
                f.write(f'\t{count_elem},\t{count_elem},\t{count_elem + countN1 - 1},\t{count_elem + 1},'
                        f'\t{count_elem + countN2 - 1}\n')
                count_elem += 1

    f.close()


def get_normals(xp, yp, zp):
    '''
    :param xp:
    :param yp:
    :param zp:
    :return: arrays for normal nodes
    Normal is defined by vector from start point of element to extra node defined in these arrays
    '''
    N = xp.shape[0]
    xn = []
    yn = []
    zn = []
    for i in range(0, N - 1):
        xn.append(xp[i] + 0.0)
        yn.append(yp[i] + 0.1)
        zn.append(zp[i] + 0.0)
    return xn, yn, zn


def create_yarn():
    n_points = 501
    coordinates = np.zeros((n_points, 3))
    r = 88.655*1e-3
    coordinates[:, 0] = np.linspace(91.4e-3-np.cos(np.radians(60.))*r, 91.4e-3+np.cos(np.radians(60.))*r, n_points)
    coordinates[:, 1] = np.linspace(-np.sin(np.radians(60.))*r, np.sin(np.radians(60.))*r, n_points)
    return coordinates[:, 0], coordinates[:, 1], coordinates[:, 2]


### START OF PROGRAM ###
directory = dirname(__file__)
input_file = 'yarn.inp'
geometry_file = 'nodes_elements.txt'

quadratic = True
n1 = True

print('Extracting yarn geometry')
x, y, z = create_yarn()
n_nodes = x.shape[0]
print(f'Yarn Geometry extracted. Number of nodes is {n_nodes}.\n')

print('Creating node and element list.\n')
create_node_and_element_list(x, y, z, quadratic, n1, geometry_file)
print('Writing of node and element list successful.\n')

print(f'Creating .inp-file with name {input_file}\n')
f = open(join(directory, input_file), 'w+')

f.write('*Heading\n')
f.write('** Job name: Yarn Model name: Yarn\n')
f.write('** Generated by: Abaqus/CAE 2024\n')
f.write('*Preprint, echo=NO, model=NO, history=NO, contact=NO\n')
f.write('**\n** PARTS\n**\n*Part, name=PART-YARN\n')
f.write(f'*INCLUDE, INPUT={geometry_file}\n')  # Include external file with nodes and elements
f.write(f'*Elset, elset=YARN_ELEMENTS, generate\n\t1,\t{n_nodes - 1},\t1\n')
f.write(f'*Nset, nset=START_NODE\n\t1,\n')
f.write(f'*Nset, nset=END_NODE\n\t{n_nodes},\n')

if quadratic:
    q_nodes = 2 * n_nodes - 1
else:
    q_nodes = n_nodes

f.write('** Section: Section-YARN Profile: Profile-yarn\n')
f.write('*Beam General Section, elset=YARN_ELEMENTS, poisson = 0.39, density=1140., section=CIRC\n')
f.write('0.00017731\n')  # Yarn radius
f.write('0.,1.,0.\n')  # Element set orientation (remove this?)
f.write('2.5e+09, 8.99281e+08, 0.\n')  # Young's modulus and Shear modulus, related via G = E/(2*(1+nu))
f.write('*End Part\n**\n**\n** ASSEMBLY\n**\n')
f.write('*Assembly, name=ASSEMBLY-YARN\n**\n*Instance, name=INSTANCE-YARN, part=PART-YARN\n*End Instance\n**\n')
f.write(f'*Nset, nset=YARN_NODES, instance=INSTANCE-YARN, generate\n\t1,\t{q_nodes},\t1\n')
f.write(f'*Nset, nset=START_NODE, instance=INSTANCE-YARN\n\t1,\n')
f.write(f'*Nset, nset=END_NODE, instance=INSTANCE-YARN\n\t{n_nodes},\n')
f.write(f'*Elset, elset=YARN_ELEMENTS, instance=INSTANCE-YARN, generate\n\t1,\t{n_nodes - 1},\t1\n')
f.write(f'*Surface, type=ELEMENT, name=YARN_SURF\n YARN_ELEMENTS, \n**\n')
f.write('*End Assembly\n')

f.write('** ----------------------------------------------------------------\n**\n** STEP: Step-1\n**\n')
f.write('*Step, name=Step-1, nlgeom=YES, inc=1000\n')
f.write('*Static\n0.01, 1., 0.0001, 1.\n**\n')
f.write(f'** BOUNDARY CONDITIONS\n**\n** Name: BC-START Type: Displacement/Rotation\n*Boundary\n')
f.write(f'INSTANCE-YARN.START_NODE, 1, 6\n')
f.write(f'** Name: BC-END Type: Displacement/Rotation\n*Boundary\n')
f.write(f'INSTANCE-YARN.END_NODE, 1, 6\n')
f.write('**\n** LOADS\n**\n')
f.write('** Name: LINELOAD-1\t Type: Line load\n*Dload, op=NEW\nYARN_ELEMENTS, PXNU, 1.\n')
f.write('** Name: LINELOAD-2\t Type: Line load\n*Dload, op=NEW\nYARN_ELEMENTS, PYNU, 1.\n')
f.write('** Name: LINELOAD-3\t Type: Line load\n*Dload, op=NEW\nYARN_ELEMENTS, PZNU, 1.\n')

f.write('**\n** OUTPUT REQUESTS\n**\n*Restart, write, overlay, frequency=99999\n**\n')
f.write('** FIELD OUTPUT: F-Output-2\n**\n*Output, field, frequency=99999\n*Node Output, nset=YARN_NODES\nCOORD,'
        ' U\n**\n')
f.write('** FIELD OUTPUT: F-Output-1\n**\n*Output, field, variable=PRESELECT, frequency=99999\n**\n')
f.write('** HISTORY OUTPUT: H-Output-1\n**\n*Output, history, variable=PRESELECT, frequency=99999\n')
f.write('*End Step\n')

f.close()

print('Input file created.')
