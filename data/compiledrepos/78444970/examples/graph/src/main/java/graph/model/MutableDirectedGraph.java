package graph.model;

import com.google.common.collect.HashBasedTable;
import com.google.common.collect.Table;

import java.util.LinkedHashSet;
import java.util.Set;
import java.util.function.BiFunction;

public class MutableDirectedGraph<NODE> implements DirectedGraph<NODE> {
    private final Set<NODE> nodes = new LinkedHashSet<>();
    private final Set<Edge<NODE>> edges = new LinkedHashSet<>();
    private final Table<NODE, NODE, Edge<NODE>> incidence = HashBasedTable.create();

    public NODE addNode(final NODE node) {
        nodes.add(node);
        return node;
    }

    public Edge<NODE> addEdge(final NODE source, final NODE target) {
        addNode(source);
        addNode(target);
        final Edge<NODE> newEdge = new Edge<>(source, target);
        edges.add(newEdge);
        incidence.put(source, target, newEdge);
        return newEdge;
    }

    @Override
    public Set<NODE> nodes() {
        return nodes;
    }

    @Override
    public Set<Edge<NODE>> edges() {
        return edges;
    }

    @Override
    public BiFunction<NODE, NODE, Edge<NODE>> incidence() {
        return incidence::get;
    }
}
