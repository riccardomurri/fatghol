#! /usr/bin/env python
#
"""Generic classes for homological algebra.
"""
__docformat__ = 'reStructuredText'


## logging subsystem

import logging


## stdlib imports

from collections import defaultdict


## application-local imports

from simplematrix import SimpleMatrix


## main

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

        First argument `base` is a sequence of base vectors; no
        requirement is placed on the type of base vectors.  The `base`
        object should support:
          - the `len` operator;
          - the `index` operator (with the same semantics of the `list` one)
        """
        self.base = base
        self.dimension = len(base)

    def __iter__(self):
        """Iterate over basis vectors."""
        return iter(self.base)
        
    def __repr__(self):
        return "VectorSpace(%s)" % self.base
    def __str__(self):
        return "<Vector space with base %s>" % self.base
    
    def coordinates(self, combo):
        """Return the (sparse) coordinate vector of `combo`.

        Argument `combo` represents a linear combination as a list
        of pairs `(vector, coefficient)`, where `vector` is an item in
        the `base` (specified when constructing this object).

        Return value is a sequence of pairs `(i, c)`, meaning
        `combo` has component `c` in the `i`-th basis vector.
        """
        coordinates = defaultdict(lambda: 0) 
        for (vector, coefficient) in iter(combo):
            coordinates[self.base.index(vector)] += coefficient
        return coordinates

    
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
    
    def __init__(self, length, modules=None, differentials=None):
        """Create a chain complex of specified length."""
        assert length > 0, \
                   "ChainComplex.__init__:"\
                   " argument `length` must be a positive integer," \
                   " but got `%s`." % length
        #: Total length of the complex.
        self.length = length
        #: Boundary operators; `differentials[i]` sends elements in
        #  `C[i]` to elements in `C[i+1]`.
        self.differential = [None]
        if differentials:
            assert len(differentials) == length-1, \
                   "ChainComplex.__init__:" \
                   " supplied `differentials` argument does not match" \
                   " supplied `length` argument."
            self.differential.extend(differentials)
        else:
            self.differential.extend([None] * length)
        #: The vector spaces supporting the differential complex.
        if modules:
            assert len(modules) == length, \
                   "ChainComplex.__init__:" \
                   " supplied `modules` argument does not match" \
                   " supplied `length` argument."
            self.module = modules
        else:
            self.module = [None] * length

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
        ## pass 1: compute boundary operators in matrix form
        #
        logging.info("Stage II: Computing matrix form of boundary operator ...")
        
        #: Matrix form of boundary operators; the `i`-th differential
        #: `D[i]` is `dim C[i-1]` rows (range) by `dim C[i]` columns
        #: (domain), stored in column-major format: that is, if `A =
        #: D[i]` then `A` has entries `A[j][k]` with `j` varying from 0
        #: to `self.module[i].dimension` (domain) and `k` varying in the
        #: range `0..self.module[i-1].dimension` (codomain, row).
        #
        D = [ None ]
        for i in xrange(1, self.length):
            # XXX: LinBox segfaults if asked to compute the rank of a 0xL matrix
            if self.module[i].dimension > 0 and self.module[i-1].dimension > 0:
                d = SimpleMatrix(self.module[i-1].dimension,
                                 self.module[i].dimension)
                for j in xrange(self.module[i].dimension):
                    # a = self.module[i].base[j]
                    for (k, c) in self.module[i-1].coordinates(
                                       self.differential[i](
                                            self.module[i].base[j])).iteritems():
                        d.addToEntry(k, j, c)
            else:
                d = None
            D.append(d)
            logging.info("  Computed %dx%d matrix D[%d]",
                         len(self.module[i-1].base),
                         len(self.module[i].base),
                         i)
            
        # XXX: check that the differentials form a complex
        #if __debug__:
        #    for i in xrange(1, self.length - 1):
        #        assert is_null_matrix(matrix_product(DD[i-1], DD[i]))

        
        ## pass 2: compute rank and nullity of boundary operators
        #
        logging.info("Stage III: Computing ranks of boundary operator matrices ...")
        
        #: ranks of `D[n]` matrices, for 0 <= n < len(self); the differential
        #: `D[0]` is the null map.
        ranks = [ (A.rank() if A else 0) for A in D ]
        for (i, r) in enumerate(ranks):
            logging.info("  rank D[%d]=%d", i, r)

        ## pass 3: compute homology group ranks from rank and nullity
        ##         of boundary operators.
        ##
        ## By the rank-nullity theorem, if A:V-->W is a linear map,
        ## then null(A) =  dim(V) - rk(A), hence:
        ##   dim(Z_i) = null(D_i) = dim(C_i) - rk(D_i)
        ##   dim(B_i) = rk(D_{i+1})
        ## Therefore:
        ##   h_i = dim(H_i) = dim(Z_i / B_i) = dim(Z_i) - dim(B_i)
        ##       = dim(C_i) - rk(D_i) - rk(D_{i+1})
        ##
        ranks.append(0) # augment complex with the null map.
        return [ (self.module[i].dimension - ranks[i] - ranks[i+1])
                 for i in xrange(self.length) ]


## main: run tests

if "__main__" == __name__:
    import doctest
    doctest.testmod(name="homology",
                    optionflags=doctest.NORMALIZE_WHITESPACE)
