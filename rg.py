#! /usr/bin/env python
#
"""Classes and functions to deal with ribbon graphs.
"""
__docformat__ = 'reStructuredText'


import debug, pydb, sys
sys.excepthook = pydb.exception_hook


from combinatorics import (
    InplacePermutationIterator,
    SetProductIterator,
    Permutation,
    )
from cyclicseq import CyclicList,CyclicTuple
from utils import (
    BufferingIterator,
    concat,
    itranslate
    )

from copy import copy
from itertools import chain,count,izip


class VertexCache(object):
    """A caching factory of `Vertex` objects.
    """
    __slots__ = [
        'cache',
        ]
    def __init__(self):
        self.cache = {}
    def __call__(self, edge_seq):
        key = tuple(edge_seq)
        if key not in self.cache:
            self.cache[key] = Vertex(key)
        return self.cache[key]


class Vertex(CyclicList):
    """A (representative of) a vertex of a ribbon graph.

    A vertex is represented by the cyclically ordered list of its
    (decorated) edges.  The edge colorings may be accessed through a
    (read-only) sequence interface.
    """
    # *Note:* `Vertex` cannot be a `tuple` subclass because:
    #   1) `tuple` has no `index()` method and re-implementing one in
    #      pure Python would be less efficient;
    #   2) we could not implement `rotate()` and friends: tuples are
    #      immutable.

    def __cmp__(self, other):
        """Return negative if x<y, zero if x==y, positive if x>y.
        Unlike standard Python sequence comparison, vertices with
        lower valence come first, and two vertices are only compared
        lexicographically if they have the same valence::

          >>> cmp(Vertex([0,1,2]), Vertex([0,1,2,3,4]))
          -1
          >>> cmp(Vertex([0,1,2,3,4]), Vertex([0,1,2]))
          1
          
          >>> cmp(Vertex([0,1,2]), Vertex([0,1,2]))
          0
          
          >>> cmp(Vertex([0,1,2,3]), Vertex([0,0,1,1]))
          1
          >>> cmp(Vertex([0,0,1,1]), Vertex([0,1,2,3]))
          -1
          
        """
        result = cmp(len(self), len(other))
        if 0 == result:
            if super(Vertex, self).__eq__(other):
                return 0
            else:
                if super(Vertex, self).__lt__(other):
                    return -1
                else:
                    return +1
        return result

    def __str__(self):
        return repr(self)
    
    def is_canonical_representative(self):
        """Return `True` if this `Vertex` object is maximal among
        representatives of the same cyclic sequence.
        
        Examples::
        
          >>> Vertex([3,2,1]).is_canonical_representative()
          True
          >>> Vertex([2,1,3]).is_canonical_representative()
          False
          >>> Vertex([1,1]).is_canonical_representative()
          True
          >>> Vertex([1]).is_canonical_representative()
          True
        """
        L = len(self)
        for i in xrange(1,L):
            for j in xrange(0,L):
                # k := (i+j) mod L
                k = i+j
                if k >= L:
                    k -= L
                if self[k] < self[j]:
                    # continue with next i
                    break
                elif self[k] > self[j]:
                    return False
                # else, continue comparing
        return True

    def make_canonical(self):
        """Alter `Vertex` *in place* so that it is represented by a
        canonical sequence.  Return modified sequence for convenience.
        
        Examples::
          >>> Vertex([3,2,1]).make_canonical()
          Vertex([3, 2, 1])
          >>> Vertex([2,1,3]).make_canonical()
          Vertex([3, 2, 1])
        """
        L = len(self)
        r = 0
        for i in xrange(1,L):
            for j in xrange(0,L):
                # k := (i+j) mod L
                k = i+j
                if k >= L:
                    k -= L
                if self[k] < self[j]:
                    # continue with next i
                    break
                elif self[k] > self[j]:
                    r = i
                # else, continue comparing
        if r > 0:
            self.rotate(r)
        return self


class Graph(object):
    """A fully-decorated ribbon graph.

    Exports a (read-only) sequence interface, through which vertices
    can be accessed.
    """
    # the only reason to use `__slots__` here is to keep a record of
    # all instance attribute names.
    __slots__ = [
        '_boundary_components',
        '_contractions',
        '_contraction_coefficients',
        '_genus',
        '_num_boundary_components',
        '_parent',
        '_seqnr',
        '_siblings',
        '_valence_spectrum',
        '_vertex_factory',
        '_vertex_valences',
        'edge_seq',
        'endpoints',
        'numbering',
        'num_edges',
        'num_external_edges',
        'num_vertices',
        'vertices',
        ]

    def __init__(self, vertices, vertex_factory=Vertex, **kwargs):
        """Construct a `Graph` instance, taking list of vertices.

        Argument `vertices` must be a sequence of `Vertex` class
        instances::  

          >>> G1 = Graph([Vertex([2,0,1]), Vertex([2,1,0])])

        Note that the list of vertices is assigned, *not copied* into
        the instance variable.

        """
        assert debug.is_sequence_of_type(Vertex, vertices), \
               "Graph.__init__: parameter `vertices` must be" \
               " sequence of `Vertex` instances."

        #: list of vertices 
        self.vertices = vertices
##         pv = SortingPermutation(self.vertices)
##         pv[None] = None # needed for graphs with external edges
        
        #: list of vertex valences 
        self._vertex_valences = tuple(sorted(kwargs.get('_vertex_valences',
                                                        (len(v) for v in vertices))))

        #: edge sequence from which this is/could be built
        self.edge_seq = kwargs.get('edge_seq',
                                   tuple(chain(*[iter(v)
                                                 for v in vertices])))

        #: Number of edge colors
        self.num_edges = kwargs.get('num_edges',
                                    sum(self._vertex_valences) / 2)

        #: Number of external (loose-end) edges
        self.num_external_edges = kwargs.get('num_external_edges', 0)

        #: Number of vertices
        self.num_vertices = kwargs.get('num_vertices', len(self.vertices))
        
        #: Order on the boundary cycles, or `None`.
        self.numbering = kwargs.get('numbering', None)

        # the following values will be computed on-demand

        #: Cached boundary cycles of this graph; see
        #  `.boundary_components()` for an explanation of the
        #  format. This is initially `None` and is actually computed on
        #  first invocation of the `.boundary_components()` method.
        self._boundary_components = kwargs.get('_boundary_components', None)

        #: Graphs obtained by contraction of edges.  (The children
        #  obtained by contracting edge `l` is at list position `[l]`)
        self._contractions = kwargs.get('_contractions',
                                        [None] * self.num_edges)
        
        #: Orientation of graphs resulting from contraction of edges;
        #: starts as `+1` and might be changed in `MgnGraphsIterator`
        #: if a contraction : is replaced by another (canonical)
        #: representative.
        self._contraction_coefficients = kwargs.get('_contraction_coefficients',
                                                    [1] * self.num_edges)
        
        #: Cached genus; initially `None`, and actually computed on
        #  first invocation of the `.genus()` method.
        self._genus = kwargs.get('_genus', None)

        #: cached number of boundary cycles of this graph; this is
        #  initially `None` and is actually computed on first invocation
        #  of the `.num_boundary_components()` method.
        self._num_boundary_components = kwargs.get('_num_boundary_components',
                                                   None)

        #: For un-numbered graphs, the list of numbered variants
        #  produced by `MakeNumberedGraphs` is recorded here.
        self._siblings = kwargs.get('_siblings', None)
        
        #: Valence spectrum; initially `None`, and actually computed on
        #  first invocation of the `.valence_spectrum()` method.
        self._valence_spectrum = kwargs.get('_valence_spectrum', None)

        #: Factory method to make a `Vertex` instance from a linear
        #  list of incident edge colorings.
        self._vertex_factory = vertex_factory
        
        if 'endpoints' not in kwargs:
            #: Adjacency list of this graph.  For each edge, store a pair
            #  `(v1, v2)` where `v1` and `v2` are indices of endpoints.
            self.endpoints = [ [] for dummy in xrange(self.num_edges) ]
            for current_vertex_index in xrange(len(self.vertices)):
                for edge in self.vertices[current_vertex_index]:
                    assert edge in range(self.num_edges), \
                               "Graph.__init__: edge number %d not in range 0..%d" \
                               % (edge, self.num_edges)
                    self.endpoints[edge].append(current_vertex_index)
        else:
##             self.endpoints = [ tuple(pv.itranslate(ep))
##                                for ep in kwargs.get('endpoints') ]
            self.endpoints = kwargs.get('endpoints')
            
        assert self._ok()

    def _ok(self):
        """Perform coherency checks on `Graph` instance and return `True`
        if they all pass.
        """
        assert self.num_edges > 0, \
               "Graph `%s` has 0 edges." % (self)
        # check regular edges endpoints
        for (edge, ep) in enumerate(self.endpoints[:self.num_edges]):
            assert isinstance(ep[0], int) and isinstance(ep[1], int) \
                   and (0 <= ep[0]) and (ep[0] < self.num_vertices) \
                   and (0 <= ep[1]) and (ep[1] < self.num_vertices), \
                   "Graph `%s` has invalid regular endpoints array `%s`" \
                   " invalid endpoints pair %s for edge %d" \
                   % (self, self.endpoints, ep, edge)
            assert (edge in self.vertices[ep[0]]) \
                   and (edge in self.vertices[ep[1]]), \
                   "Invalid endpoints %s for edge %d of graph `%s`" \
                   % (ep, edge, self)
        # check external edges endpoints
        for (edge, ep) in enumerate(self.endpoints[self.num_edges:]):
            xedge = -self.num_external_edges + edge
            assert isinstance(ep[0], int) and (ep[1] is None) \
                   and (0 <= ep[0]) and (ep[0] < self.num_vertices), \
                   "Graph `%s` has invalid external endpoints array: `%s`" \
                   % (self, self.endpoints)
            assert (xedge in self.vertices[ep[0]]), \
                   "Invalid endpoints %s for external edge %d of graph `%s`" \
                   % (ep, xedge, self)
        # check that each edge occurs exactly two times in vertices
        cnt = [ 0 for x in xrange(self.num_edges + self.num_external_edges) ]
        for v in self.vertices:
            for edge in v:
                cnt[edge] += 1
        for edge, cnt in enumerate(cnt):
            if edge < self.num_edges:
                assert cnt == 2, \
                       "Regular edge %d appears in %d vertices" \
                       % (edge, cnt)
            else:
                assert cnt == 1, \
                       "External edge %d appears in %d vertices" \
                       % (edge, cnt)
        return True
        
    def __eq__(self, other):
        """Return `True` if Graphs `self` and `other` are isomorphic.

        Examples::

          >>> Graph([Vertex([1,0,0,1])]) == Graph([Vertex([1,1,0,0])])
          True

          >>> Graph([Vertex([2,0,0]), Vertex([2,1,1])]) \
                == Graph([Vertex([2,2,0]), Vertex([1,1,0])])
          True

          >>> Graph([Vertex([2,0,1]), Vertex([2,0,1])]) \
                == Graph([Vertex([2,1,0]), Vertex([2,0,1])])
          False

          >>> Graph([Vertex([2,0,1]), Vertex([2,0,1])]) \
                == Graph([Vertex([2,0,0]), Vertex([2,1,1])])
          False

          >>> Graph([Vertex([2,0,0]), Vertex([2,1,1])]) \
                == Graph([Vertex([1,1,0,0])])
          False

        Graph instances equipped with a numbering are compared as
        numbered graphs (that is, the isomorphism should transform the
        numbering on the source graph onto the numbering of the
        destination)::

          >>> Graph([Vertex([2,0,1]), Vertex([2,1,0])], \
                     numbering={CyclicTuple((0,1)): 0, \
                                CyclicTuple((0,2)): 1, \
                                CyclicTuple((2,1)): 2 } ) \
              == Graph([Vertex([2,0,1]), Vertex([2,1,0])], \
                        numbering={CyclicTuple((1,0)): 0, \
                                   CyclicTuple((0,2)): 2, \
                                   CyclicTuple((2,1)): 1})
          True

          >>> Graph([Vertex([1, 0, 0, 2, 2, 1])], \
                     numbering={CyclicTuple((2,)):    0, \
                                CyclicTuple((0,2,1)): 1, \
                                CyclicTuple((0,)):    3, \
                                CyclicTuple((1,)):    2 }) \
                == Graph([Vertex([2, 2, 1, 1, 0, 0])], \
                          numbering={CyclicTuple((2,)):    0, \
                                     CyclicTuple((0,)):    1, \
                                     CyclicTuple((2,1,0)): 3, \
                                     CyclicTuple((1,)):    2})
          False
        
          >>> Graph([Vertex([1, 0, 0, 2, 2, 1])], \
                     numbering={CyclicTuple((2,)):    0, \
                                CyclicTuple((0,2,1)): 1, \
                                CyclicTuple((0,)):    3, \
                                CyclicTuple((1,)):    2 }) \
                == Graph([Vertex([2, 2, 1, 1, 0, 0])], \
                          numbering={CyclicTuple((2,)):    3, \
                                     CyclicTuple((0,)):    0, \
                                     CyclicTuple((2,1,0)): 2, \
                                     CyclicTuple((1,)):    1 })
          False

          >>> Graph([Vertex([3, 2, 2, 0, 1]), Vertex([3, 1, 0])], \
                    numbering={CyclicTuple((2,)):      0,  \
                               CyclicTuple((0, 1)):    1,  \
                               CyclicTuple((3, 1)):    2,  \
                               CyclicTuple((0, 3, 2)): 3}) \
              == Graph([Vertex([2, 3, 1]), Vertex([2, 1, 3, 0, 0])], \
                       numbering={CyclicTuple((0,)):      0, \
                                  CyclicTuple((1, 3)):    2, \
                                  CyclicTuple((3, 0, 2)): 3, \
                                  CyclicTuple((2, 1)):    1})
          True
          
          """
        assert isinstance(other, Graph), \
               "Graph.__eq__:" \
               " called with non-Graph argument `other`: %s" % other
        # shortcuts
        if ((self.num_edges != other.num_edges)
            or (self.num_vertices != other.num_vertices)
            or (self._vertex_valences != other._vertex_valences)):
            return False
        if (self.vertices == other.vertices) \
           and (self.endpoints == other.endpoints) \
           and (self.numbering == other.numbering):
            return True

        # else, go the long way: try to find an explicit isomorphims
        # between graphs `self` and `other`
        try:
            # if there is any morphism, then return `True`
            self.isomorphisms_to(other).next()
            return True
        except StopIteration:
            # list of morphisms is empty, graphs are not equal.
            return False

    def __getitem__(self, index):
        return self.vertices[index]

    def __hash__(self):
        return hash(self.edge_seq)

    def __iter__(self):
        """Return iterator over vertices."""
        return iter(self.vertices)

    # both `__eq__` and `__ne__` are needed for testing equality of objects;
    # see `<http://www.voidspace.org.uk/python/articles/comparison.shtml>`
    def __ne__(self, other):
        """The opposite of `__eq__` (which see)."""
        return not self.__eq__(other)

    def __repr__(self):
        extra = dict((x,getattr(self, x))
                     for x in ['numbering', 'num_external_edges']
                     if ((getattr(self, x) is not None)
                         and (not isinstance(getattr(self, x), int)
                              or (getattr(self, x) > 0))))
        return "Graph(%s%s)" % (repr(self.vertices),
                                  "".join((", %s=%s" % (k,v) for k,v
                                             in extra.iteritems())))
    
    def __str__(self):
        return repr(self)

    def automorphisms(self):
        """Enumerate automorphisms of this `Graph` object.

        See `.isomorphisms_to()` for details of how a `Graph`
        isomorphism is represented.
        """
        return self.isomorphisms_to(self)

    
    def boundary_components(self):
        """Return the number of boundary components of this `Graph` object.

        Each boundary component is represented by the list of (colored)
        edges::

          >>> Graph([Vertex([2,1,0]),Vertex([2,0,1])]).boundary_components()
          set([CyclicTuple((0, 1)), CyclicTuple((1, 2)), CyclicTuple((2, 0))])

        If both sides of an edge belong to the same boundary
        component, that edge appears twice in the list::

          >>> Graph([Vertex([2,1,1]),Vertex([2,0,0])]).boundary_components()
          set([CyclicTuple((2, 0, 2, 1)), CyclicTuple((0,)), CyclicTuple((1,))])
          
          >>> Graph([Vertex([2,1,0]),Vertex([2,1,0])]).boundary_components()
          set([CyclicTuple((2, 1, 0, 2, 1, 0))])
          
        """
        assert self.num_external_edges == 0, \
               "Graph.boundary_components: "\
               " cannot compute boundary components for" \
               " a graph with nonzero external edges: %s" % self
        
        # if no cached result, compute it now...
        if self._boundary_components is None:
            # micro-optimizations
            L = self.num_edges
            ends = self.endpoints

            # pass1: build a "copy" of `graph`, replacing each edge
            # coloring with a triplet `(other, index, edge)` pointing to
            # the other endpoint of that same edge: the element at
            # position `index` in vertex `other`.
            pass1 = []
            for (index_of_vertex_in_graph, vertex) in enumerate(self.vertices):
                replacement = []
                for (index_of_edge_in_vertex, edge) in enumerate(vertex):
                    (v1, v2) = ends[edge]
                    if v1 != v2:
                        if v1 == index_of_vertex_in_graph:
                            other_end = v2
                        else:
                            other_end = v1
                        other_index = self.vertices[other_end].index(edge)
                    else:
                        other_end = v1 # == v2, that is *this* vertex
                        # presume `index_of_edge_in_vertex` is *not* the first
                        # occurrence of edge
                        other_index = vertex.index(edge)
                        if other_index == index_of_edge_in_vertex:
                            # indeed it is, take next occurrence
                            other_index = vertex.index(edge,
                                                       index_of_edge_in_vertex+1)
                    # replace other_index with index of *next* edge
                    # (in the vertex cyclic order)
                    if other_index == len(self.vertices[other_end])-1:
                        other_index = 0
                    else:
                        other_index += 1
                    replacement.append((other_end, other_index, edge))
                pass1.append(replacement)

            # pass2: now build a linear list, each element of the list
            # corresponding to an half-edge, of triples `(pos, seen,
            # edge)` where `pos` is the index in this list where the other
            # endpoint of that edge is located, `seen` is a flag, set to
            # `False` for half-edges that have not yet been walked
            # through, and `edge` is the corresponding edge.
            pass2 = []
            # build indices to the where each vertex begins in the linear list
            vi=[0]
            for vertex in self.vertices:
                vi.append(vi[-1]+len(vertex))
            # build list from collapsing the 2-level structure
            for vertex in pass1:
                for triplet in vertex:
                    pass2.append([vi[triplet[0]]+triplet[1], False, triplet[2]])

            # pass3: pick up each element of the linear list, and follow it
            # until we come to an already marked one.
            result = []
            pos = 0
            while pos < len(pass2):
                # fast forward to an element that we've not yet seen
                while (pos < len(pass2)) and (pass2[pos][1] == True):
                    pos += 1
                if pos >= len(pass2):
                    break
                # walk whole chain of edges
                i = pos
                result.append([]) # new boundary component
                while pass2[i][1] == False:
                    result[-1].append(pass2[i][2])
                    pass2[i][1] = True
                    i = pass2[i][0]
                pos += 1

            # save result for later reference
            self._boundary_components = set(CyclicTuple(bc) for bc in result)
        
        # that's all, folks!
        return self._boundary_components

    def contract(self, edgeno):
        """Return new `Graph` obtained by contracting the specified edge.

        The returned graph is presented in canonical form, that is,
        vertices are ordered lexicographically, longest ones first.
        
        Examples::

          >>> Graph([Vertex([2,2,0]), Vertex([0,1,1])]).contract(0)
          Graph([Vertex([1, 1, 0, 0])])
          >>> Graph([Vertex([2,1,0]), Vertex([2,0,1])]).contract(1)
          Graph([Vertex([0, 1, 1, 0])])

        The M_{1,1} trivalent graph yield the same result no matter
        what edge is contracted::

          >>> Graph([Vertex([2,1,0]), Vertex([2,1,0])]).contract(0)
          Graph([Vertex([1, 0, 1, 0])])
          >>> Graph([Vertex([2,1,0]), Vertex([2,1,0])]).contract(1)
          Graph([Vertex([0, 1, 0, 1])])
          >>> Graph([Vertex([2,1,0]), Vertex([2,1,0])]).contract(2)
          Graph([Vertex([1, 0, 1, 0])])

        If boundary components have already been computed, they are
        adapted and set in the contracted graph too::

          >>> g1 = Graph([Vertex([2,1,1]), Vertex([2,0,0])])
          >>> g1.boundary_components() # compute b.c.'s
          set([CyclicTuple((2, 0, 2, 1)), CyclicTuple((0,)), CyclicTuple((1,))])
          >>> g2 = g1.contract(2)
          >>> g2.boundary_components()
          set([CyclicTuple((0,)), CyclicTuple((0, 1)), CyclicTuple((1,))])

          >>> g1 = Graph([Vertex([2,1,0]), Vertex([2,0,1])])
          >>> g1.boundary_components() # compute b.c.'s
          set([CyclicTuple((0, 1)), CyclicTuple((1, 2)), CyclicTuple((2, 0))])
          >>> g2 = g1.contract(2)
          >>> g2.boundary_components()
          set([CyclicTuple((0,)), CyclicTuple((0, 1)), CyclicTuple((1,))])

        In the above examples, notice that any reference to edge `2`
        has been removed from the boundary cycles after contraction.

        """
        # check that we are not contracting a loop or an external edge
        assert self.endpoints[edgeno][0] != self.endpoints[edgeno][1], \
               "Graph.contract: cannot contract a loop."
        assert (self.endpoints[edgeno][0] is not None) \
               and (self.endpoints[edgeno][1] is not None), \
               "Graph.contract: cannot contract an external edge."
        assert (edgeno >= 0) and (edgeno < self.num_edges), \
               "Graph.contract: invalid edge number (%d):"\
               " must be in range 0..%d" \
               % (edgeno, self.num_edges)

        if self._contractions[edgeno] is None:
            # store position of the edge to be contracted at the endpoints
            i1 = min(self.endpoints[edgeno])
            i2 = max(self.endpoints[edgeno])
            pos1 = self.vertices[i1].index(edgeno)
            pos2 = self.vertices[i2].index(edgeno)

            # Build new list of vertices, removing the contracted edge and
            # shifting all indices above:
            #   - edges numbered 0..edgeno-1 are unchanged;
            #   - edges numbered `edgeno+1`.. are renumbered, 
            #     shifting the number down one position.
            renumber_edges = dict((i+1,i)
                                  for i in xrange(edgeno, self.num_edges))
            #   - edge `edgeno` is removed (subst with `None`)
            renumber_edges[edgeno] = None  
            # See `itranslate` in utils.py for how this prescription is
            # encoded in the `renumber_edges` mapping.
            new_vertices = [ self._vertex_factory(itranslate(renumber_edges, v))
                             for v in self.vertices ]

            # Mate endpoints of contracted edge:
            # 0. make copies of vertices `v1`, `v2` so that subsequent
            #    operations do not alter the (possibly) shared `Vertex`
            #    object.
            v1 = copy(new_vertices[i1])
            v2 = copy(new_vertices[i2])
            # 1. Rotate endpoints `v1`, `v2` so that the given edge
            #    appears *last* in `v1` and *first* in `v2` (*Note:*
            #    the contracted edge has already been deleted from
            #    `v1` and `v2`, so index positions need to be adjusted):
            if (0 < pos1) and (pos1 < len(v1)):
                v1.rotate(pos1)
            if (0 < pos2) and (pos2 < len(v2)):
                v2.rotate(pos2)
            # 2. Join vertices by concatenating the list of incident
            # edges:
            v1.extend(v2)

            # set new `v1` vertex in place of old first endpoint, 
            new_vertices[i1] = v1
            # and remove second endpoint from list of new vertices
            del new_vertices[i2]

            # vertices with index above `i2` are now shifted down one place
            renumber_vertices = dict((i+1,i)
                                     for i in xrange(i2, self.num_vertices))
            # vertex `i2` is mapped to vertex `i1`
            renumber_vertices[i2] = i1
            new_endpoints = [ tuple(itranslate(renumber_vertices, ep))
                              for ep in  self.endpoints ]
            del new_endpoints[edgeno]

            numbering = None
            if self.numbering is not None:
                numbering = dict((CyclicTuple(itranslate(renumber_edges, c)), n)
                                 for (c,n) in self.numbering.iteritems())

            bc = None
            if self._boundary_components is not None:
                if numbering is not None:
                    bc = set(numbering.iterkeys())
                else:
                    bc = set(CyclicTuple(itranslate(renumber_edges, c))
                             for c in self._boundary_components)

            # build new graph 
            self._contractions[edgeno] = \
                                       Graph(new_vertices,
                                             vertex_factory=self._vertex_factory,
                                             endpoints = new_endpoints,
                                             num_edges = self.num_edges - 1,
                                             num_external_edges = self.num_external_edges,
                                             numbering = numbering,
                                             _boundary_components = bc,
                                             _parent = (self, edgeno))
            
        elif (self.numbering is not None) \
             and (self._contractions[edgeno].numbering is None):
            # see above for the meaning of `renumber_edges`
            renumber_edges = dict((i+1,i)
                                  for i in xrange(edgeno, self.num_edges))
            renumber_edges[edgeno] = None  
            self._contractions[edgeno].numbering = \
                                                 dict((CyclicTuple(itranslate(renumber_edges, c)), n)
                                                      for (c,n) in self.numbering.iteritems())
            
            assert set(self._contractions[edgeno]._boundary_components) == \
                   set(self._contractions[edgeno].numbering.iterkeys()), \
                   "Graph.contract:" \
                   " numbering keys after contraction differs"\
                   " from boundary components computed from"\
                   " non-numbered sibling graph"
                   
        return self._contractions[edgeno]
        
    def edges(self):
        """Iterate over edge colorings."""
        return xrange(0, self.num_edges)
    
    def genus(self):
        """Return the genus g of this `Graph` object."""
        # compute value if not already done
        if (self._genus is None):
            n = self.num_boundary_components()
            K = self.num_vertices
            L = self.num_edges
            # by Euler, K-L+n=2-2*g
            self._genus = (L - K - n + 2) / 2
        return self._genus


    def graft(self, G, v):
        """Return new `Graph` formed by grafting graph `G` into vertex
        with index `v`.  The number of"external" edges in `G` must match the
        valence of `v`.
        """
        assert G.num_external_edges == len(self.vertices[v]), \
               "Graph.graft:" \
               " attempt to graft %d-legged graph `%s`"\
               " into %d-valent vertex `%s`" \
               % (G.num_external_edges, G,
                  len(self.vertices[v]), self.vertices[v])
        vertextype = self._vertex_factory # micro-optimization

        # edges of `G` are renumbered depending on whether
        # they are internal of external edges:
        #   - internal edges in `G` have numbers ranging from 0 to
        #     `G.num_edges`: they get new numbers starting from
        #     `self.num_edges` and counting upwards
        renumber_g_edges = dict((x,x+self.num_edges)
                                for x in xrange(G.num_edges))
        #   - external edges in `G` are mated with edges incoming to
        #     vertex `v`: the first external edge (labeled -1)
        #     corresponds to the first edge in `v`, the second
        #     external edge (labeled -2) to the second edge in `v`,
        #     and so on.
        renumber_g_edges.update((-n-1,l)
                                for (n,l) in enumerate(self.vertices[v]))

        # the first `v-1` vertices of the new graph are the first
        # `v-1` vertices of `self`; then come vertices `v+1`,... of
        # `self`; vertices from `G` come last in the new graph
        new_vertices = (self.vertices[:v] 
                        + self.vertices[v+1:] 
                        + [ vertextype(itranslate(renumber_g_edges, gv))
                            for gv in G.vertices ])

##         # map each mated edge in `self` with the endpoint of the
##         # corresponding external edge in `G`
##         g_endpoint = dict( (l,G.endpoints[-n-1][0])
##                            for (n,l) in enumerate(self.vertices[v]))
        
##         # `G.endpoints` lists external edges last
##         new_endpoints = self.endpoints[:self.num_edges] \
##                         + G.endpoints[:G.num_edges]
##         for edge in self.vertices[v]:
##             v1, v2 = self.endpoints[edge]
##             if v == v1:
##                 new_endpoints[edge] = (v2, g_endpoint[edge]+self.num_vertices-1)
##             else: # v == v2
##                 new_endpoints[edge] = (v1, g_endpoint[edge]+self.num_vertices-1)

        return Graph(new_vertices, vertex_factory=vertextype,
                     #endpoints = new_endpoints,
                     num_edges = self.num_edges + G.num_edges,
                     num_external_edges = self.num_external_edges)


    def is_canonical(self):
        """Return `True` if this `Graph` object is canonical.

        A graph is canonical iff:
        1) Each vertex is represented by the maximal sequence, among all
           sequences representing the same cyclic order.
        2) Vertices are sorted in lexicographic order.

        Examples::
          >>> Graph([Vertex([2,1,0]), Vertex([2,1,0])]).is_canonical()
          True             
          >>> Graph([Vertex([2,1,0]), Vertex([2,0,1])]).is_canonical()
          True             
          >>> Graph([Vertex([2,0,1]), Vertex([2,1,0])]).is_canonical()
          False
          >>> Graph([Vertex([0,1,2]), Vertex([2,1,0])]).is_canonical()
          False 
        """
        previous_vertex = None
        for vertex in self.vertices:
            if not vertex.is_canonical_representative():
                return False
            if previous_vertex and (previous_vertex < vertex):
                return False
            previous_vertex = vertex
        return True


    def is_connected(self):
        """Return `True` if graph is connected.

        Count all vertices that we can reach from the 0th vertex,
        using a breadth-first algorithm; the graph is connected iff
        this count equals the number of vertices.

        See:
          http://brpreiss.com/books/opus4/html/page554.html#SECTION0017320000000000000000
          http://brpreiss.com/books/opus4/html/page561.html#SECTION0017341000000000000000
          
        Examples::
          >>> Graph([Vertex([3, 3, 0, 0]), Vertex([2, 2, 1, 1])]).is_connected()
          False
          >>> Graph([Vertex([3, 1, 2, 0]), Vertex([3, 0, 2, 1])]).is_connected()
          True
        """
        endpoints = self.endpoints
        visited_edges = set()
        visited_vertices = set()
        vertices_to_visit = [0]
        for vi in vertices_to_visit:
            # enqueue neighboring vertices that are not connected by
            # an already-visited edge
            for l in self.vertices[vi]:
                if l not in visited_edges:
                    # add other endpoint of this edge to the to-visit list
                    if endpoints[l][0] == vi:
                        other = endpoints[l][1]
                    else:
                        other = endpoints[l][0]
                    if other not in visited_vertices:
                        vertices_to_visit.append(other)
                    visited_edges.add(l)
                visited_vertices.add(vi)
        return (len(visited_vertices) == len(self.vertices))


    def is_loop(self, edge):
        """Return `True` if `edge` is a loop (i.e., the two endpoint coincide).
        """
        return self.endpoints[edge][0] == self.endpoints[edge][1]
        

    def is_orientation_reversing(self, automorphism):
        """Return `True` if `automorphism` reverses orientation of
        this `Graph` instance."""
        pv = automorphism[0]
        result = pv.sign()
        def arrow(endpoints):
            if endpoints[0]>endpoints[1]:
                return -1
            else:
                return +1
        for before_ep, after_ep in izip(self.endpoints,
                                        [ (pv[e[0]], pv[e[1]])
                                          for e in self.endpoints ]):
            result *= arrow(before_ep)*arrow(after_ep)
        return (-1 == result)


    def is_oriented(self):
        """Return `True` if `Graph` is orientable.

        A ribbon graph is orientable iff it has no
        orientation-reversing automorphism.

        Enumerate all automorphisms of `graph`, end exits with `False`
        result as soon as one orientation-reversing one is found.

        Examples::

          >>> Graph([Vertex([1,0,1,0])]).is_oriented()
          True

          >>> Graph([Vertex([2, 0, 1]), Vertex([2, 0, 1])]).is_oriented()
          True
          
          >>> Graph([Vertex([2, 1, 0]), Vertex([2, 0, 1])]).is_oriented()
          True
          
          >>> Graph([Vertex([2, 1, 1]), Vertex([2, 0, 0])]).is_oriented()
          True

          >>> Graph([Vertex([3, 2, 2, 0, 1]), Vertex([3, 1, 0])], \
                    numbering={CyclicTuple((2,)):      0,  \
                               CyclicTuple((0, 1)):    1,  \
                               CyclicTuple((3, 1)):    2,  \
                               CyclicTuple((0, 3, 2)): 3}) \
                               .is_oriented()
          True
          >>> Graph([Vertex([2, 3, 1]), Vertex([2, 1, 3, 0, 0])], \
                       numbering={CyclicTuple((0,)):      0,  \
                                  CyclicTuple((1, 3)):    2,  \
                                  CyclicTuple((3, 0, 2)): 3,  \
                                  CyclicTuple((2, 1)):    1}) \
                               .is_oriented()
          True
        """
        for a in self.automorphisms():
            if self.is_orientation_reversing(a):
                return False
        # no orientation reversing automorphism found
        return True

    def isomorphisms_to(self, other):
        """Iterate over isomorphisms from `self` to `other`.

        An isomorphism is represented by a tuple `(pv, rot, pe)` where:

          - `pv` is a permutation of ther vertices: the `i`-th vertex
            of `g1` is sent to the `pv[i]`-th vertex of `g2`, rotated
            by `rot[i]` places leftwards;

          - `pe` is a permutation of the edge colors: edge `i` in `g1`
            is mapped to edge `pe[i]` in `g2`.

        This method can iterate over the automorphism group of a
        graph::

          >>> g1 = Graph([Vertex([2, 1, 1]), Vertex([2, 0, 0])])
          >>> for f in g1.isomorphisms_to(g1): print f
          ({0: 1, 1: 0}, (0, 0), {0: 1, 1: 0, 2: 2})
          ({0: 0, 1: 1}, (0, 0), {0: 0, 1: 1, 2: 2})

        Or it can find the isomorphisms between two given graphs::

          >>> for f in g1.isomorphisms_to(Graph([Vertex([2, 2, 0]), \
                                                 Vertex([1, 1, 0])])):
          ...   print f
          ({0: 1, 1: 0}, (1, 1), {0: 2, 1: 1, 2: 0})
          ({0: 0, 1: 1}, (1, 1), {0: 1, 1: 2, 2: 0})

        If there are no isomorphisms connecting the two graphs, then no
        item is returned by the iterator::

          >>> g2 = Graph([Vertex([2, 1, 0]), Vertex([2, 0, 1])])
          >>> list(g1.isomorphisms_to(g2))
          []

        """
        ## Compute all permutations of vertices that preserve valence.
        ## (A permutation `p` preserves vertex valence if vertices `v`
        ## and `p[v]` have the same valence.)
        vs1 = self.valence_spectrum()
        vs2 = other.valence_spectrum()
        
        # save valences as we have no guarantees that keys() method
        # will always return them in the same order
        valences = vs1.keys()

        assert set(valences) == set(vs2.keys()), \
               "Graph.isomorphisms_to: "\
               " graphs `%s` and `%s` differ in vertex valences: `%s` vs `%s`" \
               % (self, other, valences, vs2.keys())
        assert dict((val, len(vs1[val])) for val in valences) \
               == dict((val, len(vs2[val])) for val in valences), \
               "Graph.isomorphisms_to: graphs `%s` and `%s`" \
               " have unequal vertex distribution by valence: `%s` vs `%s`" \
               % (self, other, vs1, vs2)
        
        # it's easier to compute vertex-preserving permutations
        # starting from the order vertices are given in the valence
        # spectrum; will rearrange them later.
        domain = Permutation(concat([ vs1[val] for val in valences ])).inverse()
        codomain = Permutation()
        codomain.update(dict(concat(zip(vs1[val],vs2[val]) for val in valences)))
        permutations_of_vertices_of_same_valence = [
            [ tuple(codomain.itranslate(p))
              for p in InplacePermutationIterator(vs1[val]) ]
            for val in valences
            ]

        #: Permutations of the vertex order that preserve valence.
        candidate_pvs = [
            domain.rearrange(concat(ps))
            for ps
            in SetProductIterator(permutations_of_vertices_of_same_valence)
            ]

        # use "repetition patterns" to avoid mapping loop-free
        # vertices into vertices with loops, and viceversa.
        # FIXME: as loop-free vertices are much more common than
        # looped ones, this might turn out to be slower than just
        # checking all possible rotations.  Maybe just check
        # the number of loops instead of building the full repetition pattern?
        rps1 = [ v.repetition_pattern() for v in self.vertices ]
        rps2 = [ v.repetition_pattern() for v in other.vertices ]
        for vertex_index_map in candidate_pvs:
            pvrots = [ [] for x in xrange(len(self.vertices)) ]
            for (j, (b1, rp1), (b2, rp2)) \
                    in izip(count(),
                            rps1,
                            (rps2[i] for i in vertex_index_map)):
                # Items in pvrots are lists (of length
                # `self.num_vertices`), composed of tuples
                # `(i1,b1+s,i2,b2)`, meaning that vertex at index
                # `i1` in `self` should be mapped to vertex at index
                # `i2` in `other` with shift `s` and bases `b1` and `b2`
                # (that is, `self.vertices[i1][b1+s:b1+s+len]` should be
                # mapped linearly onto `other.vertices[i2][b2:b2+len]`).
                # `rp1` is a kind of "derivative" of `v1`; we gather
                # the displacement `b1+s` for `v1` by summing elements
                # of rp1 up to -but not including- the `s`-th.
                pvrots[j].extend([ (j,b1+sum(rp1[:s]),vertex_index_map[j],b2)
                                   for s
                                   in rp1.all_shifts_for_linear_eq(rp2) ])
            for pvrot in SetProductIterator(pvrots):
                pe = Permutation()
                pe_is_ok = True  # optimistic default
                for (i1,b1,i2,b2) in pvrot:
                    v1 = self.vertices[i1]
                    v2 = other.vertices[i2]
                    if not pe.extend(v1[b1:b1+len(v1)],
                                     v2[b2:b2+len(v2)]):
                        # cannot extend, proceed to next `pvrot`
                        pe_is_ok = False
                        break
                if pe_is_ok and (len(pe) > 0):
                    pv = Permutation(t[2] for t in pvrot)
                    # Check that the combined action of `pv` and `pe`
                    # preserves the adjacency relation.  Note:
                    #   - we make list comprehensions of both adjacency lists
                    #     to avoid inverting `pe`: that is, we compare the
                    #     the adjacency lists in the order they have in `self`,
                    #     but with the vertex numbering from `other`;
                    #   - elements of the adjacency lists are made into
                    #     `set`s for unordered comparison;
                    if 0 != cmp([ set(other.endpoints[pe[x]])
                                  for x in xrange(other.num_edges) ],
                                [ set(pv.itranslate(self.endpoints[x]))
                                  for x in xrange(self.num_edges) ]):
                        continue # to next `pvrot`
                    if self.numbering is not None:
                        assert other.numbering is not None, \
                               "Graph.isomorphisms_to: " \
                               "Numbered and un-numbered graphs mixed in arguments."
                        assert len(self.numbering) == len(other.numbering), \
                               "Graph.isomorphisms_to: " \
                               "Arguments differ in number of boundary components."
                        pe_does_not_preserve_bc = False
                        for bc in self.boundary_components():
                            if self.numbering[bc] != \
                                   other.numbering[CyclicTuple(pe.itranslate(bc))]:
                                pe_does_not_preserve_bc = True
                                break
                        if pe_does_not_preserve_bc:
                            continue # to next `pvrot`
                    rots = tuple(t[1]-t[3] for t in pvrot)
                    yield (pv, rots, pe)
    
    def num_boundary_components(self):
        """Return the number of boundary components of this `Graph` object.

        Each boundary component is represented by the list of (colored)
        edges.

        Examples::
          >>> Graph([Vertex([2,1,0]), Vertex([2,1,0])]).num_boundary_components()
          1
          >>> Graph([Vertex([2,1,0]), Vertex([2,0,1])]).num_boundary_components()
          3
        """
        # compute boundary components and cache result
        if self._num_boundary_components is None:
            self._num_boundary_components = len(self.boundary_components())

        return self._num_boundary_components

    def projection(self, other):
        """Return the component of the projection of `self` on the
        basis vector `other`.
        """
        assert isinstance(other, Graph), \
               "Graph.__eq__:" \
               " called with non-Graph argument `other`: %s" % other
        try:
            # if there is any morphism, then return `True`
            iso = self.isomorphisms_to(other).next()
            pv = iso[0]
            result = pv.sign()
            for (e0, e1) in [ (pv[e[0]], pv[e[1]])
                              for e in self.endpoints ]:
                if e0 > e1:
                   result = -result 
            return result
        except StopIteration:
            # list of morphisms is empty, graphs are not equal.
            return 0

    def valence_spectrum(self):
        """Return a dictionary mapping valences into vertex indices.

        Examples::

           >>> Graph([Vertex([1,1,0,0])]).valence_spectrum()
           {4: [0]}

           >>> Graph([Vertex([1,1,0]), Vertex([2,2,0])]).valence_spectrum()
           {3: [0, 1]}

           >>> Graph([Vertex([3, 1, 0, 1]), \
                      Vertex([4, 4, 0]), Vertex([3, 2, 2])]).valence_spectrum()
           {3: [1, 2], 4: [0]}
        """
        # compute spectrum on first invocation
        if self._valence_spectrum is None:
            self._valence_spectrum = {}
            for (index, vertex) in enumerate(self.vertices):
                l = len(vertex)
                if l in self._valence_spectrum:
                    self._valence_spectrum[l].append(index)
                else:
                    self._valence_spectrum[l] = [index]
            # consistency checks
            assert set(self._valence_spectrum.keys()) == set(self._vertex_valences), \
                   "Graph.valence_spectrum:" \
                   "Computed valence spectrum `%s` does not exhaust all " \
                   " vertex valences %s" \
                   % (self._valence_spectrum, self._vertex_valences)
            assert set(concat(self._valence_spectrum.values())) \
                   == set(range(self.num_vertices)), \
                   "Graph.valence_spectrum:" \
                   "Computed valence spectrum `%s` does not exhaust all " \
                   " %d vertex indices" % (self._valence_spectrum, self.num_vertices)
        return self._valence_spectrum


def MakeNumberedGraphs(graph):
    """Return all distinct (up to isomorphism) decorations of `graph`
    with a numbering of the boundary cycles.

    Examples::

      >>> g1 = Graph([Vertex([2,0,0]), Vertex([2,1,1])])
      >>> MakeNumberedGraphs(g1)
      [Graph([Vertex([2, 0, 0]), Vertex([2, 1, 1])],
             numbering={CyclicTuple((2, 1, 2, 0)): 0,
                        CyclicTuple((0,)): 2,
                        CyclicTuple((1,)): 1}),
       Graph([Vertex([2, 0, 0]), Vertex([2, 1, 1])],
             numbering={CyclicTuple((2, 1, 2, 0)): 1,
                        CyclicTuple((0,)): 0,
                        CyclicTuple((1,)): 2}),
       Graph([Vertex([2, 0, 0]), Vertex([2, 1, 1])],
             numbering={CyclicTuple((2, 1, 2, 0)): 2,
                        CyclicTuple((0,)): 0,
                        CyclicTuple((1,)): 1})]
       
    Note that, when only one numbering out of many possible ones is
    returned because of isomorphism, the returned numbering may not be
    the trivial one (it is actually the first permutation of 0..n
    returned by `InplacePermutationIterator`)::
      
      >>> g2 = Graph([Vertex([2,1,0]), Vertex([2,0,1])])
      >>> MakeNumberedGraphs(g2)
      [Graph([Vertex([2, 1, 0]), Vertex([2, 0, 1])],
              numbering={CyclicTuple((2, 0)): 1,
                         CyclicTuple((0, 1)): 0,
                         CyclicTuple((1, 2)): 2})]

    When the graph has only one boundary component, there is only one
    possible numbering, which is actually returned::
    
      >>> g3 = Graph([Vertex([1,0,1,0])])
      >>> MakeNumberedGraphs(g3)
      [Graph([Vertex([1, 0, 1, 0])],
              numbering={CyclicTuple((1, 0, 1, 0)): 0})]
      
    """
    graphs = []
    bc = list(bcy for bcy in graph.boundary_components())
    n = graph.num_boundary_components()

    for numbering in InplacePermutationIterator(range(n)):
        # make a copy of `graph` with the given numbering
        g = copy(graph)
        g.numbering = dict((bc[x], numbering[x]) for x in xrange(n))

        # only add `g` to list if it is *not* isomorphic to a graph
        # already in the list
        if g not in graphs:
            graphs.append(g)

    # set the `._siblings` attribute on the given graph,
    # pointing to the numbered decorated versions
    graph._siblings = graphs

    return graphs


class ConnectedGraphsIterator(BufferingIterator):
    """Iterate over all connected numbered graphs having vertices of
    the prescribed valences.
    
    Examples::

      >>> for g in ConnectedGraphsIterator([4]): print g
      Graph([Vertex([1, 0, 1, 0])], numbering={CyclicTuple((1, 0, 1, 0)): 0})
      Graph([Vertex([1, 1, 0, 0])],
            numbering={CyclicTuple((0,)): 0,
                       CyclicTuple((1, 0)): 2,
                       CyclicTuple((1,)): 1})
      Graph([Vertex([1, 1, 0, 0])],
            numbering={CyclicTuple((0,)): 1,
                       CyclicTuple((1, 0)): 0,
                       CyclicTuple((1,)): 2})
      Graph([Vertex([1, 1, 0, 0])],
            numbering={CyclicTuple((0,)): 2,
                       CyclicTuple((1, 0)): 1,
                       CyclicTuple((1,)): 0})

      >>> for g in ConnectedGraphsIterator([3,3]): print g
      Graph([Vertex([2, 0, 1]), Vertex([2, 0, 1])],
            numbering={CyclicTuple((2, 0, 1, 2, 0, 1)): 0})
      Graph([Vertex([2, 1, 0]), Vertex([2, 0, 1])],
            numbering={CyclicTuple((2, 0)): 1,
                       CyclicTuple((0, 1)): 0,
                       CyclicTuple((1, 2)): 2})
      Graph([Vertex([2, 1, 1]), Vertex([2, 0, 0])],
            numbering={CyclicTuple((2, 0, 2, 1)): 0,
                       CyclicTuple((0,)): 2,
                       CyclicTuple((1,)): 1})
      Graph([Vertex([2, 1, 1]), Vertex([2, 0, 0])],
            numbering={CyclicTuple((2, 0, 2, 1)): 1,
                       CyclicTuple((0,)): 0,
                       CyclicTuple((1,)): 2})
      Graph([Vertex([2, 1, 1]), Vertex([2, 0, 0])],
            numbering={CyclicTuple((2, 0, 2, 1)): 2,
                       CyclicTuple((0,)): 0,
                       CyclicTuple((1,)): 1})

    Generation of all graphs with prescribed vertex valences `(v_1,
    v_2, ..., v_n)` goes this way:
    
      1) Generate all lists `L` of length `2*n` comprising the symbols
         `{0,...,n-1}`, each of which is repeated exactly twice;

      2) Pick such a list `L` and break it into smaller pieces of
         length `v_1`, ..., `v_n`, each one corresponding to a vertex
         (this is actually done in the `Graph` class constructor),
         effectively building a graph `G`.

      3) Test the graph `G` for connectedness: if it's not connected,
         then go back to step 2).

      4) Compare `G` with all graphs previously found: if there is a
         permutation of the edge labels that transforms `G` into an
         already-found graph, then go back to step 2).

    """

    __slots__ = [
        '_graphs',
        ]

    def __init__(self, vertex_valences, vertex_factory=VertexCache()):
        assert debug.is_sequence_of_integers(vertex_valences), \
               "ConnectedGraphsIterator: " \
               " argument `vertex_valences` must be a sequence of integers,"\
               " but got %s" % vertex_valences
        assert 0 == sum(vertex_valences) % 2, \
               "ConnectedGraphsIterator: " \
               " sum of vertex valences must be divisible by 2"

        self._graphs = GivenValenceGraphsIterator(vertex_valences,
                                                  vertex_factory=vertex_factory)

        # initialize superclass
        BufferingIterator.__init__(self)

    def refill(self):
        return MakeNumberedGraphs(self._graphs.next())


class GivenValenceGraphsIterator(object):
    """Iterate over all connected (un-numbered) ribbon graphs having
    vertices of the prescribed valences.
    
    Examples::

      >>> for g in GivenValenceGraphsIterator([4]): print g
      Graph([Vertex([1, 0, 1, 0])])
      Graph([Vertex([1, 1, 0, 0])])

      >>> for g in GivenValenceGraphsIterator([3,3]): print g
      Graph([Vertex([2, 0, 1]), Vertex([2, 0, 1])])
      Graph([Vertex([2, 1, 0]), Vertex([2, 0, 1])])
      Graph([Vertex([2, 1, 1]), Vertex([2, 0, 0])])

    Generation of all graphs with prescribed vertex valences `(v_1,
    v_2, ..., v_n)` proceeds this way:
    
      1) Generate all lists `L` of length `2*n` comprising the symbols
         `{0,...,n-1}`, each of which is repeated exactly twice;

      2) Pick such a list `L` and break it into smaller pieces of
         length `v_1`, ..., `v_n`, each one corresponding to a vertex
         (this is actually done in the `Graph` class constructor),
         effectively building a graph `G`.

      3) Test the graph `G` for connectedness: if it's not connected,
         then go back to step 2).

      4) Compare `G` with all graphs previously found: if there is a
         permutation of the edge labels that transforms `G` into an
         already-found graph, then go back to step 2).

    """

    __slots__ = [
        'graphs',
        'vertex_factory',
        '_edge_seq_iterator',
        '_morphism_factory',
        '_vertex_valences',
        ]

    def __init__(self, vertex_valences, vertex_factory=VertexCache()):
        assert debug.is_sequence_of_integers(vertex_valences), \
               "GivenValenceGraphsIterator: " \
               " argument `vertex_valences` must be a sequence of integers,"\
               " but got %s" % vertex_valences
        assert 0 == sum(vertex_valences) % 2, \
               "GivenValenceGraphsIterator: " \
               " sum of vertex valences must be divisible by 2"

        self.vertex_factory = vertex_factory
        self.graphs = []
        self._morphism_factory = None
        self._vertex_valences = vertex_valences

        # build list [0,0,1,1,...,n-1,n-1]
        starting_edge_seq=[]
        for l in xrange(0, sum(vertex_valences)/2):
            starting_edge_seq += [l,l]
        self._edge_seq_iterator = InplacePermutationIterator(starting_edge_seq)

    def __iter__(self):
        return self
    
    def next(self):
        for edge_seq in self._edge_seq_iterator:
            # Break up `edge_seq` into smaller sequences corresponding
            # to vertices.
            vertices = []
            base = 0
            for current_vertex_index in xrange(len(self._vertex_valences)):
                VLEN = self._vertex_valences[current_vertex_index]
                vertices.append(self.vertex_factory(edge_seq[base:base+VLEN]))
                base += VLEN

            current = Graph(vertices,
                            edge_seq=tuple(edge_seq),
                            vertex_factory=self.vertex_factory,)
            if not (current.is_canonical() and current.is_connected()):
                continue
            
            # now walk down the list and remove isomorphs
            current_is_not_isomorphic_to_already_found = True
            for candidate in self.graphs:
                # if there is any isomorphism, then reject current
                try:
                    candidate.isomorphisms_to(current).next()
                    # if we get here, an isomorphism has been found,
                    # so try again with a new `current` graph
                    current_is_not_isomorphic_to_already_found = False
                    break
                except StopIteration:
                    # no isomorphism has been found, try with next
                    # `candidate` graph
                    pass
            if current_is_not_isomorphic_to_already_found:
                self.graphs.append(current)
                return current
            # otherwise, continue with next `current` graph

        # no more graphs to generate
        raise StopIteration


def AlgorithmB(n):
    """Iterate over all binary trees with `n+1` internal nodes in
    pre-order.  Equivalently, iterate over all full binary trees with
    `n+2` leaves.

    Returns a pair `(l,r)` of list, where `l[j]` and `r[j]` are the
    left and right child nodes of node `j`.  A `None` in `l[j]`
    (resp. `r[j]`) means that node `j` has no left (resp. right) child.

    The number of such trees is equal to the n-th Catalan number::

      >>> [ len(list(AlgorithmB(n))) for n in xrange(6) ]
      [1, 2, 5, 14, 42, 132]

    This is "Algorithm B" in Knuth's Volume 4, fasc. 4, section 7.2.1.6
    """
    # B1 -- Initialize
    l = [ k+1 for k in xrange(n) ] + [None]
    r = [ None ] * (n+1)
    while True:
        # B2 -- Visit
        yield (l, r)
        # B3 -- Find `j`
        j = 0
        while l[j] == None:
            r[j] = None
            l[j] = j+1
            j += 1
            if j >= n:
                raise StopIteration
        # B4 -- Find `k` and `y`
        y = l[j]
        k = None
        while r[y] != None:
            k = y
            y = r[y]
        # B5 -- Promote `y`
        if k is not None:
            r[k] = None
        else:
            l[j] = None
        r[y] = r[j]
        r[j] = y


def Tree(nodeseq=[], vertex_factory=Vertex):
    """Construct a tree fatgraph from sequence of internal nodes.

    Items in `nodeseq` are sequences `(c[0], c[1], ..., c[n])` where
    `c[i]` are the labels (index number) of child nodes; if any
    `c[i]` is `None`, then a new terminal node is appended as child.
    The node created from the first item in `nodeseq` gets the label
    `0`, the second node gets the label `1`, and so on.
        
    Each internal node with `n` children is represented as a fatgraph
    vertex with `n+1` edges; the first one connects the node with its
    parent, and the other ones with the children, in the order they
    were given in the constructor.  Terminal nodes (i.e., leaves) are
    represented as edges with one loose end; that is, terminal nodes
    are *not* represented as vertices.

    Loose-end edges are given a negative index color, to easily
    distinguish them from regular edges, and are not counted in the
    `num_edges` attribute.

      >>> Tree([(1, 2), (None, None), (3, None), (None, None)])
      Graph([Vertex([-1, 0, 1]), Vertex([0, -2, -3]),
             Vertex([1, 2, -4]), Vertex([2, -5, -6])],
             num_external_edges=6)

    """
    edge_to_parent = {}
    next_external_edge_label = -2  # grows downwards: -2,-3,...
    next_internal_edge_label = 0   # grows upwards: 1,2,...
    internal_edge_endpoints = []
    external_edge_endpoints = [ (0, None) ]
    vertices = []
    next_vertex_index = 0
    for cs in nodeseq:
        # Edges incident to this vertex; for the root vertex, the
        # connection to the parent node is just the first external
        # edge (labeled `-1`)
        edges = [ edge_to_parent.get(next_vertex_index, -1) ]
        for child in cs:
            if child is None:
                # terminal node here
                edges.append(next_external_edge_label)
                external_edge_endpoints.append((next_vertex_index, None))
                next_external_edge_label -= 1
            else:
                # internal node here
                edges.append(next_internal_edge_label)
                edge_to_parent[child] = next_internal_edge_label
                internal_edge_endpoints.append((next_vertex_index,
                                                child))
                next_internal_edge_label += 1
        vertices.append(vertex_factory(edges))
        next_vertex_index += 1

    return Graph(vertices,
                 endpoints = internal_edge_endpoints +
                                list(reversed(external_edge_endpoints)),
                 num_edges = next_internal_edge_label,
                 num_external_edges = -next_external_edge_label-1,
                 vertex_factory=vertex_factory)


class TreeIterator(BufferingIterator):
    """Iterate over trees with a specified number of leaves.

    Internal nodes are allowed to have any number of children: the
    iterator is not restricted to binary trees.
    """

    def __init__(self, num_leaves):
        self._internal_edges = num_leaves - 2

        self._trees = [ Tree(zip(l,r))
                        for l,r in AlgorithmB(num_leaves - 2) ]

        BufferingIterator.__init__(self, self._trees)

    def refill(self):
        if self._internal_edges > 1:
            self._internal_edges -= 1
            l = self._internal_edges - 1 # label of edge to contract
            new_trees = [ t.contract(l) for t in self._trees ]
            self._trees = new_trees
            return new_trees
        else:
            raise StopIteration


class MgnGraphsIterator(BufferingIterator):
    """Iterate over all connected numbered graphs having the
    prescribed genus `g` and number of boundary cycles `n`.
    
    Examples::

      >>> for g in MgnGraphsIterator(0,3): print g
      Graph([Vertex([1, 2, 1]), Vertex([2, 0, 0])],
            numbering={CyclicTuple((2, 0, 2, 1)): 0, 
                       CyclicTuple((0,)):         2, 
                       CyclicTuple((1,)):         1})
      Graph([Vertex([1, 2, 1]), Vertex([2, 0, 0])],
            numbering={CyclicTuple((2, 0, 2, 1)): 1,
                       CyclicTuple((0,)):         0,
                       CyclicTuple((1,)):         2})
      Graph([Vertex([1, 2, 1]), Vertex([2, 0, 0])],
            numbering={CyclicTuple((2, 0, 2, 1)): 2,
                       CyclicTuple((0,)):         0,
                       CyclicTuple((1,)):         1})
      Graph([Vertex([1, 0, 2]), Vertex([2, 0, 1])],
            numbering={CyclicTuple((1, 2)): 1,
                       CyclicTuple((0, 1)): 2,
                       CyclicTuple((2, 0)): 0})
      Graph([Vertex([1, 1, 0, 0])], 
            numbering={CyclicTuple((0,)):   0,
                       CyclicTuple((0, 1)): 2,
                       CyclicTuple((1,)):   1})
      Graph([Vertex([1, 1, 0, 0])], 
            numbering={CyclicTuple((0,)):   1,
                       CyclicTuple((0, 1)): 0,
                       CyclicTuple((1,)):   2})
      Graph([Vertex([1, 1, 0, 0])], 
            numbering={CyclicTuple((0,)):   2,
                       CyclicTuple((0, 1)): 1,
                       CyclicTuple((1,)):   0})

      >>> for g in MgnGraphsIterator(1,1): print g
      Graph([Vertex([1, 0, 2]), Vertex([2, 1, 0])],
            numbering={CyclicTuple((1, 0, 2, 1, 0, 2)): 0})
      Graph([Vertex([1, 0, 1, 0])],
            numbering={CyclicTuple((0, 1, 0, 1)): 0})

    """

    __slots__ = [
        '_batch',
        '_current_edge',
        '_num_vertices',
        '_vertex_factory',
        'g',
        'n',
        ]

    def __init__(self, g, n, vertex_factory=VertexCache()):
        assert n > 0, \
               "MgnGraphsIterator: " \
               " number of boundary cycles `n` must be positive,"\
               " but got `%s` instead" % n
        assert (g > 0) or (g == 0 and n >= 3), \
               "MgnGraphsIterator: " \
               " Invalid (g,n) pair (%d,%d): "\
               " need either g>0 or g==0 and n>2" \
               % (g,n)

        #: Prescribed genus of returned graphs
        self.g = g

        #: Prescribed number of boundary components
        self.n = n
        
        #: Factory method to build `Vertex` instances from the
        #  incoming edges list.
        self._vertex_factory = vertex_factory

        #: Unique (up to isomorphism) graphs found so far
        graphs = []
        
        #: Minimum number of edges of a (g,n)-graph
        max_valence = 2 * (2*g + n - 1)

        ## pass 1: Gather all roses.
        roses = []
        for rose in GivenValenceGraphsIterator((max_valence,)):
            if (rose.genus() != self.g) \
                   or (rose.num_boundary_components() != self.n) \
                   or (rose in roses):
                continue
            roses.append(rose)
            # a rose is a valid fatgraph too
            #graphs.extend(MakeNumberedGraphs(rose))
            
        ## pass 2: Gather all 3-valent graphs.
        trivalent = []
        #: Full binary trees
        trees = [ Tree(zip(l,r))
                  for l,r in AlgorithmB(max_valence - 3) ]
        for rose in roses:
            # now substitute the unique vertex with any possible tree
            # and any possible rotation
            for places in xrange(max_valence):
                # need to make a deep copy, because `Vertex` objects are shared
                rotated_rose = Graph([copy(rose[0])])
                rotated_rose[0].rotate(places)
                for tree in trees:
                    graph = rotated_rose.graft(tree, 0)
                    if (graph.genus() != self.g) \
                           or (graph.num_boundary_components() != self.n) \
                           or (graph in trivalent):
                        continue
                    trivalent.append(graph)
                    # insert decorated graphs into iterator buffer
                    graphs.extend(MakeNumberedGraphs(graph))

        #: Graphs to be contracted at next `.refill()` invocation
        self._batch = trivalent

        #: Number of edges of graphs that will be returned by next
        #  `.refill()` call.  Starts with `6*g + 3*n - 7`, which is the
        #  highest-numbered edge in trivalent graphs.
        self._current_edge = 6*g + 3*n - 7

        self._num_vertices = 4*g + 2*n - 4
        
        # initialize superclass with list of roses + trivalent graphs
        BufferingIterator.__init__(self, graphs)

    def refill(self):
        if self._num_vertices == 0:
            raise StopIteration
        
        result = []
        next_batch = []
        for graph in self._batch:
            # contract all edges
            for edge in xrange(graph.num_edges):
                if not graph.is_loop(edge):
                    dg = graph.contract(edge)
                    if dg not in next_batch:
                        # put decorated version into `result`
                        result.extend(MakeNumberedGraphs(dg))
                        # put graph back into next batch for processing
                        next_batch.append(dg)
        self._batch = next_batch
        self._num_vertices -= 1
        return result
    


## main: run tests

if "__main__" == __name__:
    import doctest
    doctest.testmod(optionflags=doctest.NORMALIZE_WHITESPACE)
