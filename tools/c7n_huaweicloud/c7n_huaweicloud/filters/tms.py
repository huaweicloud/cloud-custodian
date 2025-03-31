import re
from datetime import datetime, timedelta

from c7n import utils
from c7n.exceptions import PolicyValidationError
from c7n.filters import OPERATORS, Filter
from dateutil import tz as tzutil
from dateutil.parser import parse

from c7n.filters.offhours import Time

DEFAULT_TAG = "mark-for-op-custodian"


def register_tms_filters(filters):
    filters.register('tag-count', TagCountFilter)
    filters.register('marked-for-op', TagActionFilter)


class TagCountFilter(Filter):
    """Simplify tag counting..

    ie. these two blocks are equivalent

    .. code-block :: yaml

       - filters:
           - type: value
             op: gte
             count: 5

       - filters:
           - type: tag-count
             count: 5
    """
    schema = utils.type_schema(
        'tag-count',
        count={'type': 'integer', 'minimum': 0},
        op={'enum': list(OPERATORS.keys())})
    schema_alias = True

    def __call__(self, i):
        count = self.data.get('count', 5)
        op_name = self.data.get('op', 'gte')
        op = OPERATORS.get(op_name)
        tags = self.get_tags_from_resource(i)
        tag_count = len([k for k, v in tags.items() if not k.startswith('_sys')])
        return op(tag_count, count)

    def get_tags_from_resource(self, resource):
        try:
            tags = resource["tags"]
            if isinstance(tags, dict):
                return tags
            elif isinstance(tags, list):
                if all(isinstance(item, dict) and len(item) == 1 for item in tags):
                    # [{k1: v1}, {k2: v2}]
                    result = {}
                    for item in tags:
                        key, value = list(item.items())[0]
                        result[key] = value
                    return result
                elif all(isinstance(item, str) and '=' in item for item in tags):
                    # ["k1=v1", "k2=v2"]
                    result = {}
                    for item in tags:
                        key, value = item.split('=', 1)
                        result[key] = value
                    return result
                elif all(isinstance(item, dict) and 'key' in item and 'value' in item for item in
                         tags):
                    # [{"key": k1, "value": v1}, {"key": k2, "value": v2}]
                    return {item['key']: item['value'] for item in tags}
            return {}
        except Exception:
            self.log.error("Parse Tags in resource %s failed", resource["id"])
            return {}


class TagActionFilter(Filter):
    """Filter resources for tag specified future action

    Filters resources by a 'mark-for-op-custodian' tag which specifies a future
    date for an action.

    The filter parses the tag values looking for an 'op_date'
    string. The date is parsed and compared to do today's date, the
    filter succeeds if today's date is gte to the target date.

    The optional 'skew' parameter provides for incrementing today's
    date a number of days into the future. An example use case might
    be sending a final notice email a few days before terminating an
    instance, or snapshotting a volume prior to deletion.

    The optional 'skew_hours' parameter provides for incrementing the current
    time a number of hours into the future.

    Optionally, the 'tz' parameter can get used to specify the timezone
    in which to interpret the clock (default value is 'utc')

    .. code-block :: yaml

      policies:
        - name: marked-for-op-volume
          resource: huaweicloud.volume
          filters:
            - type: marked-for-op
              # The default tag used is mark-for-op-custodian
              # but that is configurable
              tag: custodian_status
              op: stop
              # Another optional tag is skew
              tz: utc
          actions:
            - type: stop

    """
    schema = utils.type_schema(
        'marked-for-op',
        tag={'type': 'string'},
        tz={'type': 'string'},
        skew={'type': 'number', 'minimum': 0},
        skew_hours={'type': 'number', 'minimum': 0},
        op={'type': 'string'})
    schema_alias = True

    def validate(self):
        op = self.data.get('op')
        if self.manager and op not in self.manager.action_registry.keys():
            raise PolicyValidationError(
                "Invalid marked-for-op op:%s in %s" % (op, self.manager.data))

        tz = tzutil.gettz(Time.TZ_ALIASES.get(self.data.get('tz', 'utc')))
        if not tz:
            raise PolicyValidationError(
                "Invalid timezone specified '%s' in %s" % (
                    self.data.get('tz'), self.manager.data))
        return self

    def __call__(self, i):
        tag = self.data.get('tag', DEFAULT_TAG)
        op = self.data.get('op', 'stop')
        skew = self.data.get('skew', 0)
        skew_hours = self.data.get('skew_hours', 0)
        tz = tzutil.gettz(Time.TZ_ALIASES.get(self.data.get('tz', 'utc')))

        tags = self.get_tags_from_resource(i)

        value = None
        for key in tags.keys():
            if key == tag:
                value = tags[key]
                break

        if value is None:
            return False
        if '_' not in value:
            return False

        action, action_date_str = value.strip().split('_', 1)

        if action != op:
            return False

        try:
            action_date_str = self.replace_nth_regex(action_date_str, "-", " ", 3)
            action_date_str = self.replace_nth_regex(action_date_str, "-", ":", 3)
            action_date_str = self.replace_nth_regex(action_date_str, "-", " ", 3)
            action_date = parse(action_date_str)
        except Exception:
            self.log.warning("could not parse tag:%s value:%s on %s" % (
                tag, value, i['id']))
            return False

        if action_date.tzinfo:
            # if action_date is timezone aware, set to timezone provided
            action_date = action_date.astimezone(tz)
            current_date = datetime.now(tz=tz)
        else:
            current_date = datetime.now()

        return current_date >= (
                action_date - timedelta(days=skew, hours=skew_hours))

    def replace_nth_regex(self, s, old, new, n):
        pattern = re.compile(re.escape(old))
        matches = list(pattern.finditer(s))
        if len(matches) < n:
            return s
        match = matches[n - 1]
        return s[:match.start()] + new + s[match.end():]

    def get_tags_from_resource(self, resource):
        try:
            tags = resource["tags"]
            if isinstance(tags, dict):
                return tags
            elif isinstance(tags, list):
                if all(isinstance(item, dict) and len(item) == 1 for item in tags):
                    # [{k1: v1}, {k2: v2}]
                    result = {}
                    for item in tags:
                        key, value = list(item.items())[0]
                        result[key] = value
                    return result
                elif all(isinstance(item, str) and '=' in item for item in tags):
                    # ["k1=v1", "k2=v2"]
                    result = {}
                    for item in tags:
                        key, value = item.split('=', 1)
                        result[key] = value
                    return result
                elif all(isinstance(item, dict) and 'key' in item and 'value' in item for item in
                         tags):
                    # [{"key": k1, "value": v1}, {"key": k2, "value": v2}]
                    return {item['key']: item['value'] for item in tags}
            return {}
        except Exception:
            self.log.error("Parse Tags in resource %s failed", resource["id"])
            return {}
