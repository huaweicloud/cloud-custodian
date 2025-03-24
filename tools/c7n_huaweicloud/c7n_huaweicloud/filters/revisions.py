# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
"""
Custodian support for diffing and patching across multiple versions
of a resource.
"""

from dateutil.parser import parse as parse_date
from dateutil.tz import tzlocal, tzutc
from huaweicloudsdkconfig.v1 import ShowResourceHistoryRequest
from huaweicloudsdkcore.exceptions import exceptions

from c7n.exceptions import PolicyValidationError
from c7n.filters import Filter
from c7n.manager import resources
from c7n.utils import local_session, type_schema

try:
    import jsonpatch
    print("123456")
    HAVE_JSONPATH = True
except ImportError:
    HAVE_JSONPATH = False

UTC = tzutc()


class Diff(Filter):
    """Compute the diff from the current resource to a previous version.

    A resource matches the filter if a diff exists between the current
    resource and the selected revision.

    Utilizes config as a resource revision database.

    Revisions can be selected by date, against the previous version, and
    against a locked version (requires use of is-locked filter).
    """

    schema = type_schema(
        'diff',
        selector={'enum': ['previous', 'date', 'locked']},
        # For date selectors allow value specification
        selector_value={'type': 'string'})

    selector_value = mode = parser = resource_shape = None

    def validate(self):
        if 'selector' in self.data and self.data['selector'] == 'date':
            if 'selector_value' not in self.data:
                raise PolicyValidationError(
                    "Date version selector requires specification of date on %s" % (
                        self.manager.data))
            try:
                parse_date(self.data['selector_value'])
            except ValueError:
                raise PolicyValidationError(
                    "Invalid date for selector_value on %s" % (self.manager.data))

        elif 'selector' in self.data and self.data['selector'] == 'locked':
            idx = self.manager.data['filters'].index(self.data)
            found = False
            for n in self.manager.data['filters'][:idx]:
                if isinstance(n, dict) and n.get('type', '') == 'locked':
                    found = True
                if isinstance(n, str) and n == 'locked':
                    found = True
            if not found:
                raise PolicyValidationError(
                    "locked selector needs previous use of is-locked filter on %s" % (
                        self.manager.data))
        return self

    def process(self, resources, event=None):
        session = local_session(self.manager.session_factory)
        config = session.client('config')
        self.model = self.manager.get_model()

        results = []
        for r in resources:
            revisions = self.get_revisions(config, r)
            r['huaweicloud:previous-revision'] = rev = self.select_revision(revisions)
            if not rev:
                continue
            delta = self.diff(rev['resource'], r)
            if delta:
                r['huaweicloud:diff'] = delta
                results.append(r)
        return results

    def get_revisions(self, config, resource):
        request = self.get_selector_params(resource)
        try:
            response = config.show_resource_history(request=request)
            revisions = response.items
        except exceptions.ClientRequestException as ex:
            self.log.exception(
                f"Cannot show resource history of resource {resource['id']}, "
                f"RequestId: {ex.request_id}, Reason: {ex.error_msg}")
            revisions = []
        return revisions

    def get_selector_params(self, resource):
        resource_id = resource["id"]
        selector = self.data.get('selector', 'previous')
        later_time = None
        limit = None
        if selector == 'date':
            if not self.selector_value:
                self.selector_value = parse_date(
                    self.data.get('selector_value'))
            later_time = self.selector_value
            limit = 3
        elif selector == 'previous':
            limit = 2
        elif selector == 'locked':
            later_time = resource.get('locked_date')
            limit = 2
        request = ShowResourceHistoryRequest(resource_id=resource_id, later_time=later_time,
                                             limit=limit)
        return request

    def select_revision(self, revisions):
        for rev in revisions:
            # convert unix timestamp to utc to be normalized with other dates
            if rev.capturn_time.tzinfo and \
                    isinstance(rev.capturn_time.tzinfo, tzlocal):
                rev.capturn_time = rev.capturn_time.astimezone(UTC)
            return {
                'date': rev.capturn_time,
                'resource': rev.resource}

    def diff(self, source, target):
        raise NotImplementedError("Subclass responsibility")


class JsonDiff(Diff):
    schema = type_schema(
        'json-diff',
        selector={'enum': ['previous', 'date', 'locked']},
        # For date selectors allow value specification
        selector_value={'type': 'string'})

    def diff(self, source, target):
        source, target = (
            self.sanitize_revision(source), self.sanitize_revision(target))
        patch = jsonpatch.JsonPatch.from_diff(source, target)
        return list(patch)

    def sanitize_revision(self, rev):
        sanitized = dict(rev)
        for k in [k for k in sanitized if 'huaweicloud' in k]:
            sanitized.pop(k)
        return sanitized

    @classmethod
    def register_resources(klass, registry, resource_class):
        """ meta model subscriber on resource registration.

        We watch for new resource types being registered and if they
        support aws config, automatically register the jsondiff filter.
        """
        resource_class.filter_registry.register('json-diff', klass)


if HAVE_JSONPATH:
    resources.subscribe(JsonDiff.register_resources)
