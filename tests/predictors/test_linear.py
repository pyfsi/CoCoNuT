from coconut import data_structure
from coconut.data_structure.interface import Interface
from coconut.tools import create_instance

import unittest
import os
import json
import numpy as np


class TestPredictorLinear(unittest.TestCase):

    def test_predictor_linear(self):
        m = 10
        dz = 3
        a0 = 1
        p1 = 1
        a1 = 2
        p2 = 3
        variable = 'area'
        model_part_name = 'wall'
        interface_settings = [{'model_part': model_part_name, 'variables': [variable]}]

        # create model and model_part
        model = data_structure.Model()
        ids = np.arange(0, m)
        x0 = np.zeros(m)
        y0 = np.zeros(m)
        z0 = np.arange(0, m * dz, dz)
        model.create_model_part(model_part_name, x0, y0, z0, ids)

        a0_array = np.full((m, 1), a0)

        # create interface
        interface = Interface(interface_settings, model)
        interface.set_variable_data(model_part_name, variable, a0_array)

        # read settings
        parameter_file_name = os.path.join(os.path.dirname(__file__), 'test_linear.json')
        with open(parameter_file_name, 'r') as parameter_file:
            settings = json.load(parameter_file)

        predictor_linear = create_instance(settings)
        predictor_linear.initialize(interface)

        # first prediction needs to be equal to initialized value
        predictor_linear.initialize_solution_step()
        prediction = predictor_linear.predict(interface)
        self.assertIsInstance(prediction, Interface)
        prediction_as_array = prediction.get_interface_data()
        for i in range(m):
            self.assertAlmostEqual(p1, prediction_as_array[i])
        interface_as_array = a1 * prediction_as_array
        interface.set_interface_data(interface_as_array)
        predictor_linear.update(interface)
        predictor_linear.finalize_solution_step()

        # second prediction needs to be linear
        predictor_linear.initialize_solution_step()
        prediction = predictor_linear.predict(interface)
        self.assertIsInstance(prediction, Interface)
        prediction_as_array = prediction.get_interface_data()
        for i in range(m):
            self.assertAlmostEqual(p2, prediction_as_array[i])


if __name__ == '__main__':
    unittest.main()
