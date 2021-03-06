#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright 1999-2018 Alibaba Group Holding Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import numpy as np
from numpy.linalg import LinAlgError

from .... import operands
from ...core import ExecutableTuple
from ..datasource import tensor as astensor
from .core import TSQR


class TensorQR(operands.QR, TSQR):
    def __init__(self, method=None, dtype=None, **kw):
        super(TensorQR, self).__init__(_method=method, _dtype=dtype, **kw)

    def _set_inputs(self, inputs):
        super(TensorQR, self)._set_inputs(inputs)
        self._input = self._inputs[0]

    def __call__(self, a):
        a = astensor(a)

        if a.ndim != 2:
            raise LinAlgError('{0}-dimensional tensor given. '
                              'Tensor must be two-dimensional'.format(a.ndim))

        tiny_q, tiny_r = np.linalg.qr(np.ones((1, 1), dtype=a.dtype))

        x, y = a.shape
        q_shape = a.shape if x > y else (x, x)
        r_shape = a.shape if x < y else (y, y)
        q, r = self.new_tensors([a], (q_shape, r_shape),
                                kws=[{'side': 'q', 'dtype': tiny_q.dtype},
                                     {'side': 'r', 'dtype': tiny_r.dtype}])
        return ExecutableTuple([q, r])

    @classmethod
    def tile(cls, op):
        q, r = op.outputs
        q_dtype, r_dtype = cls._get_obj_attr(q, 'dtype'), cls._get_obj_attr(r, 'dtype')
        q_shape, r_shape = cls._get_obj_attr(q, 'shape'), cls._get_obj_attr(r, 'shape')
        in_tensor = op.input
        if in_tensor.chunk_shape == (1, 1):
            in_chunk = in_tensor.chunks[0]
            chunk_op = op.copy().reset_key()
            qr_chunks = chunk_op.new_chunks([in_chunk], (q_shape, r_shape), index=in_chunk.index,
                                            kws=[{'side': 'q'}, {'side': 'r'}])
            q_chunk, r_chunk = qr_chunks

            new_op = op.copy()
            kws = [
                {'chunks': [q_chunk], 'nsplits': ((1,), (1,)), 'dtype': q_dtype},
                {'chunks': [r_chunk], 'nsplits': ((1,), (1,)), 'dtype': r_dtype}
            ]
            return new_op.new_tensors(op.inputs, [q_shape, r_shape], kws=kws)
        elif op.method == 'tsqr':
            return super(TensorQR, cls).tile(op)
        # TODO(hks): support sfqr(short-and-fat qr)
        else:
            raise NotImplementedError('Only tsqr method supported for now')


def qr(a, method='tsqr'):
    """
    Compute the qr factorization of a matrix.

    Factor the matrix `a` as *qr*, where `q` is orthonormal and `r` is
    upper-triangular.

    Parameters
    ----------
    a : array_like, shape (M, N)
        Matrix to be factored.
    method: {'tsqr'}, optional
        method to calculate qr factorization, tsqr as default

        TSQR is presented in:

            A. Benson, D. Gleich, and J. Demmel.
            Direct QR factorizations for tall-and-skinny matrices in
            MapReduce architectures.
            IEEE International Conference on Big Data, 2013.
            http://arxiv.org/abs/1301.1071

    Returns
    -------
    q : Tensor of float or complex, optional
        A matrix with orthonormal columns. When mode = 'complete' the
        result is an orthogonal/unitary matrix depending on whether or not
        a is real/complex. The determinant may be either +/- 1 in that
        case.
    r : Tensor of float or complex, optional
        The upper-triangular matrix.

    Raises
    ------
    LinAlgError
        If factoring fails.

    Notes
    -----
    For more information on the qr factorization, see for example:
    http://en.wikipedia.org/wiki/QR_factorization

    Examples
    --------
    >>> import mars.tensor as mt

    >>> a = mt.random.randn(9, 6)
    >>> q, r = mt.linalg.qr(a)
    >>> mt.allclose(a, mt.dot(q, r)).execute()  # a does equal qr
    True

    """
    op = TensorQR(method=method)
    return op(a)
