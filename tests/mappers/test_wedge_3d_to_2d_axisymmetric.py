from coconut import data_structure
from coconut.coupling_components.tools import create_instance

import unittest
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm


class TestMapperAxisymmetric2DTo3D(unittest.TestCase):
    gui = False

    def setUp(self):
        self.parameters = {'type': 'mappers.wedge_3d_to_2d_axisymmetric',
                           'settings':
                               {'direction_axial': 'x',
                                'direction_radial': 'y'}
                           }

    def test_instantiation(self):
        create_instance(self.parameters)

        self.parameters['settings']['direction_axial'] = 'X'
        self.assertRaises(ValueError, create_instance, self.parameters)

        self.parameters['settings']['direction_axial'] = 'x'
        self.parameters['settings']['direction_radial'] = 2
        self.assertRaises(ValueError, create_instance, self.parameters)

    def test_initialize(self):
        mp_name_in = 'wall_in'
        mp_name_out = 'wall_out'

        # create geometry for 3D model_part_in
        n_in = 10
        n_from = n_in
        x = np.linspace(0,0.1, n_in)
        r = 1 + 0.07 * np.sin(x * 600)

        x_in = np.zeros(n_from)
        y_in = np.zeros(n_from)
        z_in = np.zeros(n_from)

        i = 0
        for k in range(n_in):
            x_in[i] = x[k]
            y_in[i] = r[k] * np.cos(np.radians(2.5))
            z_in[i] = 0
            i += 1

        model = data_structure.Model()
        model.create_model_part(mp_name_in, x_in, y_in, z_in, np.arange(n_from))

        # create reference geometry for 2D model_part_out
        n_out_ref = n_in
        x_out_ref = np.zeros(n_out_ref)
        y_out_ref = np.zeros(n_out_ref)
        z_out_ref = np.zeros(n_out_ref)

        i_to = 0

        for i_from in range(n_from):
                r=y_in[i_from]
                x_out_ref[i_to]=x_in[i_from]
                y_out_ref[i_to] = r/np.cos(np.radians(2.5))
                z_out_ref[i_to]=0
                i_to +=1

        # initialize mapper to get model_part_out
        mapper = create_instance(self.parameters)
        mapper.initialize(model, mp_name_in, mp_name_out, forward=True)

        # get mapped geometry from 2D model_part_out
        mp_out = model.get_model_part(mp_name_out)
        n_out = mp_out.size
        x_out = mp_out.x0
        y_out = mp_out.y0
        z_out = mp_out.z0

        # compare mapped and reference geometries
        self.assertEqual(n_out, n_out_ref)
        np.testing.assert_array_equal(x_out, x_out_ref)
        np.testing.assert_array_equal(y_out, y_out_ref)
        np.testing.assert_array_equal(z_out, z_out_ref)

    # def test_call(self):
        def fun_s(x):
            return 1. + 2.5 * x

        def fun_v(x, y, z):
            r = y/np.cos(np.radians(2.5))
            v_x = 1. + 2.5 * x
            v_y = v_x * 0.5 * r
            v_z = 0 * z
            return np.column_stack((v_x, v_y, v_z))

        mp_name_from = 'wall_from'
        mp_name_to = 'wall_to'
        var_s = 'pressure'
        var_v = 'displacement'

        n_in = 10
        n_from = n_in
        tmp = np.linspace(0, 0.05, n_in)
        r_tmp = 0.01*(1. + 0.2 * np.sin(100 * np.pi / 5 * tmp))

        # create model_part_from (3D)
        x_from = np.zeros(n_from)
        y_from = np.zeros(n_from)
        z_from = np.zeros(n_from)

        i = 0
        for k in range(n_in):
            x_from[i] = tmp[k]
            y_from[i] = 0.01*r_tmp[k] * np.cos(np.radians(2.5))
            z_from[i] = r_tmp[k] * 0
            i += 1


        model = data_structure.Model()
        model.create_model_part(mp_name_from, x_from, y_from, z_from, np.arange(n_from))

        parameters_from = [{'model_part': mp_name_from, 'variables': [var_s, var_v]}]
        interface_from = data_structure.Interface(parameters_from, model)

        v_s_from = fun_s(x_from).reshape(-1, 1)
        v_v_from = fun_v(x_from, y_from, z_from)
        interface_from.set_variable_data(mp_name_from, var_s, v_s_from)
        interface_from.set_variable_data(mp_name_from, var_v, v_v_from)


        # initialize mapper to get model_part_to (2D)
        mapper = create_instance(self.parameters)
        mapper.initialize(model, mp_name_from, mp_name_to, forward=True)
        parameters_to = [{'model_part': mp_name_to, 'variables': [var_s, var_v]}]
        interface_to = data_structure.Interface(parameters_to, model)
        mp_to = interface_to.get_model_part(mp_name_to)
        x_to, y_to, z_to = mp_to.x0, mp_to.y0, mp_to.z0

        # check mapped values for 1D variable
        mapper((interface_from, mp_name_from, var_s),
               (interface_to, mp_name_to, var_s))
        v_s_to_ref = fun_s(x_to).reshape(-1, 1)
        v_s_to = interface_to.get_variable_data(mp_name_to, var_s)
        np.testing.assert_allclose(v_s_to, v_s_to_ref, rtol=1e-14)

        # check mapped values for 3D variable
        mapper((interface_from, mp_name_from, var_v),
               (interface_to, mp_name_to, var_v))
        v_v_to_ref = fun_v(x_to, y_to, z_to)
        v_v_to = interface_to.get_variable_data(mp_name_to, var_v)
        np.testing.assert_allclose(v_v_to, v_v_to_ref, rtol=1e-14)


         # extra: visualization
        if self.gui:
            v_s_from, v_s_to = v_s_from.flatten(), v_s_to.flatten()
            c_from = cm.jet((v_s_from - v_s_from.min()) / (v_s_from.max() - v_s_from.min()))
            c_to = cm.jet((v_s_to - v_s_from.min()) / (v_s_from.max() - v_s_from.min()))

            fig = plt.figure()

            ax_s = fig.add_subplot(121, projection='3d')
            ax_s.set_title('check geometry and scalar mapping')
            ax_s.scatter(x_from, y_from, z_from, s=50, c=c_from, depthshade=True, marker='s')
            ax_s.scatter(x_to, y_to, z_to, s=20, c=c_to, depthshade=True)

            ax_v = fig.add_subplot(122, projection='3d')
            ax_v.set_title('check vector mapping')
            ax_v.quiver(x_from, y_from, z_from, v_v_from[:, 0], v_v_from[:, 1], v_v_from[:, 2],
                        pivot='tail', arrow_length_ratio=0.2, normalize=False, length=0.01, colors='r', linewidth=3)
            ax_v.quiver(x_to, y_to, z_to, v_v_to[:, 0], v_v_to[:, 1], v_v_to[:, 2],
                        pivot='tail', arrow_length_ratio=0.2, normalize=False, length=0.01)

            for ax in [ax_s, ax_v]:
                ax.set_xlabel('x')
                ax.set_ylabel('y')
                ax.set_zlabel('z')

            plt.get_current_fig_manager().window.showMaximized()
            # plt.xlim(1,1.25)
            # plt.ylim(0.99,1.02)
            plt.show()
            plt.close()


if __name__ == '__main__':
    unittest.main()
