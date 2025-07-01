import functools
import json
import logging

from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkiam.v3 import (UpdateLoginProtectRequest, UpdateLoginProjectReq,
    ShowUserLoginProtectRequest, UpdateLoginProject)
from huaweicloudsdkiam.v5 import (DeletePolicyV5Request, ListAttachedUserPoliciesV5Request,
    DetachUserPolicyV5Request, DetachUserPolicyReqBody, DeleteUserV5Request,
    AddUserToGroupV5Request, AddUserToGroupReqBody, RemoveUserFromGroupV5Request,
    RemoveUserFromGroupReqBody, UpdateAccessKeyV5Request, UpdateAccessKeyReqBody,
    AccessKeyStatus, DeleteAccessKeyV5Request, ListMfaDevicesV5Request, ListAccessKeysV5Request,
    GetPolicyVersionV5Request)

from c7n.filters import ValueFilter
from c7n.utils import type_schema, chunks, local_session
from c7n_huaweicloud.actions import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

log = logging.getLogger("custodian.huaweicloud.resources.iam")


@resources.register('iam-user')
class User(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'iam-user'
        enum_spec = ("list_users_v5", 'users', 'marker')
        id = 'user_id'


@resources.register('iam-policy')
class Policy(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'iam-policy'
        enum_spec = ("list_policies_v5", 'policies', 'marker')
        id = 'policy_id'


@Policy.action_registry.register('delete')
class PolicyDelete(HuaweiCloudBaseAction):
    """Delete an IAM Policy.

    For example, if you want to automatically delete all unused IAM policies.

    :example:

      .. code-block:: yaml
        policies:
          - name: iam-delete-unused-policies
            resource: huaweicloud.iam-policy
            filters:
              - type: unused
            actions:
              - delete

    """
    schema = type_schema('delete')

    def perform_action(self, resource):
        client = self.manager.get_client()
        try:
            if resource['policy_type'] == 'custom':
                client.delete_policy_v5(DeletePolicyV5Request(policy_id=resource['policy_id']))
                log.info(f"Successfully detached policy: {resource['policy_id']}")
        except exceptions.ClientRequestException as e:
            log.error(f"Failed detached policy: {resource['policy_id']},"
                      f" status_code:{e.status_code}, request_id:{e.request_id},"
                      f" error_code:{e.error_code}, error_msg:{e.error_msg}")
        except Exception as e:
            log.error(f"Unexpected error: {e}")


@User.action_registry.register('delete')
class UserDelete(HuaweiCloudBaseAction):
    """Delete a user.

    :Example:

    .. code-block:: yaml

        policies:
          - name: delete-user
            resource: huaweicloud.iam-user
            filters:
              - type: access-key
                key: status
                value: active
              - type: access-key
                key: created_at
                value_type: age
                value: 90
                op: gt
            actions:
              - delete
    """

    schema = type_schema('delete')

    def perform_action(self, resource):
        if resource["is_root_user"]:
            log.warning("Root user is not delete.")
            return
        client = self.manager.get_client()
        try:
            request = ListAttachedUserPoliciesV5Request(
                user_id=resource["id"], limit=200)
            response = client.list_attached_user_policies_v5(request)
            policy_ids = [policy.policy_id for policy in response.attached_policies]

            for policy_id in policy_ids:
                try:
                    request = DetachUserPolicyV5Request(policy_id=policy_id)
                    request.body = DetachUserPolicyReqBody(user_id=resource["id"])
                    client.detach_user_policy_v5(request)
                    log.info(f"Successfully detached policy: {policy_id}")
                except exceptions.ClientRequestException as e:
                    log.error(f"Failed to detach policy {policy_id}: {e.error_msg}")

            request = DeleteUserV5Request(user_id=resource["id"])
            response = client.delete_user_v5(request)
            if response.status_code == 204:
                log.info(f"Successfully deleted user: {resource['id']}")
            else:
                log.error(f"Failed to delete user: {resource['id']}. "
                      f"Status code: {response.status_code}")
        except exceptions.ClientRequestException as e:
            log.error(f"status_code:{e.status_code}, request_id:{e.request_id},"
                      f" error_code:{e.error_code}, error_msg:{e.error_msg}")
        except Exception as e:
            log.error(f"Unexpected error: {e}")


@User.action_registry.register('set-group')
class SetGroup(HuaweiCloudBaseAction):
    """Set user to group.

    :Example:

    .. code-block:: yaml

        policies:
          - name: set-group
            resource: huaweicloud.iam-user
            filters:
              - type: access-key
                key: status
                value: active
              - type: access-key
                key: created_at
                value_type: age
                value: 90
                op: gt
            actions:
              - type: set-groups
                state: remove
                group_id: aba123xxxxxxxxxxxd1ss1fd
    """

    schema = type_schema(
        'set-group',
        state={'enum': ['add', 'remove']},
        group_id={'type': 'string'},
        required=['state', 'group_id']
    )

    def perform_action(self, resource):
        group_id = self.data.get('group_id')
        user_id = resource["id"]
        state = self.data['state']
        client = self.manager.get_client()
        try:
            if state == 'add':
                request = AddUserToGroupV5Request(group_id=group_id)
                request.body = AddUserToGroupReqBody(user_id=user_id)
                client.add_user_to_group_v5(request)
                log.info(f"add user to group success, user id: {user_id}")
            elif state == 'remove':
                request = RemoveUserFromGroupV5Request(group_id=group_id)
                request.body = RemoveUserFromGroupReqBody(user_id=user_id)
                client.remove_user_from_group_v5(request)
                log.info(f"remove user from group success, user id: {user_id}")
        except exceptions.ClientRequestException as e:
            log.error(f"status_code:{e.status_code}, request_id:{e.request_id},"
                      f" error_code:{e.error_code}, error_msg:{e.error_msg}")
        except Exception as e:
            log.error(f"Unexpected error: {e}")


@User.action_registry.register('remove-access-key')
class UserRemoveAccessKey(HuaweiCloudBaseAction):
    """Remove user's access-key or disable user's access-key.

    :Example:

    .. code-block:: yaml

        policies:
          - name: UserRemoveAccessKey
            resource: huaweicloud.iam-user
            filters:
              - type: access-key
                key: status
                value: active
              - type: access-key
                key: created_at
                value_type: age
                value: 90
                op: gt
            actions:
              - type: remove-access-key
                disable: true
    """

    schema = type_schema(
        'remove-access-key',
        disable={'type': 'boolean'})

    def perform_action(self, resource):
        client = self.manager.get_client()
        try:
            for key in resource["c7n:matched_keys"]:
                if self.data.get('disable'):
                    request = UpdateAccessKeyV5Request(
                        user_id=resource["id"],
                        access_key_id=key['access_key_id'])
                    request.body = UpdateAccessKeyReqBody(
                        status=AccessKeyStatus.INACTIVE)
                    client.update_access_key_v5(request)
                    log.info(f"disable access key success, access key id: {key['access_key_id']}")
                else:
                    request = DeleteAccessKeyV5Request(
                        user_id=resource["id"],
                        access_key_id=key['access_key_id'])
                    client.delete_access_key_v5(request)
                    log.info(f"delete access key success, access key id: {key['access_key_id']}")
        except exceptions.ClientRequestException as e:
            log.error(f"status_code:{e.status_code}, request_id:{e.request_id},"
                      f" error_code:{e.error_code}, error_msg:{e.error_msg}")
        except Exception as e:
            log.error(f"Unexpected error: {e}")


@User.action_registry.register('set-login-protect')
class SetLoginProtect(HuaweiCloudBaseAction):
    """Set IAMUser Login Protect.

    :Example:

    .. code-block:: yaml

        policies:
          - name: set-user-login-protect
            resource: huaweicloud.iam-user
            filters:
              - type: access-key
                key: status
                value: active
              - type: access-key
                key: created_at
                value_type: age
                value: 90
                op: gt
            actions:
              - type: set-login-protect
                enabled: true
                verification_method: vmfa
    """

    schema = type_schema(
        'set-login-protect',
        enabled={'type': 'boolean'},
        verification_method={'type': 'string'},
    )

    def perform_action(self, resource):
        client = local_session(self.manager.session_factory).client("iam-v3")
        try:
            request = UpdateLoginProtectRequest(user_id=resource["id"])

            loginProtectBody = UpdateLoginProject(
                enabled=self.data.get('enabled'),
                verification_method=self.data.get('verification_method')
            )
            request.body = UpdateLoginProjectReq(login_protect=loginProtectBody)

            response = client.update_login_protect(request)
            log.info(response)
        except exceptions.ClientRequestException as e:
            log.error(f"status_code:{e.status_code}, request_id:{e.request_id},"
                      f" error_code:{e.error_code}, error_msg:{e.error_msg}")
        except Exception as e:
            log.error(f"Unexpected error: {e}")


"""------------------------------------filter---------------------------------------"""


# login-protect filter for iam-users
@User.filter_registry.register('login-protect')
class UserLoginProtect(ValueFilter):
    """Filter iam-users based on login-protect

    :example:

    .. code-block:: yaml

        policies:
          - name: login-protect-enabled-users
            resource: huaweicloud.iam-user
            filters:
              - type: login-protect
                key: enabled
                value: true
            actions:
              - type: set-login-protect
                enabled: false
                verification_method: vmfa
    """

    schema = type_schema('login-protect',
                         key={'enum': ['enabled', 'verification_method']})
    annotation_key = 'login_protect'
    matched_annotation_key = 'c7n:matched_login_protect'
    schema_alias = False

    def _user_login_protect(self, resource):
        try:
            client = local_session(self.manager.session_factory).client("iam-v3")
            request = ShowUserLoginProtectRequest(user_id=resource["id"])
            response = client.show_user_login_protect(request)
            login_protect = response.login_protect
            resource[self.annotation_key] = {
                'verification_method': login_protect.verification_method,
                'enabled': login_protect.enabled
            }
        except exceptions.ClientRequestException as e:
            if not (e.status_code == 404 and e.error_code == 'IAM.0004'):
                log.error(f"status_code:{e.status_code}, request_id:{e.request_id},"
                          f" error_code:{e.error_code}, error_msg:{e.error_msg}")
                resource[self.annotation_key] = {}
        except Exception as e:
            resource[self.annotation_key] = {}
            log.error(f"Unexpected error: {e}")

    def process(self, resources, event=None):
        matched = []
        try:
            with self.executor_factory(max_workers=2) as w:
                query_resources = [
                    r for r in resources if self.annotation_key not in r]
                list(w.map(self._user_login_protect, query_resources))

            for user in resources:
                login_protect = user.get(self.annotation_key, {})
                if (self.data.get('key') == 'login_protect'
                        and self.data.get('value') == 'none'
                        and not login_protect):
                    matched.append(user)
                else:
                    if self.match(login_protect):
                        self.merge_annotation(user, self.matched_annotation_key, login_protect)
                        matched.append(user)
        except exceptions.ClientRequestException as e:
            log.error(f"status_code:{e.status_code}, request_id:{e.request_id},"
                      f" error_code:{e.error_code}, error_msg:{e.error_msg}")
        except Exception as e:
            log.error(f"Unexpected error: {e}")
        return matched or []


# Mfa-device filter for iam-users
@User.filter_registry.register('mfa-device')
class UserMfaDevice(ValueFilter):
    """Filter iam-users based on mfa-device status

    :example:

    .. code-block:: yaml

        policies:
          - name: mfa-enabled-users
            resource: huaweicloud.iam-user
            filters:
              - type: mfa-device
                key: enabled
                value: true
    """

    schema = type_schema('mfa-device',
                         key={'enum': ['enabled', 'serial_number']})
    annotation_key = 'mfa_devices'
    matched_annotation_key = 'c7n:matched_mfa_devices'
    schema_alias = False

    def _user_mfa_devices(self, resource):
        try:
            client = self.manager.get_client()
            request = ListMfaDevicesV5Request(user_id=resource["id"])
            mfa_devices = client.list_mfa_devices_v5(request).mfa_devices
            resource[self.annotation_key] = [
                {
                    'serial_number': mfa.serial_number,
                    'enabled': mfa.enabled
                }
                for mfa in mfa_devices
            ]
        except Exception as e:
            self.log.warning(f"Failed to query MFA for user {resource['id']}: {str(e)}")
            resource[self.annotation_key] = []

    def process(self, resources, event=None):
        matched = []
        try:
            with self.executor_factory(max_workers=2) as w:
                query_resources = [
                    r for r in resources if self.annotation_key not in r]
                list(w.map(self._user_mfa_devices, query_resources))

            for user in resources:
                devices = user.get(self.annotation_key, []) or []
                if (self.data.get('key') == 'mfa_devices'
                        and self.data.get('value') == 'none'
                        and len(devices) == 0):
                    matched.append(user)
                else:
                    matched_devices = [d for d in devices if self.match(d)]
                    self.merge_annotation(user, self.matched_annotation_key, matched_devices)
                    if matched_devices:
                        matched.append(user)
        except exceptions.ClientRequestException as e:
            log.error(f"status_code:{e.status_code}, request_id:{e.request_id},"
                      f" error_code:{e.error_code}, error_msg:{e.error_msg}")
        except Exception as e:
            log.error(f"Unexpected error: {e}")
        return matched or []


@User.filter_registry.register('policy')
class UserPolicy(ValueFilter):
    """Filter IAM users based on attached policy values

    :example:

    .. code-block:: yaml

        policies:
          - name: iam-users-with-admin-access
            resource: huaweicloud.iam-user
            filters:
              - type: policy
                key: Policy_id
                value: xxxx
    """
    schema = type_schema('policy',
                         key={'enum': ['policy_name', 'policy_id', 'urn', 'attached_at']})
    annotation_key = 'attached_policies'
    matched_annotation_key = 'c7n:matched_attached_policies'
    schema_alias = False

    def get_user_policies(self, client, user_set):
        for u in user_set:
            try:
                request = ListAttachedUserPoliciesV5Request(
                    user_id=u['user_id'], limit=200)
                response = client.list_attached_user_policies_v5(request)
                attached_policies = response.attached_policies
                u[self.annotation_key] = [
                    {
                        'policy_name': key.policy_name,
                        'policy_id': key.policy_id,
                        'urn': key.urn,
                        'attached_at': key.attached_at.isoformat()
                    }
                    for key in attached_policies
                ]
            except Exception as e:
                log.error(f"Failed to list attached policies for user {u['user_id']}: {e}")
                u[self.annotation_key] = []

    def process(self, resources, event=None):
        client = self.manager.get_client()
        with self.executor_factory(max_workers=2) as w:
            augment_set = [r for r in resources if self.annotation_key not in r]
            list(w.map(
                functools.partial(self.get_user_policies, client),
                chunks(augment_set, 50)))

        matched = []
        for r in resources:
            keys = r[self.annotation_key]
            k_matched = []
            for k in keys:
                if self.match(k):
                    k_matched.append(k)
            for k in k_matched:
                k['c7n:match-type'] = 'policies'
            self.merge_annotation(r, self.matched_annotation_key, k_matched)
            if k_matched:
                matched.append(r)

        return matched


@User.filter_registry.register('access-key')
class UserAccessKey(ValueFilter):
    """Filter IAM users based on access-key values

    By default multiple uses of this filter will match
    on any user key satisfying either filter. To find
    specific keys that match multiple access-key filters,
    use `match-operator: and`

    :example:

    .. code-block:: yaml

        policies:
          - name: iam-users-with-active-keys-or-created_at
            resource: huaweicloud.iam-user
            filters:
              - or:
                - type: access-key
                  key: status
                  value: active
                - type: access-key
                  key: created_at
                  value_type: age
                  value: 90
                  op: gt

        policies:
          - name: iam-users-with-active-keys-or-created_at
            resource: huaweicloud.iam-user
            filters:
              - type: access-key
                key: status
                value: active
              - type: access-key
                key: size
                value: 1
    """

    schema = type_schema('access-key',
                         key={'enum': ['access_key_id', 'status', 'created_at']})
    schema_alias = False
    annotation_key = 'access_keys'
    matched_annotation_key = 'c7n:matched_keys'
    annotate = False

    def get_user_keys(self, client, user_set):
        for u in user_set:
            try:
                response = client.list_access_keys_v5(
                    ListAccessKeysV5Request(user_id=u['user_id']))
                access_keys = response.access_keys
                u[self.annotation_key] = [
                    {
                        'access_key_id': key.access_key_id,
                        'status': key.status,
                        'created_at': key.created_at.isoformat()
                    }
                    for key in access_keys
                ]
            except Exception as e:
                log.error(f"Failed to list access keys for user {u['user_id']}: {e}")
                u[self.annotation_key] = []

    def process(self, resources, event=None):
        client = self.manager.get_client()
        with self.executor_factory(max_workers=2) as w:
            augment_set = [r for r in resources if self.annotation_key not in r]
            list(w.map(
                functools.partial(self.get_user_keys, client),
                chunks(augment_set, 50)))

        matched = []
        for r in resources:
            keys = r[self.annotation_key]
            if (self.data.get('key') == 'size'
                    and len(keys) == self.data.get('value')):
                matched.append(r)
            else:
                k_matched = []
                for k in keys:
                    if self.match(k):
                        k_matched.append(k)
                for k in k_matched:
                    k['c7n:match-type'] = 'access'
                self.merge_annotation(r, self.matched_annotation_key, k_matched)
                if k_matched:
                    matched.append(r)

        return matched


@Policy.filter_registry.register('has-allow-all')
class AllowAllIamPolicies(ValueFilter):
    """Check if IAM policy resource(s) have allow-all IAM policy statement block.

    Policy must have 'Action' and Resource = '*' with 'Effect' = 'Allow'

    The policy will trigger on the following IAM policy (statement).
    For example:

    .. code-block:: json

      {
          "Version": "2012-10-17",
          "Statement": [{
              "Action": "*",
              "Resource": "*",
              "Effect": "Allow"
          }]
      }

    Additionally, the policy checks if the statement has no 'Condition' or
    'NotAction'.

    For example, if the user wants to check all used policies and filter on
    allow all:

    .. code-block:: yaml
        policies:
         - name: iam-no-used-all-all-policy
           resource: huaweicloud.iam-policy
           filters:
             - type: used
             - type: has-allow-all

    Note that scanning and getting all policies and all statements can take
    a while. Use it sparingly or combine it with filters such as 'used' as
    above.

    """

    schema = type_schema('has-allow-all')

    def has_allow_all_policy(self, client, resource):
        document = client.get_policy_version_v5(GetPolicyVersionV5Request(
            policy_id=resource.get('policy_id'),
            version_id=resource.get('default_version_id'))
        ).policy_version.document

        statements = json.loads(document).get('Statement')
        if isinstance(statements, dict):
            statements = [statements]

        for s in statements:
            if ('Condition' not in s and
                    'NotResource' not in s and
                    'Action' in s and
                    isinstance(s['Action'], list) and
                    ("*" in s['Action'] or
                     "*:*:*" in s['Action']) and
                    ('Resource' not in s or
                     'Resource' in s and
                     isinstance(s['Resource'], list) and
                     "*" in s['Resource'] or
                     "*:*:*:*:*" in s['Resource']) and
                    s['Effect'] == "Allow"):
                return True
        return False

    def process(self, resources, event=None):
        client = self.manager.get_client()
        results = [r for r in resources if self.has_allow_all_policy(client, r)]
        self.log.info(
            "%s of %s iam policies have allow all.",
            len(results), len(resources))
        for res in results:
            self.log.info("allow all iam policy id: %s", res['policy_id'])
        return results


@Policy.filter_registry.register('unused')
class UnusedIamPolicies(ValueFilter):
    """Filter IAM policies that are not being used

    :example:

    .. code-block:: yaml

        policies:
          - name: iam-policy-unused
            resource: huaweicloud.iam-policy
            filters:
              - type: unused
    """

    schema = type_schema('unused')

    def process(self, resources, event=None):
        return [r for r in resources if
                r['attachment_count'] == 0]


@Policy.filter_registry.register('used')
class UsedIamPolicies(ValueFilter):
    """Filter IAM policies that are being used

    :example:

    .. code-block:: yaml

        policies:
          - name: iam-policy-used
            resource: huaweicloud.iam-policy
            filters:
              - type: used
    """

    schema = type_schema('used')

    def process(self, resources, event=None):
        return [r for r in resources if
                r['attachment_count'] > 0]
