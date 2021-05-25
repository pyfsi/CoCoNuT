from coconut import data_structure
from coconut.data_structure.interface import Interface
from coconut.tools import create_instance

import unittest
import numpy as np


class TestPredictorConstant(unittest.TestCase):

    def test_predictor_constant(self):
        m = 10
        dz = 3
        a0 = 1
        p1 = 1
        a1 = 2
        p2 = 2
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

        # create predictor
        parameters = {'type': 'predictors.constant'}
        predictor_constant = create_instance(parameters)
        predictor_constant.initialize(interface)

        # first prediction needs to be equal to initialized value
        predictor_constant.initialize_solution_step()
        prediction = predictor_constant.predict(interface)
        self.assertIsInstance(prediction, Interface)
        prediction_as_array = prediction.get_interface_data()
        for i in range(m):
            self.assertAlmostEqual(p1, prediction_as_array[i])
        interface_as_array = a1 * prediction_as_array
        interface.set_interface_data(interface_as_array)
        predictor_constant.update(interface)
        predictor_constant.finalize_solution_step()

        # second prediction needs to equal to the previous value
        predictor_constant.initialize_solution_step()
        prediction = predictor_constant.predict(interface)
        self.assertIsInstance(prediction, Interface)
        prediction_as_array = prediction.get_interface_data()
        for i in range(m):
            self.assertAlmostEqual(p2, prediction_as_array[i])


if __name__ == '__main__':
    unittest.main()
