from coconut import data_structure
from coconut import tools

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as ani
from fractions import Fraction


# This file contains the class Animation, which can be used to make an animation, showing a variable on the interface
# for different time steps. Also, a plot of the variable on a certain time step can be made. Alternatively, the
# coordinates of the interface can also be animated using 'coordinates' as variable.
# These Animation instances have to be added to an AnimationFigure instance. All Animations added to the same
# AnimationFigure will be plotted in the same Figure.
# After adding to an AimationFigure,animation has to initialized, specifying which plane of the 3D space to plot in as
# well as which coordinate on the x-axis and possibly which component of the variable has to be plotted.
# An AnimationFigure can hold different Animations from different cases. The code is able to handle different time
# step sizes and starting time steps. The case data is supplied using a results file. To generate such a result file,
# include a non-zero int "save_results" in the settings of the coupled solver.
# Give a name to the case by including the string {"case_name": "a_name"} in the settings of the coupled solver.


class Animation:

    def __init__(self, animation_figure, solution, interface, dt, time_step_start,
                 model_part_name=None, variable=None, name=None):
        """
        Creates Animation instance
            self.info: list e.g. [("mp_a", ["PRESSURE", "TRACTION"]), ("mp_b, "DISPLACEMENT")]
                this dictates the order of the values in solution and coordinates:
                e.g. p0, p1, ..., pm, tx0, ty0, tz0, tx1, ty1, tz1,, ..., txm, tym, tzm, dx0, dy0, dz0, ...,
                    dxm, dym, dzm
                where p and t are pressure and traction on mp_a and d is displacement on mp_b
            self.coordinates: np.array contains the initial coordinates of the nodes on the interface
                as given in self.info
                  e.g. x0, y0, z0, x1, y1, z1, ...
        :param animation_figure: (AnimationFigure) AnimationFigure object where animation is created
        :param solution : (np.array) contains as columns the solution of each time step, order is dictated by self.info
        :param interface: (Interface) object interface to be plotted
        :param dt: (float) time step size
        :param time_step_start: (int) starting time step (typically zero)
        :param model_part_name: (string) model part to be plotted (optional if there is only one)
        :param variable: (string) variable to be plotted (optional if there is only one corresponding to the model part)
        :param name: (string) the name in the legend (optional)
        """
        self.animation_figure = animation_figure
        self.complete_solution = solution
        self.interface = interface
        self.info = interface.model_part_variable_pairs
        self.time_steps = solution.shape[1] - 1  # number of times steps
        self.dt = dt
        self.time_step_start = time_step_start

        # check that model_part_name or variable are given if not unique
        if model_part_name is None:
            if len(set(_[0] for _ in self.info)) > 1:
                raise Exception(f"Specify model_part_name: more than one present: {self.info}")
            else:
                model_part_name = self.info[0][0]
        elif model_part_name not in [_[0] for _ in self.info]:
            raise Exception(f"Given model_part_name '{model_part_name}' is not found")
        self.model_part = self.interface.get_model_part(model_part_name)
        mp_vars = [pair for pair in self.info if pair[0] == model_part_name]
        if variable is None:
            if len(mp_vars) > 1:
                raise Exception(f"Specify variable: more than one present: {[_[1] for _ in mp_vars]}")
            else:
                self.variable = mp_vars[0][1]
        else:
            if variable != variable.lower():
                raise Exception(f"Variable '{variable}' should be lower case")
            if variable not in [_[1] for _ in mp_vars] + ['coordinates']:
                raise Exception(f"Given variable '{variable}' is not found")
            else:
                self.variable = variable

        self.name = name if name is not None else model_part_name + ': ' + variable

        self.coordinates = np.zeros((self.model_part.size, 3))
        for j, direction in enumerate(['x0', 'y0', 'z0']):
            self.coordinates[:, j] = getattr(self.model_part, direction)
        
        self.m = self.model_part.size  # number of nodes

        self.animation = None
        self.mask = None
        self.argsort = None
        self.initial_position = None
        self.abscissa = None
        self.solution = None
        self.displacement = None
        self.line = None
        self.initialized = False

        # find location of data
        index = 0
        self.displacement_available = False
        for mp_name, var in self.info:
            mp = interface.get_model_part(mp_name)
            dimension = data_structure.variables_dimensions[var]
            if var == variable and mp_name == model_part_name:  # correct location
                self.start_index = index
                self.dimension = dimension
                self.end_index = index + self.dimension * self.m
                if self.m != mp.size:
                    raise Exception("Number of coordinates do not match")
            if var == "displacement" and mp_name == model_part_name:  # displacement location
                self.start_index_displacement = index
                self.end_index_displacement = index + 3 * self.m
                self.displacement_available = True
                if self.m != mp.size:
                    raise Exception("Number of coordinates do not match")
            index += dimension * mp.size

        if not self.displacement_available:
            out = f"{self.name} ({model_part_name}: {variable}): Nodes positions are not updated, because no " \
                f"'displacement' available"
            if self.variable == 'coordinates':
                raise Exception(out)
            else:
                tools.print_info(out, layout='warning')

        if index != self.complete_solution.shape[0]:
            raise Exception("Size of provided solution data does not match interface")

    def initialize(self, mask_x, mask_y, mask_z, abscissa, component):
        """
        This method selects which points to plot and how to sort them.
        :param mask_x: (ndarray) selects points based on x-coordinate
        :param mask_y: (ndarray) selects points based on y-coordinate
        :param mask_z: (ndarray) selects points based on z-coordinate
        :param abscissa: (int) abscissa direction: 0 for x-axis, 1 for y-axis and 2 for z-axis
        :param component: (int) which component to plot if variable is vector:
                                0 for x-axis, 1 for y-axis and 2 for z-axis
        """
        # chose which nodes to plot
        self.mask = mask_x & mask_y & mask_z
        if not sum(self.mask):
            raise Exception(f"Intersection of sets of selected coordinates in Initialize is empty\n"
                            f"\tmask_x selects {sum(mask_x)} points\n\tmask_y selects {sum(mask_y)} points\n"
                            f"\tmask_z selects {sum(mask_z)} points")

        # chose sort direction
        self.argsort = np.lexsort((self.coordinates[self.mask, component], self.coordinates[self.mask, abscissa]))
        self.abscissa = self.coordinates[self.mask, abscissa][self.argsort]

        if self.variable == 'coordinates':
            self.initial_position = self.coordinates[self.mask, component][self.argsort]
            self.solution = [self.select_displacement(self.complete_solution[:, i], component) + self.initial_position
                             for i in range(self.time_steps + 1)]
        else:
            if self.dimension == 1:
                component = 0
            self.solution = [self.select(self.complete_solution[:, i], component) for i in range(self.time_steps + 1)]
        if self.displacement_available:
            self.displacement = [self.select_displacement(self.complete_solution[:, i], abscissa)
                                 for i in range(self.time_steps + 1)]

        plt.figure(self.animation_figure.number)  # make figure active
        self.line, = plt.plot(self.abscissa, self.solution[0], label=self.name)

        # adjust scale
        self.animation_figure.update_scale(self)

        self.initialized = True

    def select(self, array, component):
        # select correct model_part and variable data and order them
        return array[self.start_index + component: self.end_index: self.dimension][self.mask][self.argsort]

    def select_displacement(self, array, abscissa):
        # select correct model_part and variable node displacement data and order them
        return array[self.start_index_displacement + abscissa: self.end_index_displacement: 3][self.mask][self.argsort]

    def case_init(self):
        self.line.set_ydata([np.nan] * self.abscissa.size)
        return self.line,

    def case_animate(self, ts):
        if ts < self.time_step_start or ts > self.time_steps + self.time_step_start:
            return self.case_init()
        if self.displacement_available:
            self.line.set_xdata(self.abscissa + self.displacement[ts - self.time_step_start])
        else:
            self.line.set_xdata(self.abscissa)
        self.line.set_ydata(self.solution[ts - self.time_step_start])
        return self.line,


class AnimationFigure:

    def __init__(self):
        self.animations_list = []
        self.animation = None
        self.base_dt = None  # common minimal time step size
        self.dt_ratio_list = []  # ratio of the animation's time step size to the base_dt (list of ints)
        self.time_steps = None  # number of time steps
        self.time_step_start = None
        self.figure = plt.figure()
        self.number = self.figure.number
        self.text = None
        self.print_time = self.print_time_default
        self.time_position = (0.1, 0.1)
        self.min = None
        self.max = None

    def add_animation(self, solution, interface, dt, time_step_start, model_part_name=None, variable=None, name=None):
        """
        Creates and adds Animation instance to self.animations_list.

        :param solution : (np.array) contains as columns the solution of each time step, order is dictated by info
        :param interface: (Interface) object interface to be plotted
        :param dt: (float) time step size
        :param time_step_start: (int) starting time step
        :param model_part_name: (string) model part to be plotted (optional if there is only one)
        :param variable: (string) variable to be plotted (optional if there is only one corresponding to the model part)
                         Use 'coordinates' to plot the coordinates of the interface
        :param name: (string) the name in the legend (optional)
        """
        animation = Animation(self, solution, interface, dt, time_step_start,
                              model_part_name=model_part_name, variable=variable, name=name)

        # add animation instance to class list
        self.animations_list.append(animation)

        # find common denominator for updating time step sizes
        def common_denominator(a, b, max_denominator=1e9):
            """
            Finds common denominator between two floats that have been converted to fractions.
            :param a: First float.
            :param b: Second float.
            :param max_denominator: Max denominator allowed for conversion to fraction.
            :return: Smallest common denominator.
            """
            fraction_a = Fraction(a).limit_denominator(int(max_denominator))
            fraction_b = Fraction(b).limit_denominator(int(max_denominator))
            multiple = np.lcm(fraction_a.denominator, fraction_b.denominator)
            return multiple

        # update base time step size and time steps for previously defined animations
        # update starting time step and number of time steps
        if self.base_dt is None:
            self.base_dt = animation.dt
            self.dt_ratio_list.append(1)
            self.time_step_start = animation.time_step_start
            self.time_steps = animation.time_steps
        else:
            base_dt_prev = self.base_dt
            self.base_dt = 1 / common_denominator(self.base_dt, animation.dt)
            update_factor = int(base_dt_prev / self.base_dt)
            self.dt_ratio_list = [int(dt_ratio * update_factor) for dt_ratio in self.dt_ratio_list]
            self.dt_ratio_list.append(int(animation.dt / self.base_dt))
            self.time_steps = max(self.time_step_start + (self.time_steps + 1) * update_factor - 1,
                                  animation.time_step_start + (animation.time_steps + 1)
                                  * int(animation.dt / self.base_dt) - 1)
            self.time_step_start = min(self.time_step_start, animation.time_step_start)

        return animation

    def update_scale(self, animation):
        # adjust scale
        minimum = min([s.min() for s in animation.solution])
        maximum = max([s.max() for s in animation.solution])
        self.min = minimum if self.min is None else min(self.min, minimum)
        self.max = maximum if self.max is None else max(self.max, maximum)
        margin = (self.max - self.min) * 0.05
        plt.figure(self.number)  # make figure active
        plt.ylim([self.min - margin, self.max + margin])

    def init(self):  # only required for blitting to give a clean slate.
        lines = ()
        for animation in self.animations_list:
            lines += animation.case_init()
        return lines

    def animate(self, ts):
        lines = ()
        for animation, dt_ratio in zip(self.animations_list, self.dt_ratio_list):
            lines += animation.case_animate(ts // dt_ratio)
        if self.text is None:
            plt.figure(self.number)  # make figure active
            self.text = plt.text(self.time_position[0], self.time_position[1], self.print_time(0),
                                 transform=self.figure.axes[0].transAxes,
                                 bbox=dict(facecolor='lightgray', edgecolor='black', pad=5.0, alpha=0.5))
        self.text.set_text(self.print_time(ts * self.base_dt))
        return lines

    def print_time_default(self, time):
        if self.base_dt >= 1e-4:
            return f"time = {time:.4f} s"
        else:
            return f"time = {time * 1e6:.3f} µs"

    def make_animation(self, interval=100, blit=False, save_count=100, repeat=True, frames=None):
        # inteval: interval between frames in ms
        # frames: (int) number of frames (<= number of time steps + 1)
        #         (iterable) frames to plot (index <= number of time steps)
        if not self.animations_list:
            raise Exception("No Animations have been added to this AnimationFigure")
        for animation in self.animations_list:
            if not animation.initialized:
                raise Exception(f"Animate object {animation.name} has not yet been initialized")
        if frames is None:
            frames = range(self.time_step_start, self.time_step_start + self.time_steps + 1)
        elif type(frames) is int:
            if not (0 < frames <= self.time_steps + 1):
                raise Exception(f"Time step out of range: maximum number of frames is {self.time_steps + 1} (number of "
                                f"time steps + 1), with time step size {self.base_dt} "
                                f"and starting time step {self.time_step_start}")
            else:
                frames = range(self.time_step_start, self.time_step_start + frames)
        elif min(frames) < self.time_step_start or max(frames) > self.time_step_start + self.time_steps:
            raise Exception(f"Time step out of range: maximum time step is {self.time_steps}, "
                            f"with time step size {self.base_dt} and starting time step {self.time_step_start}")
        self.animation = ani.FuncAnimation(self.figure, self.animate, init_func=self.init, interval=interval,
                                           blit=blit, save_count=save_count, repeat=repeat, frames=frames)

    def make_plot(self, time_step):
        # time_step: time step at which plot is made
        if not self.animations_list:
            raise Exception("No Animations have been added to this AnimationFigure")
        for animation in self.animations_list:
            if not animation.initialized:
                raise Exception("Animate object has not yet been initialized")
        if time_step < self.time_step_start or self.time_steps > self.time_steps:
            raise Exception(f"Time step out of range: \nminimum time step: {self.time_step_start}"
                            f"\nmaximum time step: {self.time_steps + self.time_step_start}"
                            f"\nwith time step size {self.base_dt}")
        self.animate(time_step)
