from coconut import data_structure
import unittest
from coconut.coupling_components.interface import Interface

import os


class TestPyKratosParameters(unittest.TestCase):
    def test_pykratos_parameters(self):
        parameter_file_name = os.path.join(os.path.dirname(__file__), 'test_parameters.json')
        with open(parameter_file_name, 'r') as parameter_file:
            par = data_structure.Parameters(parameter_file.read())

        # check if correct type is returned
        self.assertIsInstance(par, data_structure.Parameters)
        self.assertIsInstance(par['sub_parameters'], data_structure.Parameters)
        self.assertIsInstance(par['test_list'], data_structure.Parameters)
        self.assertIsInstance(par['test_int'], data_structure.Parameters)
        self.assertIsInstance(par['test_int'].GetInt(), int)

        # test getters and setters
        par.SetInt('test_int', 2)
        par.SetDouble('test_float', 2.2)
        par.SetBool('test_bool', False)
        par.SetString('test_str', 'two')
        par.SetArray('test_array', [0, 2.3, 'four'])
        self.assertEqual(par['test_int'].GetInt(), 2)
        self.assertEqual(par['test_float'].GetDouble(), 2.2)
        self.assertEqual(par['test_bool'].GetBool(), False)
        self.assertEqual(par['test_str'].GetString(), 'two')
        self.assertEqual(par['test_array'].GetArray(), [0, 2.3, 'four'])

        # test AddMissingParameters
        par_missing = par['sub_parameters']
        par.AddMissingParameters(par_missing)
        self.assertEqual(par['test_int'].GetInt(), 2)
        self.assertEqual(par['test_float'].GetDouble(), 2.2)
        self.assertEqual(par['test_str'].GetString(), 'two')
        self.assertEqual(par['missing_int'].GetInt(), 5)
        self.assertEqual(par['missing_float'].GetDouble(), 5.5)
        self.assertEqual(par['missing_str'].GetString(), 'five')

        # test AddValue
        par.AddValue('added_value', par['test_int'])
        self.assertEqual(par['added_value'].GetInt(), 2)
        par.AddValue('added_value', par['test_float'])
        self.assertEqual(par['added_value'].GetDouble(), 2.2)

        # test AddEmptyValue
        self.assertIsNone(par.AddEmptyValue('empty'))

        # test RemoveValue
        par.RemoveValue('not_a_value')
        par.RemoveValue('added_value')
        par.RemoveValue('empty')

        # test list
        self.assertIsInstance(par['test_list'].list(), list)
        self.assertIsInstance(par['test_int'].list(), list)
        self.assertEqual(len(par['test_list'].list()), par['test_list'].size())
        self.assertEqual(len(par['test_int'].list()), 1)

        # print output of test
        if False:
            print('\nTestPyKratosParameters successful.\n')
            self.assertTrue(False)


if __name__ == '__main__':
    unittest.main()
