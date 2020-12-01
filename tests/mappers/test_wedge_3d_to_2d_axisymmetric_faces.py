from coconut import data_structure
from coconut.data_structure import KratosUnittest
from coconut.coupling_components.tools import CreateInstance

import numpy as np
import os
import matplotlib.pyplot as plt
from matplotlib import cm
from mpl_toolkits.mplot3d import Axes3D

class TestMapperWedge3DTo2Daxisymmetric(KratosUnittest.TestCase):
    def test_mapper_wedge_3d_to_2d_axisymmetric(self):
        parameter_file_name = os.path.join(os.path.dirname(__file__), 'test_wedge_3d_to_2d_axisymmetric_faces.json')
        with open(parameter_file_name, 'r') as parameter_file:
            parameters = data_structure.Parameters(parameter_file.read())

        # check if method Initialize works
        if True:

            # create 3D model_part_in
            model = data_structure.Model()
            model_part_in = model.CreateModelPart('wall_in')

            n_in = 10
            n_from=n_in
            x = np.linspace(0, 0.1, n_in)
            r = 1 + 0.07 * np.sin(x * 600)

            x_in = np.zeros(n_from)
            y_in = np.zeros(n_from)
            z_in = np.zeros(n_from)

            i = 0
            for k in range(n_in):
                x_in[i] = x[k]
                y_in[i] = r[k] * np.cos(np.radians(2.5))
                z_in[i] = r[k] * 0
                model_part_in.CreateNewNode(i, x_in[i], y_in[i], z_in[i])
                i += 1

            # create 2D model_part_in
            n_out_ref=n_in
            x_out_ref=np.zeros(n_out_ref)
            y_out_ref=np.zeros(n_out_ref)
            z_out_ref = np.zeros(n_out_ref)

            i_to=0

            for i_from in range(n_from):
                s=y_in[i_from]
                x_out_ref[i_to] = x_in[i_from]
                y_out_ref[i_to] = s / np.cos(np.radians(2.5))
                z_out_ref[i_to] = 0

                i_to += 1
            # initialize mapper to get model_part_out
            mapper = CreateInstance(parameters['mapper'])
            model_part_out = mapper.Initialize(model_part_in, forward=True)

            # get mapped geometry from 2D model_part_out
            n_out = model_part_out.NumberOfNodes()

            x_out = np.zeros(n_out)
            y_out = np.zeros(n_out)
            z_out = np.zeros(n_out)
            for i, node in enumerate(model_part_out.Nodes):
                x_out[i], y_out[i], z_out[i] = node.X0, node.Y0, node.Z0

            # compare mapped and reference geometries
            self.assertEqual(n_out, n_out_ref)
            self.assertListEqual(list(x_out), list(x_out_ref))
            self.assertListEqual(list(y_out), list(y_out_ref))
            self.assertListEqual(list(z_out), list(z_out_ref))

            # check if method __call__ works
        if True:
            def fun_s(x):
                return 1 + 2.5 * x

            def fun_v(x, y, z):
                # r = y / np.cos(np.radians(2.5))
                # theta = np.arctan(r)
                # print("theta")
                # print(theta)
                f_x = 1 + 2.5 * x
                f_y = f_x * 0.5 * y
                # f_y = f_x * 0.5 * np.cos(theta)
                f_z = 0 * z
                # print("fx")
                # print(f_x)
                # print("fy")
                # print(f_y)
                return [f_x, f_y, f_z]

            # create model_part_from (3D)
            var_s = vars(data_structure)["TEMPERATURE"]
            var_v = vars(data_structure)["VELOCITY"]
            model = data_structure.Model()
            model_part_from = model.CreateModelPart('wall_from')
            model_part_from.AddNodalSolutionStepVariable(var_s)
            model_part_from.AddNodalSolutionStepVariable(var_v)


            for i in range(n_from):
                x = x_in[i]
                y = y_in[i]
                z = z_in[i]
                node = model_part_from.CreateNewNode(i, x, y, z)
                node.SetSolutionStepValue(var_s, 0, fun_s(node.X0))
                node.SetSolutionStepValue(var_v, 0, fun_v(node.X0, node.Y0, node.Z0))

            # initialize mapper to get model_part_to (2D)
            mapper = CreateInstance(parameters['mapper'])
            model_part_to = mapper.Initialize(model_part_from, forward=True)

            # check mapped values for Double Variable
            mapper((model_part_from, var_s), (model_part_to, var_s))
            for node in model_part_to.Nodes:
                self.assertAlmostEqual(node.GetSolutionStepValue(var_s),
                                            fun_s(node.X0), delta=1e-8)

            # check mapped values for Array Variable
            mapper((model_part_from, var_v), (model_part_to, var_v))
            for node in model_part_to.Nodes:
                for v1, v2 in zip(list(node.GetSolutionStepValue(var_v)),
                                    fun_v(node.X0, node.Y0, node.Z0)):
                    self.assertAlmostEqual(v1, v2, delta=1e-8)
                    print("v1")
                    print(v1)
                    print("v2")
                    print(v2)
                    if v1 != 0.0:
                        print("a")
                        a = np.abs((v1 - v2) / v1)

                    print(a)

        #Optional:Visual check
        if True:
            if os.getcwd() == os.path.dirname(os.path.abspath(__file__)):
                print('\n\nrunning visual check for whole method')

                # create model_part_from (3D)
                var_s = vars(data_structure)["TEMPERATURE"]
                var_v = vars(data_structure)["VELOCITY"]
                model = data_structure.Model()
                model_part_from = model.CreateModelPart('wall_from')
                model_part_from.AddNodalSolutionStepVariable(var_s)
                model_part_from.AddNodalSolutionStepVariable(var_v)

                n = 10
                for i in range(n):
                    x = x_in[i]
                    y = y_in[i]
                    z = z_in[i]
                    model_part_from.CreateNewNode(i,x,y,z)

                # get model_part_to (2D) from mapper
                mapper = CreateInstance(parameters['mapper'])
                model_part_to = mapper.Initialize(model_part_from, forward=True)

                # for model_part_from (3D): get geometry, set historical variables
                n_from = model_part_from.NumberOfNodes()
                x_from = np.zeros(n_from)
                y_from = np.zeros(n_from)
                z_from = np.zeros(n_from)
                v_s_from = np.zeros(n_from)
                v_v_from = np.zeros((n_from, 3))
                for i, node in enumerate(model_part_from.Nodes):
                    x_from[i], y_from[i], z_from[i] = node.X0, node.Y0, node.Z0
                    # theta = np.arctan2(z_from[i], y_from[i])

                    v_s_from[i] = x_from[i]
                    v_v_from[i] = np.array([1 + x_from[i] * 2.5, 0.5 * y_from[i],
                                            x_from[i] * 0])

                    node.SetSolutionStepValue(var_s, 0, v_s_from[i])
                    node.SetSolutionStepValue(var_v, 0, tuple(v_v_from[i]))

                # map scalar and vector variables
                mapper((model_part_from, var_s), (model_part_to, var_s))
                mapper((model_part_from, var_v), (model_part_to, var_v))

                # for model_part_to (2D): get geometry, get historical variables
                n_to = model_part_to.NumberOfNodes()
                x_to = np.zeros(n_to)
                y_to = np.zeros(n_to)
                z_to = np.zeros(n_to)
                v_s_to = np.zeros(n_to)
                v_v_to = np.zeros((n_to, 3))
                for i, node in enumerate(model_part_to.Nodes):
                    x_to[i], y_to[i], z_to[i] = node.X0, node.Y0, node.Z0
                    v_s_to[i] = node.GetSolutionStepValue(var_s)
                    v_v_to[i, :] = np.array(node.GetSolutionStepValue(var_v))

                # create plot for visual check
                c_from = cm.jet((v_s_from - v_s_from.min()) / (v_s_from.max() - v_s_from.min()))
                c_to = cm.jet((v_s_to - v_s_from.min()) / (v_s_from.max() - v_s_from.min()))

                fig = plt.figure()

                ax_s = fig.add_subplot(121, projection='3d')
                ax_s.set_title('check geometry and scalar mapping')
                ax_s.scatter(x_from, y_from, z_from, s=20, c=c_from, depthshade=True)
                ax_s.scatter(x_to, y_to, z_to, s=50, c=c_to, depthshade=True, marker='s')

                ax_v = fig.add_subplot(122, projection='3d')
                ax_v.set_title('check vector mapping')
                ax_v.quiver(x_from, y_from, z_from, v_v_from[:, 0], v_v_from[:, 1], v_v_from[:, 2],
                            pivot='tail', arrow_length_ratio=0.3, normalize=True, length=0.03)
                ax_v.quiver(x_to, y_to, z_to, v_v_to[:, 0], v_v_to[:, 1], v_v_to[:, 2],
                            pivot='tail', arrow_length_ratio=0.3, normalize=True, length=0.03, colors='r', linewidth=3)

                for ax in [ax_s, ax_v]:
                    ax.set_xlabel('x')
                    ax.set_ylabel('y')
                    ax.set_zlabel('z')
                    ax.set_aspect('equal')

                plt.get_current_fig_manager().window.showMaximized()
                plt.show()
                plt.close()
if __name__ == '__main__':
    KratosUnittest.main()