# -*- encoding: utf-8 -*-

from __future__ import annotations

from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import TypedDict
from typing import Union


class IdDict(TypedDict):
    value: str


class SingleAspectDict(TypedDict):
    aspect: str
    value: Optional[float]


class AspectsDict(TypedDict, total=False):
    entries: List[Tuple[str, SingleAspectDict]]


class IndividualStatusDict(TypedDict, total=False):
    name: str
    aspects: AspectsDict


class LegacyAspectsDict(TypedDict, total=False):
    entries: List[Union[Tuple[str, float], Tuple[str]]]


class IndividualHistoryDict(TypedDict, total=False):
    legacyAspects: Optional[LegacyAspectsDict]


class ProcessedIndividualDict(TypedDict, total=False):
    id: IdDict
    status: IndividualStatusDict
    history: IndividualHistoryDict


class SnapshotDict(TypedDict, total=False):
    date: int
    entities: List[List[Union[str, Dict]]]


class EntryDict(TypedDict, total=False):
    id: IdDict
    type: str
    snapshots: List[SnapshotDict]


class LegacyDict(TypedDict, total=False):
    entries: List[EntryDict]
