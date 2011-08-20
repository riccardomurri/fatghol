#! /usr/bin/env python
#
"""
"""
__docformat__ = 'reStructuredText'


from utils import *
from cyclic import CyclicList,repetition_pattern

from itertools import *
import operator


def vertex_valences_for_given_g_and_n(g,n):
    """
    Examples::
      >>> vertex_valences_for_given_g_and_n(0,3)
      [[4], [3, 3]]
    """
    # with 1 vertex only, there are this many edges:
    L = 2*g + n - 1
    K = 1
    result = []
    while True:
        ps = partitions(2*L, K)
        if len(ps) == 0:
            break
        for p in ps:
            result.append(p)
        K += 1
        L = 2*g + n + K - 2
    return result


class Vertex(CyclicList):
    """A (representative of) a vertex of a ribbon graph.

    A vertex is represented by the cyclically ordered list of its
    (decorated) edges.  The edge colorings may be accessed through a
    (read-only) sequence interface.
    """
    def __init__(self, edge_seq, start=0, end=None):
        """Create `Vertex` instance by excerpting the slice `[start:end]` in `edge_seq`.
        """
        if end is None:
            end = len(edge_seq)
        CyclicList.__init__(self, edge_seq[start:end])

        # the following values will be computed when they are first requested
        self._repetition_pattern = None
        
    def __iter__(self):
        """Return iterator over edges."""
        return list.__iter__(self)

    #def __repr__(self):
    #    return str(self._edges)
    #def __str__(self):
    #    return str(self._edges)
    
    def is_maximal_representative(self):
        """Return `True` if this `Vertex` object is maximal among
        representatives of same cyclic sequence.
        
        Examples::
          >>> Vertex([3,2,1]).is_maximal_representative()
          True
          >>> Vertex([2,1,3]).is_maximal_representative()
          False
          >>> Vertex([1,1]).is_maximal_representative()
          True
          >>> Vertex([1]).is_maximal_representative()
          True
        """
        def wrap_index(i,l):
            if i >= l:
                return i % l
            else:
                return i
        L = len(self)
        for i in xrange(1,L):
            for j in xrange(0,L):
                if self[wrap_index(i+j,L)] < self[j]:
                    # continue with next i
                    break
                elif self[wrap_index(i+j,L)] > self[j]:
                    return False
                # else, continue comparing
        return True

    def repetition_pattern(self):
        """Return the repetition pattern of this `Vertex` object.
        Same as calling `repetition_pattern(this._edges)` but caches
        results.
        """
        if self._repetition_pattern is None:
            self._repetition_pattern = repetition_pattern(self)
        return self._repetition_pattern


class Graph:
    """A fully-decorated ribbon graph.

    Exports a (read-only) sequence interface, through which vertices
    can be accessed.
    """
    def __init__(self, vertex_valences, edge_seq):
        assert is_sequence_of_integers(vertex_valences), \
               "Graph.__init__: parameter `vertex_valences` must be sequence of integers, "\
               "but got '%s' instead" % vertex_valences
        self._vertex_valences = vertex_valences
        assert (sum(vertex_valences) % 2 ) == 0, \
               "Graph.__init__: invalid parameter `vertex_valences`:"\
               "sum of vertex valences must be even."

        self._num_edges = sum(self._vertex_valences) / 2
        self._num_vertices = len(vertex_valences)
        # these values will be computed on-demand
        self._num_boundary_components = None
        self._genus = None
        
        assert is_sequence_of_integers(edge_seq), \
               "Graph.__init__: parameter `edge_seq` must be sequence of integers, "\
               "but got '%s' instead" % edge_seq
        assert max(edge_seq) == self._num_edges, \
               "Graph.__init__: invalid parameter `edge_seq`:"\
               "Sequence of edges %s doesn't match number of edges %d" \
               % (edge_seq, self._num_edges)
        # Break up `edge_seq` into smaller sequences corresponding to vertices.
        self.vertices = []
        base = 0
        for current_vertex_index in xrange(len(vertex_valences)):
            VLEN = vertex_valences[current_vertex_index]
            # FIXME: this results in `edge_seq` being copied into smaller
            # subsequences; can we avoid this by defining a list-like object
            # "vertex" as a "view" on a portion of an existing list?
            self.vertices.append(Vertex(edge_seq, base, base+VLEN))
            base += VLEN

    def __getitem__(self, index):
        return self.vertices[index]

    def __iter__(self):
        """Return iterator over vertices."""
        return iter(self.vertices)

    def __str__(self):
        return str(self.vertices)
            
    def is_canonical(self):
        """Return `True` if this `Graph` object is canonical.

        A graph is canonical iff:
        1) Each vertex is represented by the maximal sequence, among all
           sequences representing the same cyclic order.
        2) Vertices are sorted in lexicographic order.

        Examples::
          >>> Graph([3,3],[[3,2,1],[3,2,1]]).is_canonical()
          True
          >>> Graph([3,3],[[3,2,1],[3,1,2]]).is_canonical()
          True
          >>> Graph([3,3],[[3,1,2],[3,2,1]]).is_canonical()
          False
          >>> Graph([3,3],[[1,2,3],[3,2,1]]).is_canonical()
          False 
        """
        previous_vertex = None
        for vertex in self.vertices:
            if not vertex.is_maximal_representative():
                return False
            if previous_vertex and (previous_vertex < vertex):
                return False
            previous_vertex = vertex
        return True
    
    def endpoints(self, n):
        """Return the endpoints of edge `n`.
    
        The endpoints are returned as a pair (v1,v2) where `v1` and `v2`
        are indices of vertices in this `Graph` object.
        """
        result = []
        for vi in range(len(self.vertices)):
            c = self.vertices[vi].count(n)
            if 2 == c:
                return (vi,vi)
            elif 1 == c:
                result.append(vi)
        if 0 == len(result):
            raise KeyError, "Edge %d not found in graph '%s'" % (n, repr(self))
        return result
    
    def num_edges(self):
        return self._num_edges

    def num_vertices(self):
        return self._num_vertices

    def num_boundary_components(self):
        """Return the number of boundary components of this `Graph` object.

        Each boundary component is represented by the list of (colored)
        edges.

        Examples::
          >>> Graph([3,3], [[3,2,1],[3,2,1]]).num_boundary_components()
          1
          >>> Graph([3,3], [[3,2,1],[3,1,2]]).num_boundary_components()
          3
        """
        # try to return the cached value
        if not (self._num_boundary_components is None):
            return self._num_boundary_components

        # otherwise, compute it now...
        
        L = self.num_edges() + 1
        # for efficiency, gather all endpoints now
        ends = [ endpoints(l) for l in xrange(1,L) ]

        # pass1: build a "copy" of `graph`, replacing each edge coloring
        # with a pair `(other, index)` pointing to the other endpoint of
        # that same edge: the element at position `index` in vertex
        # `other`.
        pass1 = []
        def other(pair, one):
            """Return the member of `pair` not equal to `one`."""
            if pair[0] == one:
                return pair[1]
            else:
                return pair[0]
        for (vertex, vertex_index) in izip(self.vertices, count(0)):
            replacement = []
            for (edge, current_index) in izip(vertex, count(0)):
                (v1, v2) = ends[edge]
                if v1 != v2:
                    other_end = other(ends[edge], vertex_index)
                    other_index = self.vertices[other_end].index(edge)
                else:
                    other_end = v1 # == v2, that is *this* vertex
                    try:
                        # presume this is the first occurrence of edge...
                        other_index = vertex.index(edge, current_index+1)
                    except ValueError:
                        # it's not, take first
                        other_index = vertex.index(edge)
                # replace other_index with index of *next* edge
                # (in the vertex cyclic order)
                if other_index == len(self.vertices[other_end])-1:
                    other_index = 0
                else:
                    other_index += 1
                replacement.append((other_end, other_index))
            pass1.append(replacement)

        # pass2: now build a linear list, each element of the list
        # corresponding to an edge, of `(pos, seen)` where `pos` is the
        # index in this list where the other endpoint of that edge is
        # located, and `seen` is a flag indicating whether this side of
        # the edge has already been walked through.
        pass2 = []
        # build indices to the where each vertex begins in the linear list
        vi=[0]
        for vertex in self.vertices:
            vi.append(vi[-1]+len(vertex))
        # build list from collapsing the 2-level structure
        for vertex in pass1:
            for pair in vertex:
                pass2.append([vi[pair[0]]+pair[1],False])

        # pass3: pick up each element of the linear list, and follow it
        # until we come to an already marked one.
        result = 0
        pos = 0
        while pos < len(pass2):
            # fast forward to an element that we've not yet seen
            while (pos < len(pass2)) and (pass2[pos][1] == True):
                pos += 1
            if pos >= len(pass2):
                break
            # walk whole chain of edges
            i = pos
            while pass2[i][1] == False:
                pass2[i][1] = True
                i = pass2[i][0]
            result += 1
            pos += 1

        # save result for later reference
        self._num_boundary_components = result
        
        # that's all, folks!
        return result

    def genus(self):
        """Return the genus g of this `Graph` object."""
        # compute value if not already done
        if (self._genus is None):
            n = self.num_boundary_components()
            K = self.num_vertices()
            L = self.num_edges()
            # by Euler, K-L+n=2-2*g
            self._genus = (L - K - n + 2) / 2
        return self._genus
    
    def classify(self):
        """Return the pair (g,n) for this `Graph` object."""
        return (self.genus(), self.num_boundary_components())



def all_graphs(vertex_valences):
    """Return all graphs having vertices of the given valences.

    Examples::
      >>> all_graphs([4])
      [[[2, 1, 2, 1]],
       [[2, 2, 1, 1]]]
      >>> all_graphs([3,3])
      [[[3, 1, 2], [3, 1, 2]],
       [[3, 2, 1], [3, 1, 2]],
       [[3, 2, 2], [3, 1, 1]]]
    """
    assert is_sequence_of_integers(vertex_valences), \
           "all_graphs: parameter `vertex_valences` must be a sequence of integers, "\
           "but got %s" % vertex_valences

    total_edges = sum(vertex_valences) / 2

    ## pass 1: gather all canonical graphs built from edge sequences
    graphs = list(all_canonical_decorated_graphs(vertex_valences, total_edges))

    ## pass 2: filter out sequences representing isomorphic graphs
    pos = 0
    while pos < len(graphs):
        current = graphs[pos]
        # slight optimization: since `current` is constant in the loop below,
        # pre-compute as much as we can...
        #current_cy = current.vertices
        #current_b_rp = [repetition_pattern(v_cy) for v_cy in current_cy]

        pos2 = pos+1
        while pos2 < len(graphs):
            candidate = graphs[pos2]
            candidate_is_isomorhic_to_current = False
            if candidate == current:
                candidate_is_isomorhic_to_current = True
            else:
                perm = Map(total_edges)
                # FIXME: could save some processing time by caching
                # the cyclic list of vertices) for any `candidate`, at
                # the expense of memory usage...
                for v1,v2 in izip(current.vertices, candidate.vertices):
                    (b1, rp1) = v1.repetition_pattern()
                    (b2, rp2) = v2.repetition_pattern()
                    rp_shift = rp1.shift_for_list_eq(rp2)
                    if rp_shift is None:
                        # cannot map vertices, quit looping on vertices
                        break
                    # rp1 is a kind of "derivative" of v1; we gather the
                    # displacement for v1 by summing elements of rp1 up to
                    # -but not including- `rp_shift`.
                    shift = sum(rp1[:rp_shift])
                    if not perm.extend(v1[b1+shift:b1+shift+len(v1)],v2[b2:b2+len(v2)]):
                        # continue with next candidate
                        perm = None
                        break
                if perm and perm.completed():
                    # the two graphs are isomorphic
                    candidate_is_isomorhic_to_current = True
            if candidate_is_isomorhic_to_current:
                # delete candidate; do *not* advance `pos2`, as the
                # list would be shifted up because of the deletion in
                # the middle.
                del graphs[pos2]
            else:
                # advance to next candidate
                pos2 += 1
        pos += 1
    return graphs


def all_edge_seq(n):
    """Iterate over lists representing edges of a ribbon graph.

    Each returned list has length `2*n` and comprises the symbols `{1,...,n}`,
    each of which is repeated exactly twice.
    """
    for s in permutations(2*n):
        tr_inplace(s, range(n+1,2*n+1), range(1,n+1))
        yield s


def all_canonical_decorated_graphs(vertex_valences, total_edges):
    """Iterate over all canonical decorated graphs with `total_edges` edges."""
    for edge_seq in all_edge_seq(total_edges):
        g = Graph(vertex_valences, edge_seq)
        if g.is_canonical():
            yield g
            


def all_automorphisms(graph):
    """Enumerate all automorphisms of `graph`.

    An automorhism is represented as a pair of ordered lists `(dests,
    rots)`: the i-th vertex of `graph` is to be mapped to the vertex
    `dests[i]`, and rotated by `rots[i]`.
    """
    # build enpoints vector for the final check that a constructed map
    # is an automorphism
    ev = []
    for l in range(1,num_edges(graph)+1):
        ev.append(endpoints(l, graph))
    ev.sort()
    
    # gather valences and repetition pattern at
    # start for speedup
    valence = [len(vertex) for vertex in graph]
    rp = [repetition_pattern(vertex) for vertex in graph]

    ## pass 1: for each vertex, list all destinations it could be mapped to,
    ##         in the form (dest. vertex, rotation).
    candidates = [ [] ] * len(graph)
    # FIXME: if vertex i can be mapped into vertex j, with some rotation delta,
    # then vertex j can be mapped into vertex i with rotation -delta,
    # so rearrange this to only do computations for i>j and use the values already
    # available in the other case...
    for i in range(len(graph)):
        for j in range(len(graph)):
            # if valences don't match, skip to next vertex in list
            if valence[i] != valence[j]:
                continue
            # if repetition patterns don't match, skip to next vertex in list
            if not (rp[i] == rp[j]):
                continue
            # append `(destination vertex, rotation shift)` to
            # candidate destinations list
            for delta in rp[i].all_shifts_for_list_eq(rp[j]):
                candidates[i].append((j,delta))

    ## pass 2: for each vertex, pick a destination and return the resulting
    ##         automorphism. (FIXME: do we need to check that the adjacency 
    ##         matrix stays the same?)
    for a in enumerate_set_product(candidates):
        # check that map does not map two distinct vertices to the same one
        already_assigned = []
        a_is_no_real_map = False
        def first(seq):
            return seq[0]
        for dest in a:
            v = first(dest)
            if v in already_assigned:
                a_is_no_real_map = True
            else:
                already_assigned.append(v)
        if a_is_no_real_map:
            # try with next map
            continue
        # check that the endpoints vector stays the same
        vertex_permutation = map(first, a)
        new_ev = [(vertex_permutation[e[0]], vertex_permutation[e[1]]) for e in ev]
        new_ev.sort()
        if 0 != deep_cmp(ev, new_ev):
            # this is no automorphism, skip to next one
            continue
        # return automorphism in (vertex_perm_list, rot_list) form
        def second(seq):
            return seq[1]
        yield (map(first, a), map(second, a))


def is_orientation_reversing(graph, automorphism):
    """Return `True` if `automorphism` reverses orientation of `graph`."""
    def sign_of_rotation(l,r=1):
        """Return the sign of a rotation of `l` elements, applied `r` times."""
        # evaluating a conditional is faster than computing (-1)**...
        if 0 == ((l-1)*r) % 2:
            return 1
        else:
            return -1
    def sign_of_permutation(p):
        """Recursively compute the sign of permutation `p`.

        A permutation is represented as a linear list: `p` maps
        `i` to `p[i]`.

        Examples:
        >>> sign_of_permutation([1,2,3])
        1
        >>> sign_of_permutation([1,3,2])
        -1
        >>> sign_of_permutation([3,1,2])
        1
        >>> sign_of_permutation([1])
        1
        >>> sign_of_permutation([])
        1
        """
        l = len(p)
        if 1 >= l:
            return 1
        # find highest-numbered element
        k = p.index(l)
        # remove highest-numbered element for recursion
        q = p[:]
        del q[k]
        # recursively compute
        if 0 == ((l+k) % 2):
            s = -1
        else:
            s = 1
        return s * sign_of_permutation(q)
    return reduce(operator.mul,
                  map(sign_of_rotation,
                      map(len, graph), automorphism[1]),
                  sign_of_permutation(automorphism[0]))
                                         

def has_orientation_reversing_automorphism(graph):
    """Return `True` if `graph` has an orientation-reversing automorphism.
    
    Enumerate all automorphisms of `graph`, end exits with `True`
    result as soon as one orientation-reversing one is found.
    """
    for a in all_automorphisms(graph):
        if is_orientation_reversing(a):
            return True
    return False


class Map:
    """A mapping (in the mathematical sense) with a domain of fixed cardinality.

    Provides methods to incrementally construct the mapping by
    extending an existing map with new source->destination pairs.  The
    cardinality of the domain should be known in advance, and the
    `Map` object is *complete* when all items in the domain have been
    assigned a destination value.
    """
    def __init__(self, order):
        self.order = order
        self.map = {}
    def __call__(self, src):
        return self.map[src]
    def extend(self, srcs, dsts):
        """Return `True` if the Map can be extended by mapping
        elements of `srcs` to corresponding elements of `dsts`.
        Return `False` if any of the new mappings conflicts with an
        already established one.
        """
        for i in range(0,len(srcs)):
            if self.map.has_key(srcs[i]):
                if self.map[srcs[i]] != dsts[i]:
                    return False
                else:
                    pass
            else:
                self.map[srcs[i]] = dsts[i]
        return True
    def extend_with_hash(self, mappings):
        """Return `True` if the Map can be extended by mapping each
        key of `mappings` tothe corresponding value.  Return `False`
        if any of the new mappings conflicts with an already
        established one.
        """
        for src in mappings.keys():
            if self.map.has_key(src):
                if self.map[src] != mappings[src]:
                    return False
                else:
                    pass
            else:
                self.map[src] = mappings[src]
        return True
    def completed(self):
        return self.order == len(self.map.keys())
    def is_assigned(self, src):
        return self.map.has_key(src)



## main: run tests

if "__main__" == __name__:
    import doctest
    doctest.testmod(optionflags=doctest.NORMALIZE_WHITESPACE)
