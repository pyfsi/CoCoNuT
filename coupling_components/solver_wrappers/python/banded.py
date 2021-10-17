import numpy as np
from scipy.sparse import diags


def check_banded(j):
    rows = j.shape[0]
    main_diag = 0
    while j[main_diag, 0] == 0 or j[main_diag, -1] == 0:
        main_diag += 1
        if main_diag == rows:
            return False, None, None
    au = main_diag
    al = rows - 1 - main_diag
    for row in range(au):
        if (j[row, :main_diag - row] != 0).all():
            return False, None, None
    for row in range(main_diag + 1, al):
        if (j[row, row - main_diag:] != 0).all():
            return False, None, None
    return True, au, al


def to_dense(a):
    banded, au, al = check_banded(a)
    if not banded:
        raise ValueError('Input matrix should be banded')
    n = a.shape[1]  # shape of resulting matrix is n x n
    diagonals = []
    offsets = []
    for i in range(a.shape[0]):
        diagonals.append(a[i, max(0, au - i): n + min(0, au - i)].tolist())
        offsets.append(au - i)
    return np.array(diags(diagonals, offsets).todense())


def to_banded(a, au, al=None):
    # shape of resulting matrix is m x n
    if a.shape[0] != a.shape[1]:
        raise ValueError('Input matrix has to be square')
    if al is None:
        al = au
    m = au + al + 1
    n = a.shape[1]
    b = np.zeros((m, n))
    for i in range(n):
        for j in range(max(0, i - al), min(n, i + au + 1)):
            b[au + i - j, j] = a[i, j]
    return b


def remove_boundaries(j, num):
    # removes num boundary rows and columns from banded matrix j
    if num == 0:
        return j
    elif num < 0:
        return ValueError('Number of row and columns to be removed has to be positive')
    banded, au, al = check_banded(j)
    if not banded:
        raise ValueError('Matrix is not in banded form')
    main_diag = au
    j_new = np.zeros((j.shape[0], j.shape[1] - 2 * num))
    for row in range(au + 1):
        j_new[row, main_diag - row:] = j[row, main_diag - row + num: -num]
    for row in range(main_diag + 1, au + al + 1):
        j_new[row, :main_diag - row] = j[row, num: main_diag - row - num]
    return j_new


def multiply_banded(a, b, output_dense=False):
    banded_a, au, al = check_banded(a)
    banded_b, bu, bl = check_banded(b)
    if not (banded_a and banded_b):
        raise ValueError('Both matrices must be banded')
    if not a.shape == b.shape:
        raise ValueError('Banded matrices must have the same shape')
    cu = au + bu
    cl = al + bl
    n = a.shape[1]  # shape of resulting matrix is n x n
    if output_dense:
        c = np.zeros((n, n))
    else:
        c = np.zeros((cu + cl + 1, n))
    for i in range(n):
        for j in range(max(0, i - cl), min(n, i + cu + 1)):
            for k in range(n):
                if -al <= k - i <= au and -bu <= k - j <= bl:
                    if output_dense:
                        c[i, j] += a[au + i - k, k] * b[bu + k - j, j]
                    else:
                        c[cu + i - j, j] += a[au + i - k, k] * b[bu + k - j, j]
    return c


def transpose_banded(a):
    banded, au, al = check_banded(a)
    if not banded:
        raise ValueError('Matrix is not in banded form')
    m, n = a.shape
    at = np.zeros_like(a)
    for i in range(m):
        at[m - 1 - i, max(0, i - au): n + min(0, i - au)] = a[i, max(0, au - i): n + min(0, au - i)]
    return at
