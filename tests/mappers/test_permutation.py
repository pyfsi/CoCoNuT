from coconut import data_structure
from coconut.data_structure import KratosUnittest
from coconut.coupling_components.tools import CreateInstance

import numpy as np
import os


class TestMapperPermutation(KratosUnittest.TestCase):
    def test_mapper_permutation(self):
        parameter_file_name = os.path.join(os.path.dirname(__file__), 'test_permutation.json')
        with open(parameter_file_name, 'r') as parameter_file:
            parameters = data_structure.Parameters(parameter_file.read())

        # check if method Initialize works
        if True:
            var = vars(data_structure)["TEMPERATURE"]
            model = data_structure.Model()
            model_part_from = model.CreateModelPart('wall_from')
            model_part_from.AddNodalSolutionStepVariable(var)

            model_part_from.CreateNewNode(0, 0., 1., 2.)

            # model_part_from given
            mapper = CreateInstance(parameters['mapper'])
            model_part_to = mapper.Initialize(model_part_from, forward=True)
            node = model_part_to.Nodes[0]
            self.assertListEqual([node.X0, node.Y0, node.Z0], [2., 0., 1.])

            # model_part_to given
            mapper = CreateInstance(parameters['mapper'])
            model_part_from = mapper.Initialize(model_part_to, forward=False)
            node = model_part_from.Nodes[0]
            self.assertListEqual([node.X0, node.Y0, node.Z0], [0., 1., 2.])

        # check if method __call__ works for Double Variable
        if True:
            var = vars(data_structure)["TEMPERATURE"]
            model = data_structure.Model()
            model_part_from = model.CreateModelPart('wall_from')
            model_part_from.AddNodalSolutionStepVariable(var)

            for i in range(10):
                node = model_part_from.CreateNewNode(i, i * 1., i * 2., i * 3.)
                node.SetSolutionStepValue(var, 0, np.random.rand())

            mapper = CreateInstance(parameters['mapper'])
            model_part_to = mapper.Initialize(model_part_from, forward=True)
            mapper((model_part_from, var), (model_part_to, var))

            for node_from, node_to in zip(model_part_from.Nodes, model_part_to.Nodes):
                val_from = node_from.GetSolutionStepValue(var)
                val_to = node_to.GetSolutionStepValue(var)
                self.assertEqual(val_from, val_to)

        # check if method __call__ works for Array Variable
        if True:
            var = vars(data_structure)["DISPLACEMENT"]
            model = data_structure.Model()
            model_part_from = model.CreateModelPart('wall_from')
            model_part_from.AddNodalSolutionStepVariable(var)

            for i in range(10):
                node = model_part_from.CreateNewNode(i, i * 1., i * 2., i * 3.)
                node.SetSolutionStepValue(var, 0, list(np.random.rand(3)))

            mapper = CreateInstance(parameters['mapper'])
            model_part_to = mapper.Initialize(model_part_from, forward=True)
            mapper((model_part_from, var), (model_part_to, var))

            for node_from, node_to in zip(model_part_from.Nodes, model_part_to.Nodes):
                val_from = node_from.GetSolutionStepValue(var)
                val_from = list(np.array(val_from)[mapper.permutation])
                val_to = node_to.GetSolutionStepValue(var)
                self.assertListEqual(val_from, val_to)


if __name__ == '__main__':
    KratosUnittest.main()
