# -*- encoding: utf-8 -*-

from __future__ import annotations

import logging
from typing import Dict
from typing import List
from typing import TYPE_CHECKING
from typing import Union

if TYPE_CHECKING:
    from wildermyth_renderer import schemas

log = logging.getLogger(__name__)


def entity_to_dict(entity: List[Union[str, Dict]]) -> Dict[str, Dict]:
    """
    Converts a [id, key1, val1, key2, val2, ...] list used for describing entities in legacy JSON
    into a {"id": id, key1: val1, key2: val2, ...} dictionary
    """

    entity_dict = {}
    for idx in range(0, len(entity), 2):
        key = 'id' if idx == 0 else entity[idx - 1]
        value = entity[idx]

        assert isinstance(key, str)
        assert isinstance(value, dict)

        entity_dict[key] = value
    return entity_dict


def extract_individual_entities(legacy_dict: schemas.LegacyDict) -> List[List[schemas.ProcessedIndividualDict]]:
    """
    Extracts all entities describing individuals from legacy dictionary
    :param legacy_dict: legacy dictionary, read directly from JSON
    :return: List of lists of different character snapshots for each character
    """

    res = []
    for legacy_entry in legacy_dict['entries']:
        if legacy_entry['type'] != 'INDIVIDUAL':
            log.info('Legacy entry %s has type %s, skipping', legacy_entry['id']['value'], legacy_entry['type'])
            continue

        if not legacy_entry['snapshots']:
            log.error('Legacy entry %s has no snapshots, skipping', legacy_entry['id']['value'])

        entity_snapshots = []
        for idx, snapshot in enumerate(sorted(legacy_entry['snapshots'], key=lambda s: s['date'])):
            try:
                individual_entity = next(entity for entity in snapshot['entities'] if 'individual' in entity)
            except StopIteration:
                log.error('Legacy entry %s\'s snapshot #%d has no individual entity',
                          legacy_entry['id']['value'], idx + 1)
                continue
            else:
                entity_snapshots.append(entity_to_dict(individual_entity))

        if entity_snapshots:
            res.append(entity_snapshots)
    return res
