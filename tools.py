import time
from contextlib import contextmanager
import numpy as np
import warnings
import os
import subprocess
import pickle


def create_instance(settings):
    # create instance of given class based on settings dict
    object_type = settings['type']
    object_module = __import__('coconut.coupling_components.' + object_type, fromlist=[object_type])
    return object_module.create(settings)


class LayoutStyles:
    styles = {'plain': '\033[0m',
              'bold': '\033[1m',
              'underline': '\033[4m',
              'inverse': '\033[7m',
              'negative': '\033[97m',
              'warning': '\033[91m',
              'fail': '\033[41m',
              'grey': '\033[90m',
              'red': '\033[91m',
              'green': '\033[92m',
              'yellow': '\033[93m',
              'blue': '\033[94m',
              'magenta': '\033[95m',
              'cyan': '\033[96m',
              'white': '\033[1;8m',
              'black': '\033[1;90m',
              }

    def get(self, layout):
        self.check(layout)
        return self.styles[layout]

    def check(self, layout):
        if layout not in self.styles:
            raise ValueError("Layout style is not implemented, correct layout styles are:"
                             "header, blue, green, red, warning, fail, bold, underline and plain.")


layout_style = LayoutStyles()


# print_info: printing with color
#  @param args          The arguments to be printed
#  @param layout        The layout to be used: header, blue, green, red, warning, fail, bold, underline or plain
def print_info(*args, layout=None, **kwargs):
    if layout is None:
        print("".join(map(str, args)), **kwargs)
    else:
        print(layout_style.get(layout), "".join(map(str, args)), layout_style.get('plain'), **kwargs)


# updatePre: update preceding text, used in structure printing
#  @param pre         Preceding text ending with '├─' or '└─'
def update_pre(pre):
    """
    This function is used to update the preceding string in a structured tree-like format as such:
    Name
    ├─Name
    │ XXX
    └─Name
      XXX
    """
    if pre[-2:] == '├─':
        pre = pre[:-2] + '│ '
    elif pre[-2:] == '└─':
        pre = pre[:-2] + '  '
    elif len(pre) < 2 or pre[-2] == '  ':
        pass
    else:
        raise Exception(f"Info structure failed: last two characters not recognized: '{pre}'")
    return pre


# printInfoStructure: print information from a list of Components in a structured way
#  @param label         Preceding text ending with '├─' or '└─'
#  @param compent_list  List of Components from which the info is printed
def print_components_info(pre, component_list):
    """
    This function accepts a list of Components and print their info in a structured tree-like format as such:
    ├─Component0.PrintInfo
    │ XXX
    └─Component1.PrintInfo
      XXX
    """
    pre = update_pre(pre)
    for component in component_list[:-1]:
        component.print_components_info(pre + '├─')
    component_list[-1].print_components_info(pre + '└─')


# timer-function
@contextmanager
def quick_timer(name=None, t=0, n=0, ms=False):
    """
    Contextmanager that prints the time to execute a piece of code.

    Nothing is recorded/saved, this is meant mainly
    as a quick tool to check how long specific
    (parts of) calculations take during development.

    name: printed to identify the timer
    t, n: integers to specify number of tabs and new
          lines respectively
    ms:   print time in ms (default is s)


    example:
        with tools.quicktimer('test', ms=True):
            a = 1 / 3
    """
    start_time = time.time()
    yield
    elapsed_time = time.time() - start_time
    if ms:
        s = '\n' * n + '\t' * t + f'{elapsed_time * 1000:.2f}ms'
        s.replace(',', ' ')
    else:
        s = '\n' * n + '\t' * t + f'{elapsed_time:.1f}s'
    if name is not None:
        s += f' - {name}'
    s += '\n' * n
    print(s)


# run time measuring function
def time_solve_solution_step(solve_solution_step):
    def wrapper(*args):
        self = args[0]
        if not hasattr(self, 'run_time'):
            self.run_time = 0.0
        start_time = time.time()
        interface_output = solve_solution_step(*args)
        self.run_time += time.time() - start_time
        return interface_output

    return wrapper


# pass on parameters
def pass_on_parameters(settings_from, settings_to, keys):
    for key in keys:
        if key in settings_to:
            print_info(f'WARNING: parameter "{key}" is defined multiple times in JSON file', layout='warning')
        settings_to[key] = settings_from[key]


# compare bounding box of ModelParts
def check_bounding_box(mp_a, mp_b, tol_center_warning=.02, tol_center_error=100,
                       tol_minmax_warning=.1, tol_minmax_error=10):
    """
    Use this function to compare the bounding boxes of 2 ModelParts.

    mp_a and mp_b are the two ModelParts.

    There are 4 keyword arguments, to overwrite the
    default tolerances:
        tol_center_warning = 0.02
        tol_center_error = 0.1
        tol_minmax_warning = 0.1
        tol_minmax_error = 0.3

    Returns nothing.
    """
    # extract coordinate data
    mp_a_coords = np.column_stack((mp_a.x0, mp_a.y0, mp_a.z0))
    mp_b_coords = np.column_stack((mp_b.x0, mp_b.y0, mp_b.z0))

    # get bounding boxes
    mp_a_min = mp_a_coords.min(axis=0)
    mp_a_max = mp_a_coords.max(axis=0)
    mp_b_min = mp_b_coords.min(axis=0)
    mp_b_max = mp_b_coords.max(axis=0)
    mp_a_center = (mp_a_min + mp_a_max) / 2
    mp_b_center = (mp_b_min + mp_b_max) / 2

    # get reference distance (= average length of bounding box diagonal)
    mp_a_diag = mp_a_max - mp_a_min
    mp_b_diag = mp_b_max - mp_b_min
    d_ref = np.linalg.norm((mp_a_diag + mp_b_diag) / 2)

    # calculate errors on bounding boxes
    error_center = np.linalg.norm(mp_a_center - mp_b_center) / d_ref
    error_min = np.linalg.norm(mp_a_min - mp_b_min) / d_ref
    error_max = np.linalg.norm(mp_a_max - mp_b_max) / d_ref

    # raise warning or error if necessary
    msg_1 = f'ModelParts "{mp_a.name}", "{mp_b.name}": '
    msg_2 = ' values differ by '
    msg_3 = f'\n\t"{mp_a.name}": minimal values = {mp_a_min} and maximal values = {mp_a_max}' \
            f'\n\t"{mp_b.name}": minimal values = {mp_b_min} and maximal values = {mp_b_max}'

    # msg = f'{msg_1}center{msg_2}{100 * error_center:.1f}%' + msg_3
    # if error_center > tol_center_error:
    #     raise ValueError(msg)
    # if error_center > tol_center_warning:
    #     warnings.warn(msg, Warning)
    #
    # msg = f'{msg_1}min{msg_2}{100 * error_min:.1f}%' + msg_3
    # if error_min > tol_minmax_error:
    #     raise ValueError(msg)
    # if error_min > tol_minmax_warning:
    #     warnings.warn(msg, Warning)

    # msg = f'{msg_1}max{msg_2}{100 * error_max:.1f}%' + msg_3
    # if error_max > tol_minmax_error:
    #     raise ValueError(msg)
    # if error_max > tol_minmax_warning:
    #     warnings.warn(msg, Warning)
