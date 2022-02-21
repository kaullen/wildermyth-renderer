# -*- encoding: utf-8 -*-

from __future__ import annotations

import dataclasses
import enum
import logging
from functools import cached_property
from typing import Generator
from typing import List
from typing import Optional
from typing import TYPE_CHECKING
from typing import Tuple
from typing import Type
from typing import TypeVar

if TYPE_CHECKING:
    from wildermyth_renderer import schemas

log = logging.getLogger(__name__)


class CharacterGender(enum.Enum):
    MALE = 'male'
    FEMALE = 'female'
    NONBINARY = 'nonbinary'
    UNKNOWN = 'unknown'


_CharacterAspect_T = TypeVar('_CharacterAspect_T', bound='CharacterAspect')


@dataclasses.dataclass(frozen=True)
class CharacterAspect:
    """
    Information about a single character aspect
    """

    title: str

    data: Tuple[str] = ()
    value: float = 0

    is_legacy: bool = False
    is_past: bool = False
    snapshot_id: Optional[int] = None

    @classmethod
    def from_aspect_data(cls: Type[_CharacterAspect_T], aspect_data: Tuple, **kwargs) -> _CharacterAspect_T:
        """
        Creates a CharacterAspect instance from aspect data as seen in legacy JSON
        :param aspect_data: aspect data from legacy JSON,
            can be either [aspect_string, value] or [aspect_string, {"aspect": aspect_string, "value": value}]
            (in both cases value can be missing)
        :param kwargs: extra kwargs passed directly to created aspect
        :return: created CharacterAspect instance
        """
        aspect_data = cls._normalize_aspect_data(aspect_data)

        title, has_data, data_str = aspect_data['aspect'].partition('|')
        data = tuple(data_str.split('|')) if has_data else ()

        if aspect_data.get('value') is not None:
            kwargs['value'] = aspect_data['value']

        return cls(title=title, data=data, **kwargs)

    @classmethod
    def _normalize_aspect_data(cls, aspect_data: Tuple) -> schemas.SingleAspectDict:
        if len(aspect_data) < 2:
            value = None
        elif isinstance(aspect_data[1], (int, float)) or aspect_data[1] is None:
            value = aspect_data[1]
        elif isinstance(aspect_data[1], dict):
            value = aspect_data[1].get('value')
        else:
            raise TypeError(aspect_data[1])

        return {
            'aspect': aspect_data[0],
            'value': value,
        }


_CharacterData_T = TypeVar('_CharacterData_T', bound='CharacterData')


@dataclasses.dataclass(frozen=True)
class CharacterData:
    """
    Information about a single character
    """

    id: str

    name: str
    aspects: List[CharacterAspect]

    @cached_property
    def short_id(self) -> str:
        return self.id.split('-', 1)[0]

    @cached_property
    def gender(self) -> CharacterGender:
        for aspect in self.iter_aspects(present=True):
            if aspect.title in ('male', 'female', 'nonbinary'):
                return CharacterGender(aspect.title)
        return CharacterGender.UNKNOWN

    def iter_aspects(self,
                     legacy: Optional[bool] = None,
                     present: Optional[bool] = None,
                     ) -> Generator[CharacterAspect, None, None]:
        """
        Iterates character aspects with optional filters
        :param legacy: if not None, only aspects with is_legacy equal to this will be iterated
        :param present: if not None, only aspects with is_past NOT equal to this will be iterated
        :return: iterator of all relevant aspects
        """
        for aspect in self.aspects:
            if legacy is not None and legacy != aspect.is_legacy:
                continue
            if present is not None and present != (not aspect.is_past):
                continue
            yield aspect

    @classmethod
    def from_entity_dicts(cls: Type[_CharacterData_T],
                          *entity_snapshots: schemas.ProcessedIndividualDict) -> _CharacterData_T:
        """
        Creates a CharacterData instance from a list of different snapshots of the same individual from legacy JSON
        :param entity_snapshots: preprocessed entity dictionaries of an individual
        :return: created CharacterData instance
        """
        last_snapshot = entity_snapshots[-1]

        id_ = last_snapshot['id']['value']
        name = last_snapshot['status']['name']

        aspects = [
            CharacterAspect.from_aspect_data(
                aspect_data,
                is_legacy=False,
                is_past=False,
                snapshot_id=0,
            )
            for aspect_data in last_snapshot['status']['aspects']['entries']
        ]
        if 'legacyAspects' in last_snapshot['history']:
            for legacy_aspect in last_snapshot['history']['legacyAspects']['entries']:
                aspects.append(CharacterAspect.from_aspect_data(
                    legacy_aspect,
                    is_legacy=True,
                    is_past=False,
                    snapshot_id=0,
                ))

        for idx, past_snapshot in enumerate(entity_snapshots[-2::-1]):
            for aspect_data in past_snapshot['status']['aspects']['entries']:
                past_aspect = CharacterAspect.from_aspect_data(
                    aspect_data,
                    is_legacy=False,
                    is_past=True,
                    snapshot_id=idx + 1,
                )
                if any(a.title == past_aspect.title and a.data == past_aspect.data for a in aspects):
                    continue
                aspects.append(past_aspect)

        return cls(id=id_, name=name, aspects=aspects)
