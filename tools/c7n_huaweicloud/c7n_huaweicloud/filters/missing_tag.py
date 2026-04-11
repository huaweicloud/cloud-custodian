import re
import logging

from c7n import utils
from c7n.filters import Filter
from c7n.exceptions import PolicyExecutionError

log = logging.getLogger("custodian.filters.missing-tag-filter")


def register_missing_tag_filters(filters):
    filters.register('missing-tag-filter', MissingTagFilter)


def get_tags_from_resource(resource):
    def process_value(val):
        return val if val is not None else ""

    if "tags" not in resource:
        raise KeyError(f"tags is required in resource [{resource['id']}]")
    try:
        tags = resource["tags"]
        if isinstance(tags, dict):
            return tags
        elif isinstance(tags, list):
            result = {}
            for item in tags:
                if isinstance(item, dict):
                    if "key" in item:
                        key = item["key"]
                        value = item.get("value")
                        result[key] = process_value(value)
                    else:
                        if len(item) == 1:
                            k, v = next(iter(item.items()))
                            result[k] = process_value(v)
                elif isinstance(item, str):
                    if "=" in item:
                        k, v = item.split("=", 1)
                        result[k] = process_value(v)
                    else:
                        result[item] = ""
                else:
                    log.warning(f"{item} type not support "
                                f"in resource [{resource['id']}]")
            return result
        raise PolicyExecutionError(f"tags:{tags} type not support "
                                   f"in resource {resource['id']}")
    except Exception:
        log.error(f"tags:{tags} type not support "
                  f"in resource [{resource['id']}]")
        raise PolicyExecutionError(f"tags:{tags} type not support "
                                   f"in resource [{resource['id']}]")


class MissingTagFilter(Filter):
    """Detects and filters Huawei Cloud resources that are missing the designated tags.

    :example:

    .. code-block:: yaml

            policies:
              - name: missing-tag-test
                resource: huaweicloud.evs-volume
                filters:
                  - type: missing-tag-filter
                    tags:
                      - key: key1
                        value: ^pattern1$
                      - key: key2
                        value: value2
                    match: missing-any
    """
    schema = utils.type_schema(
        'missing-tag-filter',
        required=['tags'],
        tags={
            'type': 'array',
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'required': ['key'],
                'properties': {
                    'key': {'type': 'string', 'minLength': 1, 'maxLength': 36},
                    'value': {'type': 'string'}
                }
            }
        },
        match={'type': 'string', 'enum': ['missing-all', 'missing-any']}
    )

    expected_tags = []

    def process(self, resources, event=None):
        for t in self.data.get('tags', []):
            key = t.get('key')
            value = t.get('value')
            if isinstance(value, str) and value.startswith('^') and value.endswith('$'):
                try:
                    pattern = re.compile(value)
                    self.expected_tags.append((key, pattern))
                except re.error:
                    log.info('[filters]-[missing-tag-filter]: failed to compile' +
                             ' the regular exception [%s].' % value)
                    self.expected_tags.append((key, value))
            else:
                self.expected_tags.append((key, value))

        with self.executor_factory(max_workers=5) as executor:
            results = list(filter(None, executor.map(
                self.process_resource_wrapper, resources)))
            return results
        return None

    def process_resource_wrapper(self, resource):
        """Wrapper function to process a single resource with expected_tags."""
        return self.process_resource(resource, self.expected_tags)

    def process_resource(self, resource, expected_tags):
        match_mode = self.data.get('match', 'missing-any')

        resource_tags = get_tags_from_resource(resource)
        if self._is_match(expected_tags, resource_tags, match_mode, resource['id']):
            log.info('[filters]-[missing-tag-filter]: The resource ' +
                     '[%s] missing some tags' % (resource['id']))
            log.info("[filters]-[missing-tag-filter] filter resource " +
                     "with id:[%s] success." % (resource['id']))
            return resource
        else:
            return None

    def _is_match(self, expected_tags, actual_tags, match_mode, resource_id):
        actual_dict = actual_tags

        results = []
        for key, exp_value in expected_tags:
            actual_value = actual_dict.get(key)

            # Case 1: Expected None
            if exp_value is None:
                if key in actual_dict and actual_value is None:
                    results.append(True)
                else:
                    results.append(False)
            # Case 2: Regex pattern (key must exist and value must match pattern)
            elif isinstance(exp_value, re.Pattern):
                if actual_value is None:
                    results.append(False)
                else:
                    results.append(bool(exp_value.match(actual_value)))
            # Case 3: Literal string (key must exist and values must match exactly)
            else:
                results.append(actual_value == exp_value)

            log.debug('[filters]-[missing-tag-filter]: check resource:[%s] tag '
                      '(%s, %s) result is [%s]' % (resource_id, key, actual_value, results[-1]))

        if match_mode == 'missing-all':
            # all expected tags to NOT match
            return not any(results)
        elif match_mode == 'missing-any':
            # Require at least one expected tag to NOT match
            return not all(results)
        return False
