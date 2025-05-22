# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
from c7n.utils import type_schema
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n.filters import ValueFilter

log = logging.getLogger('custodian.huaweicloud.resources.lts')


@resources.register('lts-logstream')
class LogStream(QueryResourceManager):
    """华为云LTS日志流资源

    :example:

    .. code-block:: yaml

        policies:
          - name: lts-logstream-list
            resource: huaweicloud.lts-logstream
    """

    class resource_type(TypeInfo):
        service = 'lts-logstream'
        enum_spec = ('list_log_groups', 'log_groups', None)
        id = 'log_group_id'
        name = 'log_group_name'
        tag_resource_type = 'lts-logstream'


@LogStream.filter_registry.register('loggroup')
class LogGroupFilter(ValueFilter):
    """过滤账号下所有日志组

    :example:

    .. code-block:: yaml

        policies:
          - name: lts-logstreams-by-group
            resource: huaweicloud.lts-logstream
            filters:
              - type: loggroup
                key: log_group_id
                value: "your-log-group-id"
    """

    schema = type_schema('loggroup', rinherit=ValueFilter.schema)
    schema_alias = False

    def process(self, resources, event=None):
        return [r for r in resources if self.match(r)]
