from coconut.coupling_components.component import Component
from coconut import tools

import numpy as np
from scipy.linalg import solve_triangular


def create(parameters):
    return ModelMVMF(parameters)


class ModelMVMF(Component):
    def __init__(self, parameters):
        super().__init__()

        self.settings = parameters["settings"]
        self.min_significant = self.settings["min_significant"]
        self.q = self.settings["q"]

        self.size_in = None
        self.size_out = None
        self.out = None  # interface of output
        self.added = False
        self.rref = None
        self.xtref = None
        self.v = None
        self.w = None
        self.wprev = []
        self.rrprev = []
        self.qqprev = []

    def initialize(self):
        super().initialize()

        self.v = np.empty((self.size_in, 0))
        self.w = np.empty((self.size_out, 0))

    def filter(self):
        if self.v.shape[1] == 0:
            raise RuntimeError("No information to filter")
        # remove columns resulting in small diagonal elements in R
        singular = True
        while singular and self.v.shape[1]:
            rr = np.linalg.qr(self.v, mode='r')
            diag = np.diagonal(rr)
            m = min(abs(diag))
            if m < self.min_significant:
                i = np.argmin(abs(diag))
                tools.print_info("Removing column " + str(i) + ": " + str(m) + " < minsignificant", layout='warning')
                self.v = np.delete(self.v, i, 1)
                self.w = np.delete(self.w, i, 1)
            else:
                singular = False
        # remove columns if number of columns exceeds number of rows
        if self.v.shape[0] < self.v.shape[1]:
            self.v = np.delete(self.v, -1, 1)
            self.w = np.delete(self.w, -1, 1)

    def predict(self, dr_in):
        dr = dr_in.get_interface_data().reshape(-1, 1)
        if self.v.shape[1] + len(self.wprev) == 0:
            raise RuntimeError("No information to predict")
        # approximation for the inverse of the Jacobian from a multiple vector model
        if self.v.shape[1]:
            qq, rr = np.linalg.qr(self.v, mode='reduced')
            b = qq.T @ dr
            c = solve_triangular(rr, b)
            dxt = self.w @ c
        else:
            dxt = np.zeros((self.size_in, 1))
            qq = np.zeros((self.size_out, 1))
        dr = dr - qq @ (qq.T @ dr)
        i = 0
        while np.linalg.norm(dr) > self.min_significant and i < len(self.wprev):
            b = self.qqprev[i].T @ dr
            if self.wprev[i].shape[1]:
                c = solve_triangular(self.rrprev[i], b)
                dxt += self.wprev[i] @ c
                qq = self.qqprev[i]
                dr = dr - qq @ (qq.T @ dr)
            i += 1
        # # remove insignificant information
        # while i < len(self.wprev):
        #     self.wprev.pop(i)
        #     self.rrprev.pop(i)
        #     self.qqprev.pop(i)
        #     i += 1
        dxt_out = self.out.copy()
        dxt_out.set_interface_data(dxt.flatten())
        return dxt_out

    def add(self, r_in, xt_in):
        r = r_in.get_interface_data().reshape(-1, 1)
        xt = xt_in.get_interface_data().reshape(-1, 1)
        if self.added:
            dr = r - self.rref
            dxt = xt - self.xtref
            # update V and W matrices
            self.v = np.hstack((dr, self.v))
            self.w = np.hstack((dxt, self.w))
            self.filter()
        else:
            self.added = True
        self.rref = r
        self.xtref = xt

    def is_ready(self):
        return self.v.shape[1] + len(self.wprev)

    def initialize_solution_step(self):
        super().initialize_solution_step()

        self.rref = None
        self.xtref = None
        self.v = np.empty((self.size_in, 0))
        self.w = np.empty((self.size_out, 0))
        self.added = False

    def finalize_solution_step(self):
        super().finalize_solution_step()

        self.wprev = [self.w] + self.wprev
        qq, rr = np.linalg.qr(self.v, mode='reduced')
        self.rrprev = [rr] + self.rrprev
        self.qqprev = [qq] + self.qqprev
        # limit number of timesteps reused to q
        if len(self.wprev) > self.q:
            self.wprev.pop()
            self.rrprev.pop()
            self.qqprev.pop()

    def filter_q(self, r_in):
        r = r_in.get_interface_data().reshape(-1, 1)
        r_out = r_in.copy()
        qq, _ = np.linalg.qr(self.v, mode='reduced')
        r = r - qq @ (qq.T @ r)
        for qq in self.qqprev:
            r = r - qq @ (qq.T @ r)
        r_out.set_interface_data(r.flatten())
        return r_out
