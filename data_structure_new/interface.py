from coconut.data_structure_new.variables import variables_dimensions
from coconut.data_structure_new.model import Model

import numpy as np
import copy


class Interface:

    def __init__(self, parameters, model):
        self.__model = model
        self.__parameters = parameters
        self.__data = {}

        if not type(model) == Model:
            raise TypeError('model should be an instance of the class Model')
        if not type(parameters) == dict:
            raise TypeError('parameters should be a dictionary with model parts as key '
                            'and a list of variables as values')

        for model_part_name in parameters:
            model_part = model.get_model_part(model_part_name)
            self.__data[model_part_name] = {}
            for variable in parameters[model_part_name]:
                if variable not in variables_dimensions:
                    raise ValueError(f'invalid variable name "{variable}"')
                shape = (model_part.size, variables_dimensions[variable])
                self.__data[model_part_name][variable] = np.zeros(shape)

        tmp = []
        for model_part_name in self.parameters:
            for variable in self.parameters[model_part_name]:
                tmp.append((model_part_name, variable))
        self.__model_part_variable_pairs = tmp

    @property
    def model_part_variable_pairs(self):
        return copy.deepcopy(self.__model_part_variable_pairs)

    @property
    def parameters(self):
        return copy.deepcopy(self.__parameters)

    @property
    def size(self):
        s = 0
        for model_part_name, variable in self.model_part_variable_pairs:
            s += self.__data[model_part_name][variable].size
        return s

    def copy(self):
        # create new Interface
        interface = Interface(self.parameters, self.__model)

        # copy data
        interface += self  # uses fast __iadd__ method to transfer data

        return interface

    def __repr__(self):
        repr = 'Interface that refers to ModelParts'
        for model_part_name in self.parameters:
            model_part = self.__model.get_model_part(model_part_name)
            repr += f'\n\t"{model_part.name}" of size {model_part.size} with variables'
            for variable in self.__data[model_part_name]:
                repr += f'\n\t\t{variable} with {variables_dimensions[variable]} components'
        return repr

    def get_variable_data(self, model_part_name, variable):
        # *** always returns copies!
        if (model_part_name, variable) not in self.model_part_variable_pairs:
            raise KeyError
        return self.__data[model_part_name][variable].copy()

    def set_variable_data(self, model_part_name, variable, data):
        # *** this changes the original data!
        if type(data) is not np.ndarray:
            raise ValueError(f'data is of type {type(data)}, but must be ndarray')
        shape = self.__data[model_part_name][variable].shape
        if data.shape != shape:
            raise ValueError(f'ndarray has shape {data.shape} instead of shape {shape}')
        self.__data[model_part_name][variable] = data.copy()

    def get_interface_data(self):
        data = np.empty(0)
        for model_part_name, variable in self.model_part_variable_pairs:
            data = np.concatenate((data, self.get_variable_data(model_part_name, variable).flatten()))
        return data

    def set_interface_data(self, data):
        if type(data) is not np.ndarray:
            raise ValueError(f'data is of type {type(data)}, but must be ndarray')
        if data.shape != (self.size,):
            raise ValueError(f'ndarray has shape {data.shape} instead of shape {(self.size,)}')
        index = 0
        for model_part_name, variable in self.model_part_variable_pairs:
            tmp = self.get_variable_data(model_part_name, variable)
            self.set_variable_data(model_part_name, variable,
                                   data[index:index + tmp.size].reshape(tmp.shape))
            index += tmp.size

    def norm(self, order=2):
        return np.linalg.norm(self.get_interface_data(), order)

    def __add__(self, other):
        result = self.copy()
        if type(other) is Interface:
            for model_part_name, variable in self.model_part_variable_pairs:
                result.__data[model_part_name][variable] += other.__data[model_part_name][variable]
        elif type(other) in (int, float, np.integer, np.floating):
            for model_part_name, variable in self.model_part_variable_pairs:
                result.__data[model_part_name][variable] += other
        else:
            return NotImplemented
        return result

    def __radd__(self, other):
        return self.__add__(other)

    def __iadd__(self, other):
        if type(other) is Interface:
            for model_part_name, variable in self.model_part_variable_pairs:
                self.__data[model_part_name][variable] += other.__data[model_part_name][variable]
        else:
            return NotImplemented
        return self

    def __sub__(self, other):
        result = self.copy()
        if type(other) is Interface:
            for model_part_name, variable in self.model_part_variable_pairs:
                result.__data[model_part_name][variable] -= other.__data[model_part_name][variable]
        elif type(other) in (int, float, np.integer, np.floating):
            for model_part_name, variable in self.model_part_variable_pairs:
                result.__data[model_part_name][variable] -= other
        else:
            return NotImplemented
        return result

    def __rsub__(self, other):
        return self.__sub__(other)

    def __isub__(self, other):
        if type(other) is Interface:
            for model_part_name, variable in self.model_part_variable_pairs:
                self.__data[model_part_name][variable] -= other.__data[model_part_name][variable]
        elif type(other) in (int, float, np.integer, np.floating):
            for model_part_name, variable in self.model_part_variable_pairs:
                self.__data[model_part_name][variable] -= other
        else:
            return NotImplemented
        return self

    def __mul__(self, other):
        result = self.copy()
        if type(other) in (int, float, np.integer, np.floating):
            for model_part_name, variable in self.model_part_variable_pairs:
                result.__data[model_part_name][variable] *= other
        else:
            return NotImplemented
        return result

    def __rmul__(self, other):
        return self.__mul__(other)

    def __imul__(self, other):
        if type(other) in (int, float, np.integer, np.floating):
            for model_part_name, variable in self.model_part_variable_pairs:
                self.__data[model_part_name][variable] *= other
        else:
            return NotImplemented
        return self

    def __truediv__(self, other):
        result = self.copy()
        if type(other) in (int, float, np.integer, np.floating):
            for model_part_name, variable in self.model_part_variable_pairs:
                result.__data[model_part_name][variable] /= other
        else:
            return NotImplemented
        return result
