#! /usr/bin/env python
"""Command-line front-end for `rg.py`.
"""
__docformat__ = 'reStructuredText'


## stdlib imports

import gc
import sys
import logging

## application-local imports

from utils import positive_int


## utility functions

def graph_to_xypic(graph, g=None, n=None, orientable=None):
    """Print XY-Pic code snippet to render graph `graph`."""

    # provide default values for arguments
    if g is None:
        g = graph.genus()
    if n is None:
        n = graph.num_boundary_components()
    if orientable is None:
        orientable = graph.is_oriented()

    # header
    result = r"\begin{flushleft}" +'\n'
    
    def vertex_label(v):
        #return '[' + str.join("", map(str, v)) + ']'
        # vertices are labeled with lowercase latin letters
        return chr(97 + v)
##     label = map(vertex_label, graph)
    K = graph.num_vertices
    result += r'\xy 0;<2cm,0cm>:%'+'\n'

    # put graph vertices on a regular polygon
    if K < 3:
        result += '(2,0)="v1",%\n(0,0)="v2",%\n'
    else:
        result += r'{\xypolygon%d"v"{~={0}~>{}}},%% mark vertices' \
                  % (max(K,3)) \
                  + '\n'

    # mark invisible "control points" for bezier curves connecting vertices
    def rotation_angle(K,k):
        return 90+(k-1)*360/K
    for k in range(1,K+1):
        result += r'"v%d",{\xypolygon%d"v%dl"{~:{(1.20,0):}~={%d}~>{}}},' \
                  % (k, 2*len(graph[k-1])-2, k, rotation_angle(K,k)) \
                  + '%\n'

    for l in xrange(graph.num_edges):
        (v1, v2) = graph.endpoints_v[l]
        (i1, i2) = graph.endpoints_i[l]
        if v1 != v2:
            result += r'"v%d"*+\txt{%s};"v%d"*+\txt{%s}**\crv{"v%dl%d"&"v%dl%d"}?(.6)+/2em/*\txt{\bf %d},%%?(.3)*\dir{>},' \
                      % (v1+1, vertex_label(v1),
                         v2+1, vertex_label(v2),
                         v1+1, 1+graph.vertices[v1].index(l),
                         v2+1, 1+graph[v2].index(l), graph.edge_numbering[l]) \
                      + '%\n'
        else:
            h = graph.vertices[v1].index(l)
            result += r'"v%d"*+\txt{%s};"v%d"*+\txt{%s}**\crv{"v%dl%d"&"v%dl%d"}?(.6)+/2em/*\txt{\bf %d},%%?(.3)*\dir{>},' \
                      % (v1+1, vertex_label(v1),
                         v2+1, vertex_label(v2),
                         v1+1, h+1, v2+1, 1+graph.vertices[v1].index(l,h+1),
                         graph.edge_numbering[l]) \
                      + '%\n'

    # cross-out graph, if not orientable
    if orientable is False:
        # 0,(-1.20,+1.20);(+1.20,-1.20)**[red][|(10)]@{-},%
        result += r"0,(0,+1.20);(+2.40,-1.20)**[red][|(10)]@{-}," + '%\n'
        result += r"0,(0,-1.20);(+2.40,+1.20)**[red][|(10)]@{-}," + '%\n'
    result += r'\endxy'

    result += r"\end{flushleft}" + '\n'

    return result


## actions

def do_graphs(g,n):
    """Compute Fatgraphs occurring in `M_{g,n}`.

    Return a pair `(graphs, D)`, where `graphs` is the list of
    `(g,n)`-graphs, and `D` is a list, the `k`-th element of which is
    the list of differentials of graphs with `k` edges.
    """
    logging.debug("Computing fat graphs for g=%d, n=%d ...", g, n)
    graphs = FatgraphComplex(g,n)
    logging.debug("Found %d distinct orientable fat graphs.", len(graphs))
    
    # FIXME: `D` must match the one used in `ChainComplex.compute_homology_rank()`
    D = [ [ graphs.module[i-1].coordinates(graphs.differential[i](b))
            for b in graphs.module[i].base ]
          for i in xrange(1, graphs.length)
          ]

    return (graphs, D)

    
def do_homology(g, n):
    """Compute homology ranks of the graph complex of `M_{g,n}`.

    Return array of homology ranks.
    """
    logging.debug("Computing fat graphs complex for g=%d, n=%d ...", g, n)
    graph_complex = FatgraphComplex(g,n)

    logging.debug("Computing homology ranks ...")
    hs = graph_complex.compute_homology_ranks()

    return hs


def do_valences(g,n):
    """Compute vertex valences occurring in g,n Fatgraphs.

    Return list of valences.
    """
    logging.debug("Computing vertex valences occurring in g=%d,n=%d fatgraphs ...", g, n)
    return vertex_valences_for_given_g_and_n(g,n)



## main

# parse command-line options
from optparse import OptionParser
parser = OptionParser(version="3.4",
    usage="""Usage: %prog [options] action [arg ...]

Actions:

  valences G N
    Print the vertex valences occurring in M_{g,n} graphs

  graphs G N
    Print the graphs occurring in M_{g,n}

  homology G N
    Print homology ranks of M_{g,n}

  shell
    Start an interactive PyDB shell.
  
  selftest
    Run internal code tests and report failures.
    """)
parser.add_option("-C", "--cache",
                  action="count", dest="cache", default=0,
                  help="""Turn on internal result caching (trade speed for memory).  With '-C', cache graph attributes and equality testing results: this gives a good speedup with a reasonable memory increase.  With '-CC', cache also isomorphism groups: the speedup is larger, but the memory usage can be more than double.""")
parser.add_option("-l", "--logfile",
                  action='store', dest='logfile', default=None,
                  help="Redirect log messages to the named file (by default log messages are output to STDERR).")
parser.add_option("-n", "--silent",
                  action='store_true', dest='silent', default=False,
                  help="No output at all: only useful for timing the algorithm.")
parser.add_option("-L", "--latex",
                  action='store_true', dest='latex', default=False,
                  help="Output list of M_{g,n} graphs as a LaTeX file.")
parser.add_option("-o", "--output", dest="outfile", default=None,
                  help="Output file for all actions.")
parser.add_option("-O", "--feature", dest="features", default=None,
                  help="""Enable optional speedup or tracing features:
                  * pydb -- run Python debugger if an error occurs
                  * psyco -- run the Psyco JIT compiler
                  * profile -- dump profiler statistics in a .pf file.
                  Different features may be combined by separating them with a comma, as in '-O pydb,profile'.""")
parser.add_option("-v", "--verbose",
                  action="store_false", dest="quiet", default=True,
                  help="Print informational and status messages as the computation goes on.")
(options, args) = parser.parse_args()

# print usage message if no args given
if 0 == len(args) or 'help' == args[0]:
    parser.print_help()
    sys.exit(1)

# configure logging
if options.logfile is None:
    log_output = sys.stderr
else:
    log_output = file(options.logfile, 'a')

if options.silent or options.quiet:
    log_level = logging.ERROR
else:
    log_level = logging.DEBUG

logging.basicConfig(level=log_level,
                    stream=log_output,
                    format="%(asctime)s [%(levelname)s] %(message)s",
                    datefmt="%H:%M:%S")
    
# enable optional features
if options.features is not None:
    features = options.features.split(",")
    if 'pydb' in features:
        try:
            import pydb
            sys.excepthook = pydb.exception_hook
            logging.debug("PyDB enabled: exceptions will start a debugging session.")
        except ImportError:
            logging.warning("Could not import 'pydb' module - PyDB not enabled.")
    if 'psyco' in features:
        try:
            import psyco
            psyco.full()
            logging.debug("Psyco enabled.")
        except ImportError:
            logging.warning("Could not import 'psyco' module - Psyco JIT accelerator not enabled.")
    if 'profile' in features:
        try:
            import hotshot
            pf = hotshot.Profile(__name__ + '.pf')
            pf.start()
            logging.debug("Started call profiling with 'hotshot' module.")
        except ImportError:
            logging.warning("Could not import 'hotshot' - call profiling *not* enabled.")


# configure caching

from cache import (
    ocache0,
    ocache_iterator,
    ocache_symmetric,
    ocache_weakref,
    )

if options.cache is not None:
    ocache0.enabled = True
    ocache_weakref.enabled = True
    ocache_symmetric.enabled = True
    # only enable iterator caching wih "-CC"
    if options.cache > 1:
        ocache_iterator.enabled = True
    # this reduces memory usage at the cost of some speed
    gc.enable()
    if options.cache < 3:
        gc.set_threshold(256, 4, 4)
else:
    # default: no caching at all
    ocache_iterator.enabled = False
    ocache_symmetric.enabled = False
    ocache_weakref.enabled = False

# fat-graph handling routines need to be loaded *after* the cache module
# (in order for caching to be a runtime-selectable option)
from graph_homology import FatgraphComplex
from rg import (
    Fatgraph,
    MgnGraphsIterator,
    )
from valences import vertex_valences_for_given_g_and_n



# hack to allow 'N1,N2,...' or 'N1 N2 ...' syntaxes
for (i, arg) in enumerate(args):
    if arg.find(","):
        args[i:i+1] = arg.split(",")

# open output file
if options.outfile is None:
    outfile = sys.stdout
else:
    outfile = open(options.outfile, 'w')

# shell -- start interactive debugging shell
if 'shell' == args[0]:
    try:
        import pydb
    except ImportError:
        logging.warning("Could not import 'pydb' module - Aborting.")
        sys.exit(1)
        
    print ("""Starting interactive session (with PyDB %s).
    
    Any Python expression may be evaluated at the prompt.
    All symbols from modules `rg`, `homology`, `graph_homology`
    have already been imported into the main namespace.
    
    """ % pydb.version)
    pydb.debugger([
        "from homology import *",
        "from graph_homology import *",
        "from rg import *",
        ])
        
# selftest -- run doctests and acceptance tests on simple cases
elif 'selftest' == args[0]:
    import doctest
    import imp
    for module in [ 'rg',
                    'homology',
                    'graph_homology',
                    'combinatorics',
                    'iterators',
                    'cyclicseq',
                    ]:
        try:
            file, pathname, description = imp.find_module(module)
            m = imp.load_module(module, file, pathname, description)
            logging.debug("Running Python doctest on '%s' module..." % module)
            # temporarily turn off logging to avoid cluttering the output
            logging.getLogger().setLevel(logging.ERROR)
            # run doctests
            (failed, tested) = doctest.testmod(m, name=module, optionflags=doctest.NORMALIZE_WHITESPACE)
            # restore normal logging level
            logging.getLogger().setLevel(log_level)
            if failed>0:
                logging.error("  module '%s' FAILED %d tests out of %d." % (module, failed, tested))
                print("Module '%s' FAILED %d tests out of %d." % (module, failed, tested))
            else:
                if tested>0:
                    logging.debug("  OK - module '%s' passed all doctests." % module)
                    print("Module '%s' OK, passed all doctests." % module)
                else:
                    logging.warning("  module '%s' had no doctests." % module)
        finally:
            file.close()

    # second, try known cases and inspect results
    for (g, n, ok) in [ (0,3, [0,0,1]),
                        (1,1, [0,0,1]),
                        (1,2, [0,0,0,0,0,1]),
                        (0,4, [0,0,0,0,2,1]),
                        (2,1, [0,0,0,0,0,0,1,0,1])
                        ]:
        sys.stdout.write("Computation of M_{%d,%d} homology: " % (g,n))
        # compute homology of M_{g,n}
        hs = do_homology(g,n)
        # check result
        if hs == ok:
            print("OK")
        else:
            logging.error("Computation of M_{%d,%d} homology: FAILED, got %s expected %s"
                          % (g,n,hs,ok))
            print("FAILED, got %s expected %s" % (g,n,hs,ok))

    # third, count graphs produced in known good cases
    for (g, n, ok) in [ (0,5, 290),
                        ]:
        sys.stdout.write("Computation of M_{%d,%d} graphs: " % (g,n))
        # compute number of graphs in M_{g,n}
        qty = len(list(MgnGraphsIterator(g,n)))
        # check result
        if qty == ok:
            print("OK")
        else:
            logging.error("Computation of M_{%d,%d} graphs: FAILED, got %s expected %s"
                          % (g,n,qty,ok))
            print("FAILED, got %s expected %s" % (g,n,qty,ok))
        
        

# valences -- show vertex valences for given g,n
elif 'valences' == args[0]:
    del args[0]
    if len(args) < 2:
        parser.print_help()
        sys.exit(1)
    try:
        g = int(args[0])
        if g < 0:
            raise ValueError
    except ValueError:
        sys.stderr.write("Bad value '%s' for argument G: " \
                         "should be positive integer.\n" \
                         % (args[0],))
        sys.exit(1)
    try:
        n = positive_int(args[1])
    except ValueError, msg:
        sys.stderr.write("Bad value '%s' for argument N: " \
                         "should be non-negative integer.\n" \
                         % (args[1],))
        sys.exit(1)

    logging.debug("Computing vertex valences occurring in g=%d,n=%d fatgraphs ...", g, n)
    vvs = do_valences(g,n)
    if not options.silent:
        for vv in vvs:
            outfile.write("%s\n" % str(vv))

# graphs -- list graphs from given g,n
elif "graphs" == args[0]:
    # parse command line
    del args[0]
    if len(args) < 2:
        parser.print_help()
        sys.exit(1)

    try:
        g = int(args[0])
        if g < 0:
            raise ValueError
    except ValueError:
        sys.stderr.write("Bad value '%s' for argument G: " \
                         "should be positive integer.\n" \
                         % (args[0],))
        sys.exit(1)
    try:
        n = positive_int(args[1])
    except ValueError, msg:
        sys.stderr.write("Bad value '%s' for argument N: " \
                         "should be non-negative integer.\n" \
                         % (args[1],))
        sys.exit(1)

    graphs, D = do_graphs(g,n)

    # output results
    if not options.silent:
        if options.latex:
            outfile.write(r"""
    \documentclass[a4paper,twocolumn]{article}
    \usepackage{amsmath}
    \usepackage[color,curve,line,poly,xdvi]{xy}
    \begin{document}
    \section*{Fatgraphs labeling cells of $M_{%(genus)d,%(bc)d}$}

    The graph $G_{l,k}$ is the $k$-th graph in the
    set of graphs of genus $%(genus)d$ with $l$ edges and $%(bc)d$
    boundary cycles.

    The crossed-out graphs are those having an automorphism that
    reverses the associated cell orientation.
    
    """ % {'genus':g, 'bc':n})
        tot = 0
        for num_of_edges in xrange(1, len(graphs)):
            if options.latex and graphs.module[num_of_edges].dimension > 0:
                outfile.write(r"""
                \subsection*{Fatgraphs with $%d$ edges}
                
                """ % (num_of_edges+1))
            for (num, graph) in enumerate(graphs.module[num_of_edges]):
                tot += 1
                if options.latex:
                    outfile.write((r"\subsection*{$G_{%d,%d}$}" % (num_of_edges,num)) + '\n')

                    # draw graph
                    outfile.write(graph_to_xypic(graph,
                                                 graph.genus(),
                                                 graph.num_boundary_components(),
                                                 graph.is_oriented(),
                                                 )+'\n')

                    # print differential
                    outfile.write(r"\subsubsection*{Differential}" + '\n')
                    outfile.write(r"""
\begin{equation*}
  dG_{%d,%d} =
                    """ % (num_of_edges, num))
                    cnt = 0
                    for (num2, coeff) in enumerate(D[num_of_edges - 1][num]):
                        if coeff == 0:
                            continue # with next graph
                        elif coeff == +1:
                            coeff = "+"
                        elif coeff == -1:
                            coeff = "-"
                        else:
                            coeff = "%+d" % coeff
                        outfile.write(" %sG_{%d,%d}" % (coeff, num_of_edges-1, num2))
                        cnt += 1
                    if cnt == 0:
                        outfile.write("0")
                    outfile.write(r"""
\end{equation*}
                    """)

                    # print boundary cycles
                    if graph.numbering is not None:
                        outfile.write(r"\subsubsection*{Boundary cycles}" + '\n')
                        outfile.write(r"\begin{tabular}{rl}" + '\n')
                        def fmt_(nr):
                            if isinstance(nr, (set, frozenset)):
                                return str.join(",", [str(elt) for elt in nr])
                            else:
                                return str(nr)
                        def cmp_(x,y):
                            x = x[1]
                            y = y[1]
                            if isinstance(x, (set, frozenset)):
                                x = min(x)
                            if isinstance(y, (set, frozenset)):
                                y = min(y)
                            return cmp(x,y) 
                        for (bcy, nr) in sorted(graph.numbering.iteritems(), cmp=cmp_):
                            outfile.write(r"\textsl{%s} & (%s) \\ " % (
                                fmt_(nr),
                                str.join(",", [str(graph.edge_numbering[edge])
                                               for edge in bcy]),
                                )
                                + '\n')
                        outfile.write(r"\end{tabular}" + '\n\n')

                    # print python repr
                    outfile.write(r"\subsubsection*{Python representation}" + '\n')
                    outfile.write(r"{\small " + repr(graph) + "}") 
                    outfile.write('\n\n')

                    outfile.write(r"\vspace{1ex}\hrulefill\vspace{1ex}" + '\n')
                else:
                    outfile.write("%s\n" % ((graph,
                                             graph.genus(),
                                             graph.num_boundary_components(),
                                             graph.is_oriented(),
                                             ),))
        outfile.write("\n")
        outfile.write("Found %d graphs total.\n" % tot)
        outfile.write("\n")
        if options.latex:
            outfile.write(r"\end{document}")
            outfile.write("\n")


# vertices -- list graphs for given vertex valences
elif 'vertices' == args[0]:
    # parse command line
    del args[0]
    if len(args) == 0:
        parser.print_help()
        sys.exit(1)

    try:
        valences = [ positive_int(val) for val in args ]
    except ValueError, msg:
        sys.stderr.write("Invalid command line:"\
                         " all vertex valences must be positive integers: %s\n" \
                         % msg)
        sys.exit(1)
    if sum(valences) % 2 != 0:
        sys.stderr.write("Invalid valence list '%s': " \
                         "sum of vertex valences must be an even number. " \
                         "Aborting.\n" \
                         % (" ".join(str(val) for val in valences)))
        sys.exit(1)

    # compute graphs matching given vertex sequences
    graphs = do_vertices(valences)

    # output results
    if not options.silent:
        if options.latex:
            outfile.write(r"""
    \documentclass[a4paper,twocolumn]{article}
    \usepackage[curve,poly,xdvi]{xy}
    \begin{document}
    \section*{Fatgraphs labeling cells of $M_{%d,%d}$}
    """ % (g,n))
        for graph in graphs:
            if options.latex:
                outfile.write(graph_to_xypic(graph,
                                             graph.genus(),
                                             graph.num_boundary_components(),
                                             graph.is_oriented(),
                                             name=r"\#%d" % num,
                                             )+'\n')
            else:
                outfile.write("%s\n" % ((graph,
                                         graph.genus(),
                                         graph.num_boundary_components(),
                                         graph.is_oriented(),
                                         ),))
        outfile.write("\n")
        outfile.write("Found %d graphs.\n" % len(graphs))
        outfile.write("\n")
        if options.latex:
            outfile.write(r"\end{document}")
            outfile.write("\n")

# homology -- compute homology ranks
elif 'homology' == args[0]:
    # parse command line
    del args[0]
    if len(args) == 0:
        parser.print_help()
        sys.exit(1)

    try:
        g = int(args[0])
        if g < 0:
            raise ValueError
    except ValueError:
        sys.stderr.write("Bad value '%s' for argument G: " \
                         "should be positive integer.\n" \
                         % (args[0],))
        sys.exit(1)
    try:
        n = positive_int(args[1])
    except ValueError, msg:
        sys.stderr.write("Bad value '%s' for argument N: " \
                         "should be non-negative integer.\n" \
                         % (args[1],))
        sys.exit(1)

    # compute graph complex and its homology ranks
    hs = do_homology(g, n)

    # print results
    if not options.silent:
        for (i, h) in enumerate(reversed(hs)):
            outfile.write("h_%d(M_{%d,%d}) = %d\n" % (i, g, n, h))

else:
    sys.stderr.write("Unknown action `%s`, aborting.\n" % args[0])
    sys.exit(1)

# try to print profiling information, but ignore failures
# (profiling might not have been requested, in the first place...)
try:
    pf.stop()
    logging.debug("Stopped call profiling, now dumping stats.")
    pf.close()
    import hotshot.stats
    stats = hotshot.stats.load(__name__ + '.pf')
    stats.strip_dirs()
    stats.sort_stats('cumulative', 'calls')
    stats.print_stats(50)
except:
    pass

logging.debug("Done.")
