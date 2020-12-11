from coconut.coupling_components.component import Component
from coconut.coupling_components import tools
from coconut.data_structure import Model, Interface

import numpy as np
import os.path as path
from scipy.linalg import solve_banded


def create(parameters):
    return SolverWrapperTubeFlow(parameters)


class SolverWrapperTubeFlow(Component):
    al = 4  # Number of terms below diagonal in matrix
    au = 4  # Number of terms above diagonal in matrix

    def __init__(self, parameters):
        super().__init__()

        # Reading
        self.parameters = parameters
        self.settings = parameters["settings"]
        self.working_directory = self.settings["working_directory"]
        input_file = self.settings["input_file"]
        case_file_name = path.join(self.working_directory, input_file)
        with open(case_file_name, 'r') as case_file:
            self.settings.update(case_file.read())  # TODO: inversed priority

        # Settings
        self.unsteady = self.settings.get("unsteady", True)

        l = self.settings["l"]  # Length
        self.d = self.settings["d"]  # Diameter
        self.rhof = self.settings["rhof"]  # Density

        self.ureference = self.settings["ureference"]  # Reference velocity
        self.u0 = self.settings.get("u0", self.ureference)  # Initial velocity
        self.inlet_boundary = self.settings["inlet_boundary"]
        self.inlet_variable = self.inlet_boundary["variable"]  # Variable upon which boundary condition is specified
        if self.inlet_variable == "velocity":
            self.inlet_reference = self.inlet_boundary.get("reference", self.ureference)  # Reference of velocity inlet boundary condition
        elif self.inlet_variable == "pressure":
            self.inlet_reference = self.inlet_boundary.get("reference", self.preference)  # Reference of pressure inlet boundary condition
        elif self.inlet_variable == "total_pressure":
            self.inlet_reference = self.inlet_boundary.get("reference", self.preference + self.ureference ** 2 / 2)  # Reference of total_pressure inlet boundary condition
        else:
            raise ValueError(f"The inlet_variable \'{self.inlet_variable}\' is not implemented,"
                             f" choose between \'pressure\', \'total_pressure\' and \'velocity\'")
        self.inlet_type = self.inlet_boundary["type"]  # Type of inlet boundary condition
        self.inlet_amplitude = self.inlet_boundary["amplitude"]  # Amplitude of inlet boundary condition
        if not self.inlet_type == 4:
            self.inlet_period = self.inlet_boundary["period"]  # Period of inlet boundary condition

        self.outlet_boundary = self.settings["outlet_boundary"]
        self.outlet_type = self.outlet_boundary["type"]  # Type of outlet boundary condition
        self.outlet_amplitude = self.outlet_boundary.get("amplitude", self.preference)  # Amplitude of outlet boundary condition

        # Adjust to kinematic pressure
        if self.inlet_variable in {"pressure", "total_pressure"}:
            self.inlet_reference = self.inlet_reference / self.rhof
            self.inlet_amplitude = self.inlet_amplitude / self.rhof
        self.outlet_amplitude = self.outlet_amplitude / self.rhof
        self.preference = self.preference / self.rhof

        e = self.settings["e"].GetDouble()  # Young"s modulus of structure
        h = self.settings["h"].GetDouble()  # Thickness of structure
        self.cmk2 = (e * h) / (self.rhof * self.d)  # Wave speed squared of outlet boundary condition

        self.m = self.settings["m"].GetInt()  # Number of segments
        self.dz = l / self.m  # Segment length
        axial_offset = self.settings.get("axial_offset", 0)  # Start position along axis
        self.z = axial_offset + np.arange(self.dz / 2, l, self.dz)  # Data is stored in cell centers

        self.k = 0  # Iteration
        self.n = 0  # Time step (no restart implemented)
        if self.unsteady:
            self.dt = self.settings["delta_t"]  # Time step size
            self.alpha = np.pi * self.d ** 2 / 4 / (self.ureference + self.dz / self.dt)  # Numerical damping parameter due to central discretization of pressure in momentum equation
        else:
            self.dt = 1  # Time step size default value
            self.alpha = np.pi * self.d ** 2 / 4 / self.ureference  # Numerical damping parameter due to central discretization of pressure in momentum equation

        self.newtonmax = self.settings["newtonmax"]  # Maximal number of Newton iterations
        self.newtontol = self.settings["newtontol"]  # Tolerance of Newton iterations

        # Initialization
        self.u = np.ones(self.m + 2) * self.u0  # Velocity
        self.un = np.array(self.u)  # Previous velocity
        self.p = np.ones(self.m + 2) * self.preference  # Kinematic pressure
        self.pn = np.array(self.p)  # Previous kinematic pressure (only value at outlet is used)
        self.a = np.ones(self.m + 2) * np.pi * self.d ** 2 / 4  # Area of cross section
        self.an = np.array(self.a)  # Previous area of cross section

        self.disp = np.zeros((self.m, 3))  # Displacement
        self.pres = np.zeros(self.m)  # Pressure
        self.trac = np.zeros((self.m, 3))  # Traction

        self.conditioning = self.alpha  # Factor for conditioning Jacobian

        # ModelParts
        self.model = Model()
        self.model_part = self.model.create_model_part("wall", np.zeros(self.m), self.d / 2 * np.ones(self.m), self.z,
                                                       np.arange(self.m))  # TODO not use hardcoded mp name

        # Interfaces
        self.interface_input = Interface(self.settings["interface_input"], self.model)
        self.interface_input.set_variable_data("wall", "displacement", self.disp)
        self.interface_output = Interface(self.model, self.settings["interface_output"])
        self.interface_input.set_variable_data("wall", "pressure", self.pres)
        self.interface_input.set_variable_data("wall", "traction", self.trac)
        
        # run time
        self.run_time = 0

        # Debug
        self.debug = False  # Set on True to save input and output of each iteration of every time step
        self.output_solution_step()

    def initialize(self):
        super().initialize()

    def initialize_solution_step(self):
        super().initialize_solution_step()

        self.k = 0
        self.n += 1
        self.un = np.array(self.u)
        self.pn = np.array(self.p)
        self.an = np.array(self.a)

    @tools.time_solve_solution_step
    def solve_solution_step(self, interface_input):
        # Input
        self.interface_input = interface_input.copy()
        self.disp = interface_input.get_variable_data("wall", "displacement")
        a = np.pi * (self.d + 2 * self.disp[:, 1]) ** 2 / 4

        # Input does not contain boundary conditions
        self.a[1:self.m + 1] = a
        self.a[0] = self.a[1]
        self.a[self.m + 1] = self.a[self.m]

        # Newton iterations
        converged = False
        f = self.get_residual()
        residual0 = np.linalg.norm(f)
        if residual0:
            for s in range(self.newtonmax):
                j = self.get_jacobian()
                b = -f
                x = solve_banded((self.al, self.au), j, b)
                self.u += x[0::2]
                self.p += x[1::2]
                if self.inlet_variable == "velocity":
                    self.u[0] = self.get_inlet_boundary()
                elif self.inlet_variable == "pressure":
                    self.p[0] = self.get_inlet_boundary()
                f = self.get_residual()
                residual = np.linalg.norm(f)
                if residual / residual0 < self.newtontol:
                    converged = True
                    break
            if not converged:
                Exception("Newton failed to converge")

        self.k += 1
        if self.debug:
            file_name = self.working_directory + f"/Input_Displacement_TS{self.n}_IT{self.k}.txt"
            with open(file_name, 'w') as file:
                file.write(f"{'z-coordinate':<22}\t{'x-displacement':<22}\t{'y-displacement':<22}"
                           f"\t{'z-displacement':<22}\n")
                for i in range(len(self.z)):
                    file.write(f'{self.z[i]:<22}\t{self.disp[i, 0]:<22}\t{self.disp[i, 1]:<22}'
                               f'\t{self.disp[i, 2]:<22}\n')
            p = self.p[1:self.m + 1] * self.rhof
            u = self.u[1:self.m + 1]
            file_name = self.working_directory + f"/Output_Pressure_Velocity_TS{self.n}_IT{self.k}.txt"
            with open(file_name, 'w') as file:
                file.write(f"{'z-coordinate':<22}\t{'pressure':<22}\t{'velocity':<22}\n")
                for i in range(len(self.z)):
                    file.write(f"{self.z[i]:<22}\t{p[i]:<22}\t{u[i]:<22}\n")

        # Output does not contain boundary conditions
        self.pres = self.p[1:self.m + 1] * self.rhof
        self.interface_output.set_variable_data("wall", "pressure", self.pres)
        self.interface_output.set_variable_data("wall", "traction", self.trac)
        return self.interface_output  # TODO: make copy?

    def finalize__solution_step(self):
        super().finalize__solution_step()

    def finalize(self):
        super().finalize()

    def output_solution_step(self):
        if self.debug:
            p = self.p[1:self.m + 1] * self.rhof
            u = self.u[1:self.m + 1]
            file_name = self.working_directory + f"/Pressure_Velocity_TS{self.n}.txt"
            with open(file_name, 'w') as file:
                file.write(f"{'z-coordinate':<22}\t{'pressure':<22}\t{'velocity':<22}\n")
                for i in range(len(self.z)):
                    file.write(f"{self.z[i]:<22}\t{p[i]:<22}\t{u[i]:<22}\n")

    def get_interface_input(self):  # TODO: need to have latest data?
        return self.interface_input.copy()

    def set_interface_input(self):  # TODO: remove?
        raise Exception("This solver interface provides no mapping.")

    def get_interface_output(self):  # TODO: need to have latest data?
        return self.interface_output.copy()

    def set_interface_output(self):  # TODO: remove?
        raise Exception("This solver interface provides no mapping.")

    def get_inlet_boundary(self):
        if self.inlet_type == 1:
            x = self.inlet_reference \
                + self.inlet_amplitude * np.sin(2 * np.pi * (self.n * self.dt) / self.inlet_period)
        elif self.inlet_type == 2:
            x = self.inlet_reference + (self.inlet_amplitude if self.n <= self.inlet_period / self.dt else 0)
        elif self.inlet_type == 3:
            x = self.inlet_reference \
                + self.inlet_amplitude * (np.sin(np.pi * (self.n * self.dt) / self.inlet_period)) ** 2
        elif self.inlet_type == 4:
            x = self.inlet_reference + self.inlet_amplitude
        else:
            x = self.inlet_reference + self.inlet_amplitude * (self.n * self.dt) / self.inlet_period
        return x

    def get_residual(self):
        usign = self.u[1:self.m + 1] > 0
        ur = self.u[1:self.m + 1] * usign + self.u[2:self.m + 2] * (1.0 - usign)
        ul = self.u[0:self.m] * usign + self.u[1:self.m + 1] * (1.0 - usign)

        f = np.zeros(2 * self.m + 4)
        if self.inlet_variable == "velocity":
            f[0] = (self.u[0] - self.get_inlet_boundary()) * self.conditioning
            f[1] = (self.p[0] - (2.0 * self.p[1] - self.p[2])) * self.conditioning
        elif self.inlet_variable == "pressure":
            f[0] = (self.u[0] - (2.0 * self.u[1] - self.u[2])) * self.conditioning
            f[1] = (self.p[0] - self.get_inlet_boundary()) * self.conditioning
        elif self.inlet_variable == "total_pressure":
            f[0] = (self.u[0] - (2.0 * (self.get_inlet_boundary() - self.p[0])) ** 0.5) * self.conditioning
            f[1] = (self.p[0] - (2.0 * self.p[1] - self.p[2])) * self.conditioning
        f[2:2 * self.m + 2:2] = (self.dz / self.dt * (self.a[1:self.m + 1] - self.an[1:self.m + 1]) * self.unsteady
                                 + (self.u[1:self.m + 1] + self.u[2:self.m + 2])
                                 * (self.a[1:self.m + 1] + self.a[2:self.m + 2]) / 4.0
                                 - (self.u[1:self.m + 1] + self.u[0:self.m])
                                 * (self.a[1:self.m + 1] + self.a[0:self.m]) / 4.0
                                 - self.alpha * (self.p[2:self.m + 2] - 2.0 * self.p[1:self.m + 1] + self.p[0:self.m]))
        f[3:2 * self.m + 3:2] = (self.dz / self.dt * (self.u[1:self.m + 1] * self.a[1:self.m + 1]
                                 - self.un[1:self.m + 1] * self.an[1:self.m + 1]) * self.unsteady
                                 + ur * (self.u[1:self.m + 1] + self.u[2:self.m + 2])
                                 * (self.a[1:self.m + 1] + self.a[2:self.m + 2]) / 4.0
                                 - ul * (self.u[1:self.m + 1] + self.u[0:self.m])
                                 * (self.a[1:self.m + 1] + self.a[0:self.m]) / 4.0
                                 + ((self.p[2:self.m + 2] - self.p[1:self.m + 1])
                                 * (self.a[1:self.m + 1] + self.a[2:self.m + 2])
                                 + (self.p[1:self.m + 1] - self.p[0:self.m])
                                 * (self.a[1:self.m + 1] + self.a[0:self.m])) / 4.0)
        f[2 * self.m + 2] = (self.u[self.m + 1] - (2.0 * self.u[self.m] - self.u[self.m - 1])) * self.conditioning
        if self.outlet_type == 1:
            f[2 * self.m + 3] = (self.p[self.m + 1] - (2.0 * (self.cmk2 - (np.sqrt(self.cmk2
                                                                                   - self.pn[self.m + 1] / 2.0)
                                                              - (self.u[self.m + 1] - self.un[self.m + 1]) / 4.0) ** 2))
                                 ) * self.conditioning
        else:
            f[2 * self.m + 3] = (self.p[self.m + 1] - self.outlet_amplitude) * self.conditioning
        return f

    def get_jacobian(self):
        usign = self.u[1:self.m + 1] > 0
        j = np.zeros((self.al + self.au + 1, 2 * self.m + 4))
        if self.inlet_variable == "velocity":
            j[self.au + 0 - 0, 0] = 1.0 * self.conditioning  # [0,0]
            j[self.au + 1 - 1, 1] = 1.0 * self.conditioning  # [1,1]
            j[self.au + 1 - 3, 3] = -2.0 * self.conditioning  # [1,3]
            j[self.au + 1 - 5, 5] = 1.0 * self.conditioning  # [1,5]
        elif self.inlet_variable == "pressure":
            j[self.au + 0 - 0, 0] = 1.0 * self.conditioning  # [0,0]
            j[self.au + 0 - 2, 2] = -2.0 * self.conditioning  # [0,2]
            j[self.au + 0 - 4, 4] = 1.0 * self.conditioning  # [0,4]
            j[self.au + 1 - 1, 1] = 1.0 * self.conditioning  # [1,1]
        elif self.inlet_variable == "total_pressure":
            j[self.au + 0 - 0, 0] = 1.0 * self.conditioning  # [0,0]
            j[self.au + 0 - 1, 1] = (2.0 * (self.get_inlet_boundary() - self.p[0])) ** -0.5 * self.conditioning  # [1,1]
            j[self.au + 1 - 1, 1] = 1.0 * self.conditioning  # [1,1]
            j[self.au + 1 - 3, 3] = -2.0 * self.conditioning  # [1,3]
            j[self.au + 1 - 5, 5] = 1.0 * self.conditioning  # [1,5]

        j[self.au + 2, 0:2 * self.m + 0:2] = -(self.a[1:self.m + 1] + self.a[0:self.m]) / 4.0  # [2*i, 2*(i-1)]
        j[self.au + 3, 0:2 * self.m + 0:2] = (-((self.u[1:self.m + 1] + 2.0 * self.u[0:self.m]) * usign
                                                + self.u[1:self.m + 1] * (1.0 - usign))
                                              * (self.a[1:self.m + 1] + self.a[0:self.m]) / 4.0)  # [2*i+1, 2*(i-1)]
        j[self.au + 1, 1:2 * self.m + 1:2] = -self.alpha  # [2*i, 2*(i-1)+1]
        j[self.au + 2, 1:2 * self.m + 1:2] = -(self.a[1:self.m + 1] + self.a[0:self.m]) / 4.0  # [2*i+1, 2*(i-1)+1]

        j[self.au + 0, 2:2 * self.m + 2:2] = ((self.a[1:self.m + 1] + self.a[2:self.m + 2]) / 4.0
                                              - (self.a[1:self.m + 1] + self.a[0:self.m]) / 4.0)  # [2*i, 2*i]
        j[self.au + 1, 2:2 * self.m + 2:2] = (self.dz / self.dt * self.a[1:self.m + 1] * self.unsteady
                                              + ((2.0 * self.u[1:self.m + 1] + self.u[2:self.m + 2]) * usign
                                                 + self.u[2:self.m + 2] * (1.0 - usign))
                                              * (self.a[1:self.m + 1] + self.a[2:self.m + 2]) / 4.0
                                              - (self.u[0:self.m] * usign
                                                 + (2.0 * self.u[1:self.m + 1] + self.u[0:self.m]) * (1.0 - usign))
                                              * (self.a[1:self.m + 1] + self.a[0:self.m]) / 4.0)  # [2*i+1, 2*i]
        j[self.au - 1, 3:2 * self.m + 3:2] = 2.0 * self.alpha  # [2*i, 2*i+1]
        j[self.au + 0, 3:2 * self.m + 3:2] = (-(self.a[1:self.m + 1] + self.a[2:self.m + 2])
                                              + (self.a[1:self.m + 1] + self.a[0:self.m])) / 4.0  # [2*i+1, 2*i+1]

        j[self.au - 2, 4:2 * self.m + 4:2] = (self.a[1:self.m + 1] + self.a[2:self.m + 2]) / 4.0  # [2*i, 2*(i+1)]
        j[self.au - 1, 4:2 * self.m + 4:2] = ((self.u[1:self.m + 1] * usign + (self.u[1:self.m + 1]
                                                                               + 2.0 * self.u[2:self.m + 2])
                                               * (1.0 - usign))
                                              * (self.a[1:self.m + 1] + self.a[2:self.m + 2]) / 4.0)  # [2*i+1, 2*(i+1)]
        j[self.au - 3, 5:2 * self.m + 5:2] = -self.alpha  # [2*i, 2*(i+1)+1]
        j[self.au - 2, 5:2 * self.m + 5:2] = (self.a[1:self.m + 1]
                                              + self.a[2:self.m + 2]) / 4.0  # [2*i+1, 2*(i+1)+1]

        j[self.au + (2 * self.m + 2) - (2 * self.m + 2), 2 * self.m + 2] = 1.0 * self.conditioning  # [2*m+2, 2*m+2]
        j[self.au + (2 * self.m + 2) - (2 * self.m), 2 * self.m] = -2.0 * self.conditioning  # [2*m+2, 2*m]
        j[self.au + (2 * self.m + 2) - (2 * self.m - 2), 2 * self.m - 2] = 1.0 * self.conditioning  # [2*m+2, 2*m-2]
        if self.outlet_type == 1:
            j[self.au + (2 * self.m + 3) - (2 * self.m + 2), 2 * self.m + 2] = (-(np.sqrt(self.cmk2
                                                                                          - self.pn[self.m + 1] / 2.0)
                                                                                  - (self.u[self.m + 1]
                                                                                     - self.un[self.m + 1])
                                                                                  / 4.0)) * self.conditioning  # [2*m+3, 2*m+2]
        j[self.au + (2 * self.m + 3) - (2 * self.m + 3), 2 * self.m + 3] = 1.0 * self.conditioning  # [2*m+3, 2*m+3]
        return j
