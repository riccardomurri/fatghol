#! /usr/bin/env python
#
"""Generic classes for homological algebra.
"""
__docformat__ = 'reStructuredText'


import cython

## stdlib imports

from collections import defaultdict
import logging
import os.path
import numbers

## application-local imports

from loadsave import load, save
from runtime import runtime
from simplematrix import SimpleMatrix, is_null_product
import timing


## main

NullMatrix = SimpleMatrix(0,0)


@cython.cclass
class VectorSpace(object):
    """Represent the vector space generated by the given `base` vectors.

    After construction, you can retrieve the base vectors set and the
    dimension from instance attributes `base` and `dimension`.
    
    The `base` elements are assumed to be *linearly independent*, so
    the `dimension` of the generated vector space equals the number of
    elements in the base set.
    """
    def __init__(self, base):
        """Constructor, taking list of base vectors.

        First argument `base` is a sequence of base vectors.  No
        requirement is placed on the Python type of base vectors.  The
        `base` object should support:
          - the `len` operator;
          - the `index` operator (with the same semantics of the `list` one)
        """
        self.base = base
        self.dimension = len(base)

    
    def __iter__(self):
        """Iterate over basis vectors."""
        return iter(self.base)

    
    def __repr__(self):
        return ("VectorSpace(%s)" % self.base)

    def __str__(self):
        return ("<Vector space with base %s>" % self.base)
    
    
    def __len__(self):
        return len(self.base)
    
    
    @cython.locals(combo=list,
                   coefficient=cython.long, vector=object)
    #@cython.ccall(dict)
    def coordinates(self, combo):
        """Return the (sparse) coordinate vector of `combo`.

        Argument `combo` represents a linear combination as a list
        of pairs `(vector, coefficient)`, where `vector` is an item in
        the `base` (specified when constructing this object).

        Return value is a `dict` instance, mapping each `i` to the
        component of `combo` w.r.t. to the `i`-th basis vector.
        """
        coordinates = defaultdict(int) 
        for (vector, coefficient) in iter(combo):
            coordinates[self.base.index(vector)] += coefficient
        return coordinates



@cython.cclass
class DifferentialComplex(list):
    """A finite-length complex of differential operators.

    A `DifferentialComplex` is an ordered sequence of differential
    operators `D[i]`; each `D[i]` maps `C[i]` into `C[i+1]`.  The
    differential operators *must* be instances of the `SimpleMatrix`
    class; matrices are assumed to operate on column vectors, so that
    the number of rows equals the dimension of the domain vector
    space.
    
    Indices of the operators `D[i]` run from 0 to `len(D)-1`
    (inclusive).  The Python `len` operator returns the total length
    of the complex::
      
      | >>> len(D)
      | 2

    At present, the only supported operation on differential complexes
    is computing the rank of homology groups::

      | >>> D.compute_homology_ranks()
      | [1, 0]

    An assertion is thrown if the matrix product of
    `D[i]` and `D[i+1]` is not null.
    """
    
    def __init__(self, len_or_bds=[]):
        """Create a differential complex of specified length."""
        if isinstance(len_or_bds, numbers.Integral):
            list.__init__(self, [None]*len_or_bds)
        else:
            if __debug__:
                for elt in len_or_bds:
                    assert len(elt) == 3
                    A, dom, codom = elt
                    assert isinstance(A, SimpleMatrix)
                    assert isinstance(dom, numbers.Integral)
                    assert isinstance(codom, numbers.Integral)
            list.__init__(self, len_or_bds)

    def __repr__(self):
        return "DifferentialComplex(%s)" % list.__str__(self)
    
    def __str__(self):
        return repr(self)
    

    @cython.locals(#bd=SimpleMatrix,
        ddim=cython.int, cdim=cython.int)
    @cython.ccall
    def append(self, bd, ddim, cdim):
        list.append(self, (bd, ddim, cdim))
    

    @cython.locals(ranks=list, i=cython.int,
                   A=SimpleMatrix, ddim=cython.int, cdim=cython.int,
                   r=cython.int, rs=list, domain_dim=list)
    @cython.ccall
    def compute_homology_ranks(self):
        """Compute and return (list of) homology group ranks.

        Returns a list of integers: item at index `n` is the rank of
        the `n`-th homology group of this differential complex.  Since
        the differential complex has finite length, homology group
        indices can only run from 0 to the length of the complex (all
        other groups being, trivially, null).
        """
        # check that the differentials form a complex
        # if __debug__:
        #     for i in xrange(1, len(self)-1):
        #         assert is_null_product(self[i-1][0], self[i][0]), \
        #                "DifferentialComplex.compute_homology_ranks:" \
        #                " Product of boundary operator matrices D[%d] and D[%d]" \
        #                " is not null!" \
        #                % (i-1, i)
        
        #: ranks of `D[n]` matrices, for 0 <= n < len(self); the differential
        #: `D[0]` is the null map.
        ranks = list()
        # only compute those ranks that were not saved
        for (i, (A, ddim, cdim)) in enumerate(self):
            try:
                checkpoint = (os.path.join(runtime.options.checkpoint_dir,
                                           "M%d,%d-rkD%d.txt" % (runtime.g, runtime.n, i)))
            except AttributeError:
                # running tests, so no `runtime.options`
                checkpoint = None
            # XXX: LinBox segfaults if asked to compute the rank of a 0xL matrix
            if A.num_rows > 0 and A.num_columns > 0:
                rs = None
                if checkpoint is not None and runtime.options.restart:
                    rs = load(checkpoint)
                    if rs:
                        r = rs[0]
                        logging.info("  rank D[%d]=%d (loaded from file '%s')",
                                     i+1, r, checkpoint)
                if rs is None: # `rs` was not loaded from checkpoint file
                    timing.start("rank D[%d]" % i)
                    r = A.rank()
                    timing.stop("rank D[%d]" % i)
                    # checkpoint the computation so far
                    if checkpoint is not None:
                        save([r], checkpoint)
                    logging.info("  rank D[%d]=%d (computed in %.3fs)",
                                 i+1, r, timing.get("rank D[%d]" % i))
            else: # A is a 0xL matrix
                r = 0
                logging.info("  rank D[%d]=%d (immediate)", i+1, r)
            ranks.append(r)

        ## compute homology group ranks from rank and nullity
        ## of boundary operators.
        ##
        ## By the rank-nullity theorem, if A:V-->W is a linear map,
        ## then null(A) =  dim(V) - rk(A), hence:
        ##   dim(Z_i) = null(D_i) = dim(C_i) - rk(D_i)
        ##   dim(B_i) = rk(D_{i+1})
        ## Therefore:
        ##   h_i = dim(H_i) = dim(Z_i / B_i) = dim(Z_i) - dim(B_i)
        ##       = dim(C_i) - rk(D_i) - rk(D_{i+1})
        ## where D_i:C_i-->C_{i+1}
        ##
        domain_dim = [ ddim for (A, ddim, cdim) in self ]
        domain_dim.append(self[-1][2]) # add dimension of last vector space
        ranks.append(0) # augment complex with the null map.
        # note: `domain_dim` indices are offset by 1 w.r.t. to `ranks` indices
        return [ (domain_dim[i+1] - ranks[i] - ranks[i+1])
                 for i in xrange(len(self)) ]



@cython.cclass
class ChainComplex(object):
    """Represents a (finite-length) chain (homology) complex.

    A `ChainComplex` `C` of length `l` comprises vector spaces `C[i]`
    and differentials `C.differential[i]`; each `C[i]` represents the
    part of the graded vector space `C` having degree `i`.  The map
    `C.differential[i]` sends (linear combinations of) elements in
    vector space `C[i]` to linear combinations of vectors in `C[i-1]`;
    the `coordinates` method of `C[i-1]` will be used to obtain a
    numerical representation of the differentiated element.
    
    A `ChainComplex` instance must be initialized by assigning
    `VectorSpace` instances into each `C[i]` (for 0 <= `i` <
    `len(C)`), and appropriate maps into `C.differential[i]` (for 1 <=
    `i` < `len(C)`)::

      >>> # chain homology of a segment
      >>> C = ChainComplex(2)
      >>> C[1] = VectorSpace(['a'])
      >>> C[0] = VectorSpace(['b0', 'b1'])
      >>> C.differential[1] = lambda _: [('b0',1), ('b1', -1)]

    Indices of the slices `C[i]` run from 0 to `len(C)-1` (inclusive).
    The Python `len` operator returns the total length of the
    complex::
      
      >>> len(C)
      2

    At present, the only supported operation on chain complexes is
    computing the rank of homology groups::

      >>> C.compute_homology_ranks()
      [1, 0]
    """
    
    def __init__(self, length):
        """Create a chain complex of specified length."""
        assert length > 0, (
            "ChainComplex.__init__:"
            " argument `length` must be a positive integer," 
            " but got `%s` instead." % length)
        #: Total length of the complex.
        self.length = length
        #: The vectotr spaces supporting the differential complex
        self.module = [ VectorSpace([]) for x in xrange(length) ]
        #: Boundary operators; `differentials[i]` sends elements in
        #  `C[i]` to elements in `C[i+1]`.
        self.differential = [ ChainComplex.null_differential for x in xrange(length) ]

    @staticmethod
    def null_differential(vector):
      return [ ] # null linear combination


    def __repr__(self):
        return "ChainComplex(%d, modules=%s, differentials=%s)" \
               % (self.length, self.module, self.differential)

    def __str__(self):
        return repr(self)


    ## list-like interface: support C[i] and len(C) syntax
    def __len__(self):
        return self.length

    def __getitem__(self, i):
        """Return the `i`-th pair (module, boundary operator)."""
        return (self.module[i], self.differential[i])

    def __setitem__(self, i, val):
        """Set the `i`-th support module and, optionally, boundary operator.

        ::
          C[i] = (module, differential)  # set `i`-th module and boundary op.
          C[i] = module                  # only set module
        """
        if (isinstance(val, tuple)):
            assert len(val) == 2, \
                   "ChainComplex.__setitem__:" \
                   " Need a 2-tuple (module, differential), but got `%s`" % val
            (self.module[i], self.differential[i]) = val
        else:
            self.module[i] = val


    @cython.locals(D=DifferentialComplex, d=SimpleMatrix,
                   i=cython.int, j=cython.int, k=cython.int, c=cython.int)
    #@cython.ccall(DifferentialComplex)
    def compute_boundary_operators(self):
        """Compute and return matrix form of boundary operators.

        Return list of sparse `SimpleMatrix` instances.

        Matrix form of boundary operators operates on column vectors:
        the `i`-th differential `D[i]` is `dim C[i-1]` rows (range) by
        `dim C[i]` columns (domain).
        """
        D = DifferentialComplex()
        D.append(NullMatrix, 0, self.module[0].dimension)
        for i in xrange(1, self.length):
            d = SimpleMatrix(self.module[i-1].dimension,
                             self.module[i].dimension)
            for j in xrange(self.module[i].dimension):
                for (k, c) in self.module[i-1].coordinates(
                                   self.differential[i](
                                        self.module[i].base[j])).iteritems():
                    d.addToEntry(k, j, c)
            D.append(d, self.module[i-1].dimension, self.module[i].dimension)
            logging.info("  Computed %dx%d matrix D[%d]",
                         len(self.module[i-1].base),
                         len(self.module[i].base),
                         i)
        return D


    @cython.ccall
    def compute_homology_ranks(self):
        """Compute and return (list of) homology group ranks.

        Returns a list of integers: item at index `n` is the rank of
        the `n`-th homology group of this chain complex.  Since the
        chain complex has finite length, homology group indices can
        only run from 0 to the length of the complex (all other groups
        being, trivially, null).

        Examples::
        
          >>> # chain homology of a point
          >>> C_point = ChainComplex(1)
          >>> C_point[0] = VectorSpace(['a'])
          >>> C_point.compute_homology_ranks()
          [1]
          
          >>> # chain homology of a segment
          >>> C_segment = ChainComplex(2)
          >>> C_segment[1] = VectorSpace(['a'])
          >>> C_segment[0] = VectorSpace(['b0', 'b1'])
          >>> C_segment.differential[1] = lambda _: [('b0',1), ('b1', -1)]
          >>> C_segment.compute_homology_ranks()
          [1, 0]
          
          >>> # chain homology of a circle
          >>> C_circle = ChainComplex(2)
          >>> C_circle[1] = VectorSpace(['a'])
          >>> C_circle[0] = VectorSpace(['b'])
          >>> C_circle.differential[1] = lambda _: []
          >>> C_circle.compute_homology_ranks()
          [1, 1]
          
        """
        return self.compute_boundary_operators().compute_homology_ranks()



## main: run tests

if "__main__" == __name__:
    import doctest
    doctest.testmod(name="homology",
                    optionflags=doctest.NORMALIZE_WHITESPACE)
