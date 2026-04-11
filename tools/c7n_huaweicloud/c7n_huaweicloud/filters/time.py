# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging

from datetime import datetime
from dateutil.tz import tzutc
from dateutil.parser import parse

from c7n.exceptions import PolicyValidationError
from c7n.filters import AgeFilter

from c7n.utils import type_schema

log = logging.getLogger("custodian.filters.time")


def register_time_filters(filters):
    filters.register('resource-time', ResourceTimeFilter)


class ResourceTimeFilter(AgeFilter):
    """
    Filter resources by resource time.
    It is necessary to specify a parameter represented resource time
    as 'time_attribute', such as 'created_at', indicating the
    creation time.

    :example:

    .. code-block:: yaml

        policies:
          - name: sg-time-filter
            resource: huaweicloud.vpc-security-group
            filters:
              - type: resource-time
                time_attribute: "created_at"
                op: less-than
                days: 1
                hours: 1
                minutes: 1
    """

    schema = type_schema(
        "resource-time",
        time_attribute={"type": "string"},
        op={"$ref": "#/definitions/filters_common/comparison_operators"},
        days={"type": "number"},
        hours={"type": "number"},
        minutes={"type": "number"},
        required=["time_attribute"]
    )

    def validate(self):
        self.date_attribute = self.data.get("time_attribute", "updated_at")
        if not self.date_attribute:
            raise NotImplementedError(
                "date_attribute must be overriden in subclass")
        return self

    def get_resource_date(self, i):
        v = i.get(self.date_attribute, None)

        if not v:
            raise PolicyValidationError("Not exist resource param '%s'" % self.date_attribute)
        if isinstance(v, datetime):
            if not v.tzinfo:
                v = v.astimezone(tzutc())
            return v
        if isinstance(v, str) and not v.isdigit():
            try:
                pv = parse(v)
                if not pv.tzinfo and 'T' in v:
                    pv = pv.replace(tzinfo=tzutc())
                return pv.astimezone(tzutc())
            except ValueError as e:
                log.error(f"[filters]-[resource-time] parse '{self.date_attribute}' param value "
                          "to datetime failed, cause: invalid time format.")
                raise e
        return self.timestamp2datetime(v)

    def timestamp2datetime(self, v, tz=tzutc()):
        exceptions = (ValueError, TypeError, OverflowError)
        if isinstance(v, (int, float, str)):
            try:
                v = datetime.fromtimestamp(float(v)).astimezone(tz)
            except exceptions:
                pass

        if isinstance(v, (int, float, str)):
            # try interpreting as milliseconds epoch
            try:
                v = datetime.fromtimestamp(float(v) / 1000).astimezone(tz)
            except exceptions:
                pass
        return v
