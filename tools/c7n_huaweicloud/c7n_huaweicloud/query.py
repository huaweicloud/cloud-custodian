# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
import json
import logging
import jmespath
import sys

from c7n.actions import ActionRegistry
from c7n.filters import FilterRegistry
from c7n.manager import ResourceManager
from c7n.query import sources, MaxResourceLimit
from c7n.utils import local_session
from c7n_huaweicloud.actions.tms import register_tms_actions
from c7n_huaweicloud.filters.tms import register_tms_filters

from tools.c7n_huaweicloud.c7n_huaweicloud.marker_pagination import MarkerPagination

from huaweicloudsdkcore.exceptions import exceptions

log = logging.getLogger('custodian.huaweicloud.query')

DEFAULT_LIMIT_SIZE = 100
DEFAULT_MAXITEMS_SIZE = 400


def _dict_map(obj, params_map):
    if not params_map:
        return obj
    for k, v in params_map.items():
        obj.__dict__['_' + k] = v


class ResourceQuery:
    def __init__(self, session_factory):
        self.session_factory = session_factory

    @staticmethod
    def resolve(resource_type):
        if not isinstance(resource_type, type):
            raise ValueError(resource_type)
        return resource_type

    def filter(self, resource_manager, **params):
        m = resource_manager.resource_type
        enum_op, path, pagination = m.enum_spec

        if pagination == 'offset':
            resources = self._pagination_limit_offset(m, enum_op, path)
        elif pagination == 'marker':
            resources = self._pagination_limit_marker(m, enum_op, path)
        elif pagination == 'maxitems-marker':
            resources = self._pagination_maxitems_marker(m, enum_op, path)
        else:
            log.exception(f"Unsupported pagination type: {pagination}")
            sys.exit(1)
        return resources

    def _pagination_limit_offset(self, m, enum_op, path):
        session = local_session(self.session_factory)
        client = session.client(m.service)

        offset = 0
        limit = DEFAULT_LIMIT_SIZE
        resources = []
        while 1:
            request = session.request(m.service)
            request.limit = limit
            request.offset = offset
            response = self._invoke_client_enum(client, enum_op, request)
            res = jmespath.search(path, eval(
                str(response).replace('null', 'None').replace('false', 'False').replace('true', 'True')))

            if path == '*':
                resources.append(json.loads(str(response)))
                return resources

            # replace id with the specified one
            if res is not None:
                for data in res:
                    data['id'] = data[m.id]
                    data['tag_resource_type'] = m.tag_resource_type

            resources = resources + res
            if len(res) == limit:
                offset += limit
            else:
                return resources
        return resources

    def _pagination_maxitems_marker(self, m, enum_op, path):
        session = local_session(self.session_factory)
        client = session.client(m.service)

        marker, count = 0, 0
        maxitems = DEFAULT_MAXITEMS_SIZE
        resources = []
        while 1:
            request = session.request(m.service)
            request.marker = marker
            request.maxitems = maxitems
            try:
                response = self._invoke_client_enum(client, enum_op, request)
            except exceptions.ClientRequestException as e:
                log.error(
                    f'request[{e.request_id}] failed[{e.status_code}], error_code[{e.error_code}], error_msg[{e.error_msg}]')
                return resources
            count = response.count
            next_marker = response.next_marker
            res = jmespath.search(path, eval(
                str(response).replace('null', 'None').replace('false', 'False').replace('true', 'True')))

            # replace id with the specified one
            if res is not None:
                for data in res:
                    data['id'] = data[m.id]

            resources = resources + res
            marker = next_marker
            if next_marker >= count:
                break
        return resources

    def _pagination_limit_marker(self, m, enum_op, path, marker_pagination: MarkerPagination=None):
        session = local_session(self.session_factory)
        client = session.client(m.service)

        if not marker_pagination:
            marker_pagination = DefaultMarkerPagination(DEFAULT_LIMIT_SIZE)
        page_params = marker_pagination.get_first_page_params()
        request = session.request(m.service)
        _dict_map(request, page_params)
        resources = []
        while 1:
            response = self._invoke_client_enum(client, enum_op, request)
            response = eval(str(response).replace('null', 'None').
                            replace('false', 'False').replace('true', 'True'))
            res = jmespath.search(path, response)

            # replace id with the specified one
            if res is None or len(res) == 0:
                return resources
            # re-set id
            if 'id' not in res[0]:
                for data in res:
                    data['id'] = data[m.id]
            # merge result
            resources = resources + res

            # get next page info
            next_page_params = marker_pagination.get_next_page_params(response)
            if next_page_params:
                _dict_map(request, next_page_params)
            else:
                return resources

    def _invoke_client_enum(self, client, enum_op, request):
        return getattr(client, enum_op)(request)


# abstract method for pagination
class DefaultMarkerPagination(MarkerPagination):
    def __init__(self, limit):
        self.limit = limit

    def get_first_page_params(self):
        return {'limit': self.limit}

    def get_next_page_params(self, response):
        page_info = jmespath.search('page_info', response)
        if not page_info:
            return None
        next_marker = page_info.get('next_marker')
        if not next_marker:
            return None
        return {'limit': self.limit, 'marker': next_marker}


@sources.register('describe-huaweicloud')
class DescribeSource:
    def __init__(self, manager):
        self.manager = manager
        self.query = ResourceQuery(manager.session_factory)

    def get_resources(self, query):
        if query is None:
            query = {}
        return self.query.filter(self.manager, **query)

    def get_permissions(self):
        return ()

    def augment(self, resources):
        return resources


class QueryMeta(type):
    """metaclass to have consistent action/filter registry for new resources."""
    def __new__(cls, name, parents, attrs):
        if 'resource_type' not in attrs:
            return super(QueryMeta, cls).__new__(cls, name, parents, attrs)

        if 'filter_registry' not in attrs:
            attrs['filter_registry'] = FilterRegistry(
                '%s.filters' % name.lower())
        if 'action_registry' not in attrs:
            attrs['action_registry'] = ActionRegistry(
                '%s.actions' % name.lower())

        m = ResourceQuery.resolve(attrs['resource_type'])
        if getattr(m, 'tag_resource_type', None):
            register_tms_actions(attrs['action_registry'])
            register_tms_filters(attrs['filter_registry'])
        return super(QueryMeta, cls).__new__(cls, name, parents, attrs)


class QueryResourceManager(ResourceManager, metaclass=QueryMeta):

    source_mapping = sources

    def __init__(self, ctx, data):
        super(QueryResourceManager, self).__init__(ctx, data)
        self.source = self.get_source(self.source_type)

    def get_permissions(self):
        return ()

    def get_source(self, source_type):
        if source_type in self.source_mapping:
            return self.source_mapping.get(source_type)(self)
        if source_type in sources:
            return sources[source_type](self)
        raise KeyError("Invalid Source %s" % source_type)

    def get_client(self):
        session = local_session(self.session_factory)
        client = session.client(self.resource_type.service)
        return client

    def get_model(self):
        return self.resource_type

    def get_cache_key(self, query):
        return {'source_type': self.source_type,
                'query': query,
                'service': self.resource_type.service}

    def get_resource(self, resource_info):
        return self.resource_type.get(self.get_client(), resource_info)

    @property
    def source_type(self):
        return self.data.get('source', 'describe-huaweicloud')

    def get_resource_query(self):
        if 'query' in self.data:
            return {'filter': self.data.get('query')}

    def resources(self, query=None):
        q = query or self.get_resource_query()
        key = self.get_cache_key(q)
        resources = None
        if self._cache.load():
            resources = self._cache.get(key)
            if resources:
                self.log.debug(
                    "Using cached %s: %d"
                    % (
                        "%s.%s" % (self.__class__.__module__, self.__class__.__name__),
                        len(resources),
                    )
                )
        if resources is None:
            resources = self._fetch_resources(q)
            self._cache.save(key, resources)

        resource_count = len(resources)
        resources = self.filter_resources(resources)

        # Check if we're out of a policies execution limits.
        if self.data == self.ctx.policy.data:
            self.check_resource_limit(len(resources), resource_count)
        return resources

    def check_resource_limit(self, selection_count, population_count):
        """Check if policy's execution affects more resources then its limit.
        """
        p = self.ctx.policy
        max_resource_limits = MaxResourceLimit(p, selection_count, population_count)
        return max_resource_limits.check_resource_limits()

    def _fetch_resources(self, query):
        return self.augment(self.source.get_resources(query)) or []

    def augment(self, resources):
        return resources


class TypeMeta(type):
    def __repr__(cls):
        return "<TypeInfo service:%s>" % (
            cls.service)


class TypeInfo(metaclass=TypeMeta):
    service = None
