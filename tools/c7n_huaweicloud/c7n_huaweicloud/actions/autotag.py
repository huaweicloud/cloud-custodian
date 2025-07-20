# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
import logging
from c7n.actions import EventAction
from c7n.exceptions import PolicyValidationError
from c7n import utils

from c7n_huaweicloud.provider import resources

DEFAULT_TAG = "auto-tag-user-key"


class AutoTagUser(EventAction):
    """Tag a resource with the user who created/modified it.

    .. code-block:: yaml

      policies:
        - name: resource-auto-tag-ownercontact
          resource: resource
          description: |
            Triggered when a new resource Instance is launched. Checks to see if
            it's missing the OwnerContact tag. If missing it gets created
            with the value of the ID of whomever called the RunInstances API
          mode:
            type: cloudtracker
            xrole: fgs_admin
            eg_agency: EG_TARGET_AGENCY
            default_region: cn-north-4
            events:
              - source: "FunctionGraph"
                event: "createFunction"
                ids: "resource_name"
          actions:
           - type: auto-tag-user
             tag: OwnerContact

    There's a number of caveats to usage. Resources which don't
    include tagging as part of their api may have some delay before
    automation kicks in to create a tag. Real world delay may be several
    minutes, with worst case into hours[0]. This creates a race condition
    between auto tagging and automation.

    In practice this window is on the order of a fraction of a second, as
    we fetch the resource and evaluate the presence of the tag before
    attempting to tag it.

    """  # NOQA

    log = logging.getLogger("custodian.actions.auto-tag-user")

    schema = utils.type_schema(
        'auto-tag-user',
        required=['tag'],
        **{'user-type': {
            'type': 'array',
            'items': {'type': 'string',
                      'enum': [
                          'User',
                          'AssumedAgency',
                          'ExternalUser'
                      ]}},
            'update': {'type': 'boolean'},
            'tag': {'type': 'string'},
            'principal_id_tag': {'type': 'string'},
            'value': {'type': 'string',
                      'enum': [
                          'userName',
                          'sourceIPAddress',
                          'principalId'
                      ]},
        }
    )

    def validate(self):
        if self.manager.data.get('mode', {}).get('type') != 'cloudtrace':
            raise PolicyValidationError(
                "Auto tag owner requires an event %s" % (self.manager.data,))
        if self.manager.action_registry.get('tag') is None:
            raise PolicyValidationError(
                "Resource does not support tagging %s" % (self.manager.data,))
        if 'tag' not in self.data:
            raise PolicyValidationError(
                "auto-tag action requires 'tag'")
        return self

    def get_user_info_value(self, utype, event_data):
        value = None
        user_info = event_data['user']
        vtype = self.data.get('value', None)
        if vtype is None:
            return

        if vtype == "userName":
            if utype == "User":
                value = user_info.get('name', '')
            elif utype == "AssumedAgency" or utype == "ExternalUser":
                value = user_info.get('name', '')
        elif vtype == "sourceIPAddress":
            value = event_data.get('source_ip', '')
        elif vtype == "principalId":
            value = user_info.get('principal_id', '')

        return value

    def get_tag_value(self, event_data):
        user_info = event_data['user']
        utype = user_info.get('type', None)
        if utype not in self.data.get('user-type', ['AssumedAgency', 'User', 'ExternalUser']):
            return

        user = None
        principal_id_value = None
        if utype == "User":
            user = user_info.get('name', None)
            principal_id_value = user_info.get('principal_id', '')
        elif utype == "AssumedAgency" or utype == "ExternalUser":
            user = user_info.get('name', None)
            principal_id_value = user_info.get('principal_id', '')

        value = self.get_user_info_value(utype, event_data)

        # if the auto-tag-user policy set update to False (or it's unset) then we
        return {'user': user, 'id': principal_id_value, 'value': value}

    def process(self, resources, event):
        event_data = event.get("cts", None)
        if event_data is None:
            return
        user_info = self.get_tag_value(event_data)
        if user_info is None:
            self.log.warning("user info not found in event")
            return

        # will skip writing their UserName tag and not overwrite pre-existing values
        if not self.data.get('update', False):
            untagged_resources = []
            # iterating over all the resources the user spun up in this event
            for resource in resources:
                tags = self.get_tags_from_resource(resource)
                if self.data.get("tag", DEFAULT_TAG) not in tags:
                    untagged_resources.append(resource)
        # if update is set to True, we will overwrite the userName tag even if
        # the user already set a value
        else:
            untagged_resources = resources

        new_tags = {}
        if user_info['value']:
            new_tags[self.data['tag']] = user_info['value']
        elif user_info['user']:
            new_tags[self.data['tag']] = user_info['user']

        # if principal_id_key is set (and value), we'll set the principalId tag.
        principal_id_key = self.data.get('principal_id_tag', None)
        if principal_id_key and user_info['id']:
            new_tags[principal_id_key] = user_info['id']

        if new_tags:
            self.set_resource_tags(new_tags, untagged_resources)
        return new_tags

    def set_resource_tags(self, tags, resources):
        tag_action = self.manager.action_registry.get('tag')
        for key, value in tags.items():
            actual_value = value.replace(":", "_").replace("/", "_")
            tag_action({'key': key, 'value': actual_value}, self.manager).process(resources)

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
            self.log.warning("Parse tags in resource %s failed", resource["id"])
            return {}

    @classmethod
    def register_resource(cls, registry, resource_class):
        if 'auto-tag-user' in resource_class.action_registry:
            return
        if resource_class.action_registry.get('tag'):
            resource_class.action_registry.register('auto-tag-user', AutoTagUser)


resources.subscribe(AutoTagUser.register_resource)
