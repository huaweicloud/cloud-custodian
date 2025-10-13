# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import datetime
import logging

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

    # date_attribute = "created_at"
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
        if not isinstance(v, datetime.datetime):
            try:
                v = parse(v)
            except ValueError as e:
                log.error(f"[filters]-[resource-time] parse '{self.date_attribute}' param value "
                          "to datetime failed, cause: invalid time format.")
                raise e
        if not v.tzinfo:
            v = v.replace(tzinfo=tzutc())
        return v
