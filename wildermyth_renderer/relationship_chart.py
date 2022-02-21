# -*- encoding: utf-8 -*-

from __future__ import annotations

import contextlib
import dataclasses
import logging
import re
import uuid
from collections import defaultdict
from copy import deepcopy
from typing import DefaultDict
from typing import Dict
from typing import Generator
from typing import Iterable
from typing import Iterator
from typing import List
from typing import Optional
from typing import Set
from typing import TYPE_CHECKING
from typing import Tuple
from typing import Type
from typing import TypeVar

from wildermyth_renderer.params import RelationshipStatus

if TYPE_CHECKING:
    from wildermyth_renderer.character_data import CharacterData
    from wildermyth_renderer.params import FilterParams

log = logging.getLogger(__name__)


@dataclasses.dataclass
class CharacterNode:
    """
    A node representing a single character in a relationship chart
    """

    id: str
    label: str

    is_phantom: bool = False

    child_ids: Set[str] = dataclasses.field(default_factory=set)
    parent_ids: Set[str] = dataclasses.field(default_factory=set)

    relationships: DefaultDict[Tuple[RelationshipStatus, str], Set[str]] = dataclasses.field(
        default_factory=lambda: defaultdict(set))

    character_data: Optional[CharacterData] = dataclasses.field(repr=False, default=None)

    def __eq__(self, other: CharacterNode) -> bool:
        return self.id == other.id


class MissingNodeError(Exception):
    ...


_RelationshipChart_T = TypeVar('_RelationshipChart_T', bound='RelationshipChart')


@dataclasses.dataclass
class RelationshipChart:
    """
    Class that stores a set of characters and their relationships and allows for their modification and filtering
    """

    nodes: Dict[str, CharacterNode] = dataclasses.field(default_factory=dict)

    def __iter__(self) -> Iterator[CharacterNode]:
        return iter(self.nodes.values())

    def children(self, node: CharacterNode) -> List[CharacterNode]:
        return [self.nodes[cid] for cid in node.child_ids]

    def parents(self, node: CharacterNode) -> List[CharacterNode]:
        return [self.nodes[cid] for cid in node.parent_ids]

    def siblings(self, node: CharacterNode) -> List[CharacterNode]:
        res = []
        for parent in self.parents(node):
            for other_child in self.children(parent):
                if other_child == node or other_child in res:
                    continue
                res.append(other_child)
        return res

    def iter_relationships(
            self, source: Optional[CharacterNode] = None, target: Optional[CharacterNode] = None,
            rel_status: Optional[RelationshipStatus] = None, rel_type: Optional[str] = None,
    ) -> Generator[Tuple[CharacterNode, CharacterNode, RelationshipStatus, str], None, None]:
        if source is None:
            for node in self:
                yield from self.iter_relationships(node, target, rel_status, rel_type)
            return

        for (source_rel_status, source_rel_type), source_rel_target_ids in source.relationships.items():
            if ((rel_status is not None and rel_status != source_rel_status)
                    or (rel_type is not None and rel_type != source_rel_type)):
                continue
            if target is None:
                for source_rel_target_id in source_rel_target_ids:
                    source_rel_target = self.get_node(source_rel_target_id)
                    yield source, source_rel_target, source_rel_status, source_rel_type
            elif target.id in source_rel_target_ids:
                yield source, target, source_rel_status, source_rel_type

    def label_lookup(self) -> DefaultDict[str, List[CharacterNode]]:
        res = defaultdict(list)
        for node in self:
            res[node.label].append(node)
        return res

    def add_node(self, node: CharacterNode) -> None:
        assert node.id not in self.nodes
        self.nodes[node.id] = node

    def create_phantom_node(self) -> CharacterNode:
        node = CharacterNode(id=f"phantom_{uuid.uuid4()}", label='unknown parent', is_phantom=True)
        self.add_node(node)
        return node

    def get_node(self, node_id: str) -> CharacterNode:
        if node_id not in self.nodes:
            raise MissingNodeError(node_id)
        return self.nodes[node_id]

    def remove_node(self, node_id: str, clear_relations: bool = True) -> None:
        node = self.get_node(node_id)

        if clear_relations:
            for child in self.children(node):
                child.parent_ids.discard(node_id)
            for parent in self.parents(node):
                parent.child_ids.discard(node_id)
            for source, target, rel_status, rel_type in self.iter_relationships(target=node):
                self.remove_relationship(source.id, node_id, rel_status, rel_type)

        self.nodes.pop(node_id)

    def add_child(self, parent_id: str, child_id: str, handle_phantoms: bool = True) -> None:
        assert parent_id != child_id

        parent = self.get_node(parent_id)
        child = self.get_node(child_id)

        parent.child_ids.add(child_id)
        child.parent_ids.add(parent_id)

        if handle_phantoms:
            for other_parent in self.parents(child):
                if other_parent == parent:
                    continue
                if other_parent.is_phantom and not other_parent.child_ids.difference(parent.child_ids):
                    self.remove_node(other_parent.id)

    def add_sibling(self, first_id: str, second_id: str) -> None:
        assert first_id != second_id

        first_node = self.get_node(first_id)
        second_node = self.get_node(second_id)

        if first_node.parent_ids.intersection(second_node.parent_ids):
            return

        phantom_parent = self.create_phantom_node()
        self.add_child(phantom_parent.id, first_id)
        self.add_child(phantom_parent.id, second_id)

    def add_relationship(self, first_id: str, second_id: str, rel_status: RelationshipStatus, rel_type: str) -> None:
        assert first_id != second_id

        first_node = self.get_node(first_id)
        second_node = self.get_node(second_id)

        first_node.relationships[rel_status, rel_type].add(second_id)
        second_node.relationships[rel_status, rel_type].add(first_id)

    def remove_relationship(self, first_id: str, second_id: str, rel_status: RelationshipStatus, rel_type: str) -> None:
        first_node = self.get_node(first_id)
        second_node = self.get_node(second_id)

        first_node.relationships[rel_status, rel_type].discard(second_id)
        second_node.relationships[rel_status, rel_type].discard(first_id)

    def remove_redundant_phantoms(self, clear_relations: bool = True) -> None:
        """
        Removes all phantom parents that are redundant due to real parents or other phantoms having all their children;
        also cleans up situations where more than two characters are sisters with each other through unknown parents,
        replacing all these parents with a single phantom
        :param clear_relations: whether to remove all connections with removed phantoms from other nodes
            (makes sense to set to False if remove_dead_edges will be called afterwards anyway)
        """

        remove_ids = []
        for node in self:
            if not node.is_phantom:
                continue

            if not node.child_ids:
                remove_ids.append(node.id)
                continue

            children = self.children(node)
            child = children[0]
            for other_parent in self.parents(child):
                if other_parent != node and not node.child_ids.difference(other_parent.child_ids):
                    remove_ids.append(node.id)
                    break
            else:
                common_phantom_siblings = None
                for child in children:
                    phantom_siblings = []
                    for other_parent in self.parents(child):
                        if other_parent.is_phantom and other_parent != node:
                            phantom_siblings.extend(other_parent.child_ids)
                    if common_phantom_siblings is None:
                        common_phantom_siblings = set(phantom_siblings)
                    else:
                        common_phantom_siblings.intersection_update(phantom_siblings)
                if common_phantom_siblings:
                    for sibling_id in common_phantom_siblings:
                        self.add_child(node.id, sibling_id, handle_phantoms=False)

        for remove_id in remove_ids:
            self.remove_node(remove_id, clear_relations=clear_relations)

    def remove_dead_edges(self) -> None:
        """
        Remove all connections from all nodes with targets that are not in the chart
        """

        for node in self:
            node.parent_ids.intersection_update(self.nodes.keys())
            node.child_ids.intersection_update(self.nodes.keys())
            for rel_target_ids in node.relationships.values():
                rel_target_ids.intersection_update(self.nodes.keys())

    def ensure_everything_mutual(self) -> None:
        """
        Makes all connections mutual in case nodes/connections were added manually and some relations may be one-sided
        """

        for node in self:
            for child in self.children(node):
                child.parent_ids.add(node.id)
            for parent in self.parents(node):
                parent.child_ids.add(node.id)

            for rel_source, rel_target, rel_status, rel_type in self.iter_relationships(source=node):
                rel_target.relationships[rel_status, rel_type].add(node.id)

    def postprocess(self) -> None:
        self.remove_redundant_phantoms(clear_relations=False)
        self.remove_dead_edges()
        self.ensure_everything_mutual()

    def filter_relationships(self: _RelationshipChart_T,
                             allowed_relationships: Optional[Iterable[Tuple[RelationshipStatus, str]]] = None,
                             disallowed_relationships: Optional[Iterable[Tuple[RelationshipStatus, str]]] = None,
                             inplace: bool = False) -> Optional[_RelationshipChart_T]:
        """
        Removes relationships from chart according to specified filters; wildcard relationship types are supported
        :param allowed_relationships: if not None, only relationships present in this list will remain
        :param disallowed_relationships: if not None, any relationships in this list will be removed
            (even if present in allowed_relationships)
        :param inplace: if False, a new copy of this chart will be created for these changes
        :return: None if inplace is True, else newly created chart
        """

        if not inplace:
            chart = deepcopy(self)
            chart.filter_relationships(allowed_relationships, inplace=True)
            return chart

        if allowed_relationships is not None:
            allowed_relationships = set(allowed_relationships)
        if disallowed_relationships is not None:
            disallowed_relationships = set(disallowed_relationships)

        for node in self:
            new_relationships = {}
            for (rel_status, rel_type), rel_targets in node.relationships.items():
                if (disallowed_relationships is not None
                        and ((rel_status, rel_type) in disallowed_relationships
                             or (rel_status, '*') in disallowed_relationships)):
                    continue
                if (allowed_relationships is None
                        or (rel_status, rel_type) in allowed_relationships
                        or (rel_status, '*') in allowed_relationships):
                    new_relationships[rel_status, rel_type] = rel_targets
            node.relationships = new_relationships
        return None

    def trim(self: _RelationshipChart_T,
             anchor_ids: Optional[Iterable[str]] = None,
             exclude_ids: Optional[Iterable[str]] = None,
             clear_relations: bool = True,
             inplace: bool = False) -> Optional[_RelationshipChart_T]:
        """
        Removes nodes from chart according to specified filters
        :param anchor_ids: if not None, only nodes in this list, their relatives and direct relationships will remain
        :param exclude_ids: if not None, any nodes in this list will be removed (even if present in anchor_ids)
            and their relations will not be processed
        :param clear_relations: whether to remove all connections with removed nodes from other nodes
            (makes sense to set to False if remove_dead_edges will be called afterwards anyway)
        :param inplace: if False, a new copy of this chart will be created for these changes
        :return: None if inplace is True, else newly created chart
        """

        if not inplace:
            chart = deepcopy(self)
            chart.trim(anchor_ids, inplace=True)
            return chart

        anchor_ids = set(anchor_ids) if anchor_ids is not None else set(self.nodes.keys())
        exclude_ids = set(exclude_ids) if exclude_ids is not None else set()

        def _get_related_nodes(current_node_ids: Set[str], res_set: Set[str]) -> Set[str]:
            res_set.update(current_node_ids)
            new_node_ids = set()
            for current_node_id in current_node_ids:
                current_node = self.get_node(current_node_id)
                new_node_ids.update(current_node.parent_ids)
                new_node_ids.update(current_node.child_ids)
            new_node_ids.difference_update(res_set)
            new_node_ids.difference_update(exclude_ids)
            if not new_node_ids:
                return res_set
            return _get_related_nodes(new_node_ids, res_set)

        related_nodes = _get_related_nodes(anchor_ids, set())
        for node_id in anchor_ids.difference(exclude_ids):
            node = self.get_node(node_id)
            for rel_target_ids in node.relationships.values():
                rel_target_ids = rel_target_ids.difference(exclude_ids)
                related_nodes.update(rel_target_ids)

        self.nodes = {k: v for k, v in self.nodes.items() if k in related_nodes}
        if clear_relations:
            self.remove_redundant_phantoms(clear_relations=False)
            self.remove_dead_edges()
        return None

    def apply_filter_params(self: _RelationshipChart_T,
                            params: FilterParams,
                            inplace: bool = False) -> Optional[_RelationshipChart_T]:
        """
        Applies all filter params
        :param params: FilterParams instance specifying filters to apply
        :param inplace: if False, a new copy of this chart will be created for these changes
        :return: None if inplace is True, else newly created chart
        """

        if not inplace:
            chart = deepcopy(self)
            chart.apply_filter_params(params, inplace=True)
            return chart

        if params.include_relationships is not None or params.exclude_relationships is not None:
            self.filter_relationships(params.include_relationships, params.exclude_relationships, inplace=True)

        if params.include_heroes is not None or params.exclude_heroes is not None:
            self.trim(params.include_heroes, params.exclude_heroes, clear_relations=False, inplace=True)

        self.remove_redundant_phantoms()
        self.remove_dead_edges()
        return None

    def clean_relationships(self: _RelationshipChart_T, inplace: bool = False) -> Optional[_RelationshipChart_T]:
        """
        Leaves only the relationship with the strongest status for each relationship type for every pair of nodes
        :param inplace: if False, a new copy of this chart will be created for these changes
        :return: None if inplace is True, else newly created chart
        """

        if not inplace:
            chart = deepcopy(self)
            chart.clean_relationships(inplace=True)
            return chart

        remove_relationships = []
        rel_status_dict = {}
        for rel_source, rel_target, rel_status, rel_type in self.iter_relationships():
            status_dict_key = (*sorted((rel_source.id, rel_target.id)), rel_type)
            if (prev_status := rel_status_dict.get(status_dict_key)) is not None:
                worse_status, better_status = sorted((rel_status, prev_status))
                if worse_status != better_status:
                    remove_relationships.append((rel_source.id, rel_target.id, worse_status, rel_type))
                    rel_status_dict[status_dict_key] = better_status
            else:
                rel_status_dict[status_dict_key] = rel_status

        for rel_data in remove_relationships:
            self.remove_relationship(*rel_data)
        return None

    @classmethod
    def from_node_list(cls: Type[_RelationshipChart_T], nodes: List[CharacterNode]) -> _RelationshipChart_T:
        res = cls()
        for node in nodes:
            res.add_node(node)
        return res

    @classmethod
    def from_character_data(cls: Type[_RelationshipChart_T],
                            characters: List[CharacterData],
                            postprocess: bool = True) -> _RelationshipChart_T:
        """
        Creates a RelationshipChart instance from a list of characters
        :param characters: list of CharacterData instances representing characters in the chart
        :param postprocess: whether to cleanup the chart after creation
            (currently there's no reason not to, unless more nodes/relationships are to be added manually later)
        :return: created RelationshipChart instance
        """

        chart = cls.from_node_list([
            CharacterNode(id=cdata.id, label=cdata.name, character_data=cdata)
            for cdata in characters
        ])

        past_relationship_re = re.compile(r'relationship_(.*)_\d+')

        for character_data in characters:
            for aspect in character_data.iter_aspects():
                with contextlib.suppress(MissingNodeError):
                    if aspect.title == 'parentOf':
                        chart.add_child(character_data.id, aspect.data[0])
                    elif aspect.title == 'childOf':
                        chart.add_child(aspect.data[0], character_data.id)
                    elif aspect.title == 'siblingOf':
                        chart.add_sibling(character_data.id, aspect.data[0])

                    elif aspect.title == 'lockedRelationship':
                        chart.add_relationship(
                            character_data.id, aspect.data[1], RelationshipStatus.LOCKED, aspect.data[0])
                    elif (match := past_relationship_re.fullmatch(aspect.title)) is not None:
                        chart.add_relationship(
                            character_data.id, aspect.data[0], RelationshipStatus.PAST, match.group(1))

        if postprocess:
            chart.postprocess()
        return chart
