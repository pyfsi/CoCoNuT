from coconut import data_structure
from coconut.data_structure import KratosUnittest
from coconut.coupling_components.tools import CreateInstance
from coconut.coupling_components.interface import Interface


class TestPredictorConstant(KratosUnittest.TestCase):
    def test_predictor_constant(self):
        m = 10
        dz = 3.0
        a0 = 1.0
        p1 = 1.0
        a1 = 2.0
        p2 = 2.0
        interface_settings = data_structure.Parameters('{"wall": "AREA"}')

        # Create interface
        variable = vars(data_structure)["AREA"]
        model = data_structure.Model()
        model_part = model.CreateModelPart("wall")
        model_part.AddNodalSolutionStepVariable(variable)
        for i in range(m):
            model_part.CreateNewNode(i, 0.0, 0.0, i * dz)
        step = 0
        for node in model_part.Nodes:
            node.SetSolutionStepValue(variable, step, a0)
        interface = Interface(model, interface_settings)

        # Create predictor
        parameter_file_name = "predictors/test_constant.json"
        with open(parameter_file_name, 'r') as parameter_file:
            settings = data_structure.Parameters(parameter_file.read())

        predictor_constant = CreateInstance(settings)
        predictor_constant.Initialize(interface)

        # Test predictor: first prediction needs to be equal to initialized value
        predictor_constant.InitializeSolutionStep()
        prediction = predictor_constant.Predict(interface)
        self.assertIsInstance(prediction, Interface)
        prediction_as_array = prediction.GetNumpyArray()
        for i in range(m):
            self.assertAlmostEqual(p1, prediction_as_array[i])
        interface_as_array = a1 * prediction_as_array
        interface.SetNumpyArray(interface_as_array)
        predictor_constant.Update(interface)
        predictor_constant.FinalizeSolutionStep()

        # Test predictor: second prediction needs to equal to the previous value
        predictor_constant.InitializeSolutionStep()
        prediction = predictor_constant.Predict(interface)
        self.assertIsInstance(prediction, Interface)
        prediction_as_array = prediction.GetNumpyArray()
        for i in range(m):
            self.assertAlmostEqual(p2, prediction_as_array[i])


if __name__ == '__main__':
    KratosUnittest.main()
