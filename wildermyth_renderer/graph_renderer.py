# -*- encoding: utf-8 -*-

from __future__ import annotations

import logging
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Optional
from typing import Set
from typing import TYPE_CHECKING

import graphviz
from PIL import Image

from wildermyth_renderer.character_data import CharacterClass
from wildermyth_renderer.character_data import CharacterGender

if TYPE_CHECKING:
    from wildermyth_renderer.params import RendererParams
    from wildermyth_renderer.relationship_chart import RelationshipChart
    from wildermyth_renderer.relationship_chart import CharacterNode

log = logging.getLogger(__name__)

GRAPH_ATTRS = {
    'rankdir': 'TB',
    'overlap': 'false',
    'outputorder': 'nodesfirst',
}

NODE_SHAPES = {
    CharacterGender.MALE: 'box',
    CharacterGender.FEMALE: 'ellipse',
    CharacterGender.NONBINARY: 'diamond',
    CharacterGender.UNKNOWN: 'diamond',
}

NODE_COLORS = {
    CharacterClass.WARRIOR: 'darkred',
    CharacterClass.HUNTER: 'darkgreen',
    CharacterClass.MYSTIC: 'blue',
    CharacterClass.UNKNOWN: 'black',
}

PHANTOM_NODE_ATTRS = {
    'style': 'dotted',
}

INVISIBLE_NODE_ATTRS = {
    'shape': 'point',
    'label': '',
    'height': '.01',
    'width': '.01',
}

PARENT_EDGE_ATTRS = {
    'dir': 'none',
    'tailport': 's',
    'headport': 'n',
    'weight': '5',
}

CHILD_EGDE_ATTRS = {
    'dir': 'forward',
    'tailport': 's',
    'headport': 'n',
    'weight': '5',
}

RELATIONSHIP_EDGES = {
    'locked_lover': {
        'legend': 'soulmates',
        'attrs': {
            'dir': 'both',
            'arrowhead': 'inv',
            'arrowtail': 'inv',
            'color': 'red',
        },
    },
    'locked_rival': {
        'legend': 'rivals',
        'attrs': {
            'dir': 'both',
            'arrowhead': 'open',
            'arrowtail': 'open',
            'color': 'blue',
        },
    },
    'past_lover': {
        'legend': 'past lovers',
        'attrs': {
            'dir': 'none',
            'arrowhead': 'none',
            'arrowtail': 'none',
            'style': 'dashed',
            'color': 'red',
        },
    },
    'past_rival': {
        'legend': 'past rivals',
        'attrs': {
            'dir': 'none',
            'arrowhead': 'none',
            'arrowtail': 'none',
            'style': 'dashed',
            'color': 'blue',
        },
    },
    'past_friend': {
        'legend': 'past friends',
        'attrs': {
            'dir': 'none',
            'arrowhead': 'none',
            'arrowtail': 'none',
            'style': 'dashed',
            'color': 'green',
        },
    },
    'unknown_locked': {
        'legend': 'other locked',
        'attrs': {
            'dir': 'both',
            'arrowhead': 'halfopen',
            'arrowtail': 'halfopen',
        },
    },
    'unknown_past': {
        'legend': 'other past',
        'attrs': {
            'dir': 'none',
            'arrowhead': 'none',
            'arrowtail': 'none',
            'style': 'dashed',
        },
    },
}


class GraphRenderer:
    """
    Class that handles graph rendering and graphviz interaction
    """

    def __init__(self, params: RendererParams, relationship_chart: Optional[RelationshipChart] = None) -> None:
        self.params = params

        self.node_graph = graphviz.Digraph(name='Nodes')
        self.family_graph = graphviz.Digraph(name='Family')
        self.relationship_graph = graphviz.Digraph(name='Relationships', edge_attr={'constraint': 'false'})

        self.nodes_in_graph = set()
        self.edge_types_in_graph = set()

        self.children_nodes = defaultdict(set)

        if relationship_chart is not None:
            self.add_from_chart(relationship_chart)

    def add_from_chart(self, relationship_chart: RelationshipChart) -> None:
        """
        Adds all nodes from a chart to graph
        """
        for node in relationship_chart:
            self.add_node(node)

    def add_node(self, node: CharacterNode) -> None:
        """
        Adds a single character node to graph
        """

        label = node.label
        attrs = {}

        if not self.params.gender_shapes or node.character_data is None:
            gender = CharacterGender.UNKNOWN
        else:
            gender = node.character_data.gender
        if gender in NODE_SHAPES:
            attrs['shape'] = NODE_SHAPES[gender]

        if not self.params.class_colors or node.character_data is None:
            character_class = CharacterClass.UNKNOWN
        else:
            character_class = node.character_data.character_class
        if character_class in NODE_COLORS:
            attrs['color'] = NODE_COLORS[character_class]
            attrs['fontcolor'] = NODE_COLORS[character_class]

        if node.is_phantom:
            if self.params.hide_phantoms:
                return

            attrs.update(PHANTOM_NODE_ATTRS)
            label = f"<<i>{label}</i>>"

        self.node_graph.node(node.id, label, **attrs)
        self.nodes_in_graph.add(node.id)

        if node.parent_ids:
            children_node_id = self._make_children_node_id(node.parent_ids)
            if children_node_id not in self.nodes_in_graph:
                self.family_graph.node(children_node_id, **INVISIBLE_NODE_ATTRS)
                self.nodes_in_graph.add(children_node_id)
                for parent_id in node.parent_ids:
                    self.children_nodes[parent_id].add(children_node_id)
                    if parent_id in self.nodes_in_graph:
                        self.family_graph.edge(parent_id, children_node_id, **PARENT_EDGE_ATTRS)
            self.family_graph.edge(children_node_id, node.id, **CHILD_EGDE_ATTRS)

        for children_node_id in self.children_nodes[node.id]:
            self.family_graph.edge(node.id, children_node_id, **PARENT_EDGE_ATTRS)

        for (rel_status, rel_type), rel_target_ids in node.relationships.items():
            if not rel_target_ids:
                continue

            edge_key = f"{rel_status.name.lower()}_{rel_type}"
            if edge_key not in RELATIONSHIP_EDGES:
                edge_key = f"unknown_{rel_status.name.lower()}"
            edge_params = RELATIONSHIP_EDGES.get(edge_key, {})
            edge_attrs = edge_params.get('attrs', {})
            self.edge_types_in_graph.add(edge_key)

            for rel_target_id in rel_target_ids:
                if rel_target_id in self.nodes_in_graph:
                    self.relationship_graph.edge(node.id, rel_target_id, label='<&nbsp;&nbsp;>', **edge_attrs)

    def make_legend_graph(self) -> Optional[graphviz.Digraph]:
        """
        Creates a graphviz.Digraph to represent legend for all relationship arrows present in the graph
        :return: created legend digraph or None if no relationships are present
        """

        if not self.edge_types_in_graph:
            return None

        legend_graph = graphviz.Digraph(
            name=f"{self.params.graph_name}_legend",
            format='png',
            directory=self.params.get_render_dir(),
        )
        legend_graph.attr(rankdir='LR')

        key_first_line = '<<table border="0" cellpadding="2" cellspacing="0" cellborder="0">'
        key_line_template = '<tr><td align="right" port="i{port_idx}">{content}</td></tr>'
        key_last_line = '</table>>'

        startkey_lines = [key_first_line]
        endkey_lines = [key_first_line]
        edges = []
        for idx, egde_type in enumerate(sorted(self.edge_types_in_graph)):
            edge_params = RELATIONSHIP_EDGES.get(egde_type, {})
            if edge_params.get('legend') is None:
                continue
            startkey_lines.append(key_line_template.format(port_idx=idx + 1, content=edge_params['legend']))
            endkey_lines.append(key_line_template.format(port_idx=idx + 1, content='&nbsp;'))

            edge_attrs = edge_params.get('attrs', {}).copy()
            edge_attrs.update({
                'tailport': f"i{idx + 1}:e",
                'headport': f"i{idx + 1}:w",
            })
            edges.append(edge_attrs)

        startkey_lines.append(key_last_line)
        endkey_lines.append(key_last_line)

        with legend_graph.subgraph(name='cluster_Legend') as s:
            # make a cluster for no other reason than to have a neat border around it
            s.attr(label='<<b>Legend</b>>', style='bold')
            s.attr('node', shape='plaintext')

            s.node('startkey', label=''.join(startkey_lines))
            s.node('endkey', label=''.join(endkey_lines))
            for edge_attrs in edges:
                s.edge('startkey', 'endkey', **edge_attrs)

        return legend_graph

    def make_main_graph(self) -> graphviz.Digraph:
        """
        Creates a graphviz.Digraph with all the nodes and relationships added to the graph
        :return: created digraph
        """
        graph_attrs = GRAPH_ATTRS.copy()
        if self.params.pack_graph:
            graph_attrs.update({
                'pack': 'true',
                'packmode': 'graph' if self.params.pack_by_subgraphs else 'node',
            })

        graph = graphviz.Digraph(
            name=self.params.graph_name,
            format='png',
            directory=self.params.get_render_dir(),
            graph_attr=graph_attrs,
        )

        # order of these parts sometimes seems to affect node placement, so this is left as an option
        subgraphs = [self.family_graph, self.relationship_graph]
        if self.params.prioritize_relationships:
            subgraphs.append(self.node_graph)
        else:
            subgraphs.insert(0, self.node_graph)

        for subgraph in subgraphs:
            graph.subgraph(subgraph)

        return graph

    def render(self) -> None:
        """
        Renders the full graph (including legend if required) and saves in to output_path specified in renderer params
        """
        tmp_files = []

        main_graph = self.make_main_graph()
        tmp_files.append(Path(main_graph.filepath))

        if self.params.norender:
            main_graph.save()
            render_path = None
        else:
            main_graph.render()
            render_path = Path(f"{main_graph.filepath}.png")
            tmp_files.append(render_path)

        if self.params.include_legend and self.edge_types_in_graph:
            # after many hours of trying to make it work consistently with legend included as a subgraph
            # and encountering the weirdest assortment of graphviz bugs and quirks in the process,
            # I can say with certainty that simply rendering the two separately and stacking the images afterwards
            # is the sanest possible approach

            legend_graph = self.make_legend_graph()
            tmp_files.append(Path(legend_graph.filepath))

            if self.params.norender:
                legend_graph.save()
                legend_render_path = None
            else:
                legend_graph.render()
                legend_render_path = Path(f"{legend_graph.filepath}.png")
                tmp_files.append(legend_render_path)

                main_image = Image.open(render_path)
                legend_image = Image.open(legend_render_path)
                combined_image = Image.new(
                    'RGB',
                    (max(main_image.width, legend_image.width), main_image.height + legend_image.height),
                    color='white',
                )
                combined_image.paste(main_image, (0, 0))
                combined_image.paste(legend_image, (0, main_image.height))

                render_path = self.params.get_render_dir() / f"{main_graph.name}_with_legend.png"
                combined_image.save(render_path)

                tmp_files.append(render_path)

        if render_path is not None:
            if not self.params.output_path.suffix.lower() == '.png':
                output_path = self.params.output_path.with_suffix(f"{self.params.output_path.suffix}.png")
            else:
                output_path = self.params.output_path
            shutil.copyfile(render_path, output_path)

        if self.params.clean_tmp_files:
            for tmp_file in tmp_files:
                if tmp_file is not None and tmp_file != self.params.output_path:
                    tmp_file.unlink(missing_ok=True)

    @classmethod
    def _make_children_node_id(cls, parent_ids: Set[str]) -> str:
        return f"children_{'_'.join(sorted(parent_ids))}"
