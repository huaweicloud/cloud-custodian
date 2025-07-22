# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import json
import copy
import re

from huaweicloudsdkcore.exceptions import exceptions

from obs import ACL

from c7n.utils import type_schema, set_annotation, local_session,\
format_string_values
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

from c7n.filters import Filter

log = logging.getLogger("custodian.huaweicloud.resources.obs")


@resources.register('obs')
class Obs(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'obs'
        enum_spec = ("listBuckets", 'body.buckets', None)
        id = 'name'
        tag = False

    def augment(self, resources):
        resources = super().augment(resources)

        log.debug('[obs resource manager]-filter resource in this region.')
        current_region_buckets = filter_region_bucket(self.session_factory, resources)

        log.info('[obs resource manager]-try to get bucket tags.')
        with self.executor_factory(max_workers=5) as w:
            buckets = w.map(self.get_bucket_tags, current_region_buckets)
            buckets = list(filter(None, list(buckets)))
            log.debug('[obs resource manager]: bucket resources: %s' % buckets)
            return buckets

    def get_bucket_tags(self, bucket):
        client = get_obs_client(self.session_factory, bucket)
        resp = client.getBucketTagging(bucket['name'])
        if resp.status < 300:
            bucket['tags'] = [{'key': tag.key, 'value': tag.value if tag.value is not None else ''}
                               for tag in resp.body.get('tagSet', [])]
            return bucket
        else:
            if 'NoSuchTagSet' == resp.errorCode:
                bucket['tags'] = []
                return bucket

            log.error('[obs resource manager] query bucket:[%s] bucket tags is failed. cause: %s'
                  % (bucket['name'], resp.reason))
            raise_exception(resp, 'getBucketTagging', bucket)


class ObsSdkError():
    def __init__(self, code, message, request_id):
        self.error_code = code
        self.error_msg = message
        self.request_id = request_id
        self.encoded_auth_msg = ""


def get_obs_client(session_factory, bucket):
    session = local_session(session_factory)
    client = session.region_client(Obs.resource_type.service, bucket['location'])
    return client


def filter_region_bucket(session_factory, buckets):
    session = local_session(session_factory)
    current_region = session.region

    filtered_buckets = []
    for bucket in buckets:
        if bucket.get('location') == current_region:
            filtered_buckets.append(bucket)

    return filtered_buckets


def raise_exception(resp, method, bucket):
    log.error({"invoke method [": method, "] failed for bukcet ": bucket['name'],
               "request reason is ": resp.reason, " request id is": resp.requestId})
    sdk_error = ObsSdkError(resp.errorCode, resp.errorMessage, resp.requestId)
    raise exceptions.ClientRequestException(resp.status, sdk_error)


@Obs.action_registry.register('delete-wildcard-statements')
class DeleteWildcardStatement(HuaweiCloudBaseAction):
    """Action to delete wildcard policy statements from obs buckets

    :example:

    .. code-block:: yaml

            policies:
              - name: remove-wildcard-statements
                resource: huaweicloud.obs
                filters:
                  - type: wildcard-statements
                actions:
                  - type: delete-wildcard-statements
    """

    schema = type_schema('delete-wildcard-statements')

    def perform_action(self, bucket):
        bucket_name = bucket['name']
        p = bucket.get('Policy')
        if p is None:
            return

        if bucket.get(WildcardStatementFilter.annotation_key) is None:
            log.info("bucket %s has not wildcard policy" % bucket_name)
            return

        p = json.loads(p)
        new_statements = self.process_policy(p.get('Statement', []), bucket_name)

        p['Statement'] = new_statements
        self.update_statements(bucket, p)

        bucket['State'] = 'delete-wildcard-statements'
        bucket['newStatements'] = new_statements
        return bucket

    def process_policy(self, bucket_statements, bucket_name):
        new_statements = []
        for statement in bucket_statements:
            if statement.get('Effect') == 'Deny':
                log.info('[filters]-[wildcard-statements] current bucket[%s] statement[%s]'
                ' is Deny statment.' % (bucket_name, statement.get('Sid', '')))
                new_statements.append(statement)
                continue

            prinicipal_user = statement.get('Principal', {}).get("ID", [])
            action = statement.get('Action', [])
            if any("*" in s for s in prinicipal_user + action):
                continue

            new_statements.append(statement)

        return new_statements

    def update_statements(self, bucket, policy):
        bucket_name = bucket['name']
        client = get_obs_client(self.manager.session_factory, bucket)

        if not policy['Statement']:
            log.info('[actions]-[delete-wildcard-statements] try to delete ' +
                     'bucket resource [%s] bucket policy.' % (bucket_name))
            resp = client.deleteBucketPolicy(bucket_name)
        else:
            log.info('[actions]-[delete-wildcard-statements] try to put ' +
            'bucket resource [%s] bucket policy.' % (bucket_name))
            resp = client.setBucketPolicy(bucket_name, json.dumps(policy))

        if resp.status > 300:
            log.error('[actions]-[delete-wildcard-statements] The resource:[bucket]' +
            ' with id:[%s] update bucket policy is failed. cause: %s'
            % (bucket_name, resp.reason))
            raise_exception(resp, 'updateBucketPolicy', bucket)
        else:
            log.info('[actions]-[delete-wildcard-statements] The resource:[bucket]' +
            ' with id:[%s] update bucket policy is success.' % bucket_name)


@Obs.action_registry.register('set-bucket-encryption')
class SetBucketEncryption(HuaweiCloudBaseAction):
    """Enabling obs bucket encryption

    :example:

    .. code-block:: yaml

        policies:
            - name: encryption-bucket
              resource: huaweicloud.obs
              filters:
                - type: bucket-encryption
                  state: False
              actions:
                - type: set-bucket-encryption
                  crypto: AES256

    """
    schema = type_schema(
        'set-bucket-encryption',
        required=['encryption'],
        encryption={
            'type': 'object',
            'oneOf': [
                {
                    'required': ['crypto'],
                    'properties': {
                        'crypto': {'enum': ['AES256']}
                    }
                },
                {
                    'required': ['crypto'],
                    'properties': {
                        'crypto': {'enum': ['kms']},
                        'key': {'type': 'string'},
                        'kms_data_encryption': {'enum': ['SM4']}
                    }
                }
            ]
        }
    )

    def perform_action(self, bucket):
        bucket_name = bucket['name']

        cfg = self.data['encryption']

        client = get_obs_client(self.manager.session_factory, bucket)
        if cfg['crypto'] == 'AES256':
            resp = client.setBucketEncryption(bucket_name, 'AES256')
        else:
            key_id = cfg.get('key', None)
            if not key_id:
                resp = client.setBucketEncryption(bucket_name, 'kms')
            else:
                resp = client.setBucketEncryption(bucket_name, 'kms', key_id)

        if resp.status < 300:
            bucket['State'] = 'set-bucket-encryption'
            log.info('[actions]-[set-bucket-encryption] The resource:[bucket]' +
            ' with id:[%s] set bucket encryption is success.' % bucket_name)
        else:
            log.error('[actions]-[set-bucket-encryption] The resource:[bucket]' +
            ' with id:[%s] set bucket encryption is failed. cause: %s'
            % (bucket_name, resp.reason))
            raise_exception(resp, 'setBucketEncryption', bucket)


@Obs.action_registry.register('delete-global-grants')
class DeleteGlobalGrants(HuaweiCloudBaseAction):
    """Deletes global grants associated to a obs bucket

    :example:

    .. code-block:: yaml

            policies:
              - name: obs-delete-global-grants
                resource: huaweicloud.obs
                filters:
                  - type: global-grants
                actions:
                  - type: delete-global-grants

    """

    schema = type_schema(
        'delete-global-grants')

    def perform_action(self, bucket):
        acl = bucket.get('Acl', {'grants': []})
        if not acl or not acl['grants']:
            return

        new_acl = self.filter_grants(acl, bucket.get('website', False))
        self.update_bucket_acl(bucket, new_acl)

    def filter_grants(self, acl, is_website_bucket):
        new_grants = []
        for grant in acl['grants']:
            grantee = grant.get('grantee', {})
            if not grantee:
                continue

            if 'group' not in grantee:
                new_grants.append(grant)
                continue

            if grantee['group'] not in ['Everyone']:
                new_grants.append(grant)
                continue

            if grant['permission'] == 'READ' and is_website_bucket:
                new_grants.append(grant)
                continue

        owner = acl['owner']
        return ACL(owner, new_grants)

    def update_bucket_acl(self, bucket, acl):
        client = get_obs_client(self.manager.session_factory, bucket)
        resp = client.setBucketAcl(bucket['name'], acl)

        if resp.status < 300:
            log.info('[actions]-[delete-global-grants] The resource:[bucket]' +
            ' with id:[%s] set bucket acl is success.' % bucket['name'])
        else:
            log.error('[actions]-[delete-global-grants] The resource:[bucket]' +
            ' with id:[%s] set bucket acl is failed. cause: %s'
            % (bucket['name'], resp.reason))
            raise_exception(resp, 'setBucketAcl', bucket)


@Obs.action_registry.register('set-public-block')
class SetPublicBlock(HuaweiCloudBaseAction):
    """Action to update Public Access blocks on obs buckets

    If no action parameters are provided all settings will be set to the `state`, which defaults

    If action parameters are provided, those will be set and other extant values preserved.

    :example:

    .. code-block:: yaml

            policies:
              - name: public-block-enable-all
                resource: huaweicloud.obs
                filters:
                  - type: check-public-block
                actions:
                  - type: set-public-block

            policies:
              - name: public-block-disable-all
                resource: huaweicloud.obs
                filters:
                  - type: check-public-block
                actions:
                  - type: set-public-block
                    state: false

            policies:
              - name: public-block-enable-some
                resource: huaweicloud.obs
                filters:
                  - or:
                    - type: check-public-block
                      blockPublicAcls: false
                    - type: check-public-block
                      blockPublicPolicy: false
                actions:
                  - type: set-public-block
                    blockPublicAcls: true
                    blockPublicPolicy: true
    """

    schema = type_schema(
        'set-public-block',
        state={'type': 'boolean', 'default': True},
        blockPublicAcls={'type': 'boolean'},
        ignorePublicAcls={'type': 'boolean'},
        blockPublicPolicy={'type': 'boolean'},
        restrictPublicBuckets={'type': 'boolean'})

    keys = (
        'blockPublicPolicy', 'blockPublicAcls', 'ignorePublicAcls', 'restrictPublicBuckets')
    annotation_key = 'c7n:PublicAccessBlock'

    def perform_action(self, bucket):
        bucket_name = bucket['name']

        client = get_obs_client(self.manager.session_factory, bucket)

        config = dict(bucket.get(self.annotation_key, {key: False for key in self.keys}))
        if self.annotation_key not in bucket:
            resp = client.getBucketPublicAccessBlock(bucket_name)
            if resp.status < 300:
                config = resp.body
                log.debug('[actions]-[set-public-block] The resource:[bucket]' +
            ' with id:[%s] get bucket public access block is success.' % bucket_name)
            else:
                log.error('[actions]-[set-public-block] The resource:[bucket]' +
            ' with id:[%s] get bucket public access block is failed. cause: %s'
            % (bucket_name, resp.reason))
                raise_exception(resp, 'getBucketPublicAccessBlock', bucket)

            bucket[self.annotation_key] = config

        key_set = [key for key in self.keys if key in self.data]
        if key_set:
            for key in key_set:
                config[key] = self.data.get(key)
        else:
            for key in self.keys:
                config[key] = self.data.get('state', True)

        resp = client.putBucketPublicAccessBlock(
            bucket_name, blockPublicAcls=config['blockPublicAcls'],
            ignorePublicAcls=config['ignorePublicAcls'],
            blockPublicPolicy=config['blockPublicPolicy'],
            restrictPublicBuckets=config['restrictPublicBuckets'])

        if resp.status < 300:
            log.info('[actions]-[set-public-block] The resource:[bucket]' +
            ' with id:[%s] set bucket public access block is success.' % bucket_name)
        else:
            log.error('[actions]-[set-public-block] The resource:[bucket]' +
            ' with id:[%s] set bucket public access block is failed. cause: %s'
            % (bucket_name, resp.reason))
            raise_exception(resp, 'putBucketPublicAccessBlosck', bucket)


@Obs.action_registry.register("set-statements")
class SetPolicyStatement(HuaweiCloudBaseAction):
    """Action to add or update policy statements to obs buckets

    :example:

    .. code-block:: yaml

            policies:
              - name: force-obs-https
                resource: huaweicloud.obs
                filters:
                  - type: support-https-request
                actions:
                  - type: set-statements
                    statements:
                      - Sid: "DenyHttp"
                        Effect: "Deny"
                        Action: "*"
                        Principal:
                          ID: "*"
                        Resource: "{bucket_name}/*"
                        Condition:
                          Bool:
                            "SecureTransport": false
    """

    schema = type_schema(
        'set-statements',
        **{
            'statements': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'Sid': {'type': 'string'},
                        'Effect': {'type': 'string', 'enum': ['Allow', 'Deny']},
                        'Principal': {'anyOf': [{'type': 'string'},
                            {'type': 'object'}, {'type': 'array'}]},
                        'NotPrincipal': {'anyOf': [{'type': 'object'}, {'type': 'array'}]},
                        'Action': {'anyOf': [{'type': 'string'}, {'type': 'array'}]},
                        'NotAction': {'anyOf': [{'type': 'string'}, {'type': 'array'}]},
                        'Resource': {'anyOf': [{'type': 'string'}, {'type': 'array'}]},
                        'NotResource': {'anyOf': [{'type': 'string'}, {'type': 'array'}]},
                        'Condition': {'type': 'object'}
                    },
                    'required': ['Sid', 'Effect'],
                    'oneOf': [
                        {'required': ['Principal', 'Action', 'Resource']},
                        {'required': ['NotPrincipal', 'Action', 'Resource']},
                        {'required': ['Principal', 'NotAction', 'Resource']},
                        {'required': ['NotPrincipal', 'NotAction', 'Resource']},
                        {'required': ['Principal', 'Action', 'NotResource']},
                        {'required': ['NotPrincipal', 'Action', 'NotResource']},
                        {'required': ['Principal', 'NotAction', 'NotResource']},
                        {'required': ['NotPrincipal', 'NotAction', 'NotResource']}
                    ]
                }
            }
        }
    )

    def perform_action(self, bucket):
        target_statements = format_string_values(
            copy.deepcopy({s['Sid']: s for s in self.data.get('statements', [])}),
            **self.get_std_format_args(bucket))

        policy = bucket.get('Policy') or '{}'
        if policy:
            policy = json.loads(policy)

        bucket_statements = policy.setdefault('Statement', [])

        new_statement = []
        for s in bucket_statements:
            if s.get('Sid') not in target_statements:
                new_statement.append(s)
                continue

        new_statement.extend(target_statements.values())
        policy['Statement'] = new_statement
        policy = json.dumps(policy)

        bucket['newPolicy'] = policy

        client = get_obs_client(self.manager.session_factory, bucket)
        resp = client.setBucketPolicy(bucket['name'], policy)
        if resp.status < 300:
            log.info('[actions]-[set-statements] The resource:[bucket]' +
            ' with id:[%s] set bucket policy is success.' % bucket['name'])
        else:
            log.error('[actions]-[set-statements] The resource:[bucket]' +
            ' with id:[%s] set bucket policy is failed. cause: %s'
            % (bucket['name'], resp.reason))
            raise_exception(resp, 'setBucketPolicy', bucket)

    def get_std_format_args(self, bucket):
        return {
            'bucket_name': bucket['name'],
            'bucket_region': bucket['location']
        }


@Obs.action_registry.register("remove-cross-account-config")
class RemoveCrossAccountAccessConfig(HuaweiCloudBaseAction):
    """delete cross-account access statements in obs bucket policy

        :example:

        .. code-block:: yaml

                policies:
                - name: remove-cross-account-access
                    resource: huaweicloud.obs
                    filters:
                      - type: cross-account
                    actions:
                      - type: remove-cross-account-config
        """
    schema = type_schema('remove-cross-account-config')

    annotation_policy_key = 'c7n:Statements'
    annotation_acl_key = 'c7n:Acl'

    def perform_action(self, bucket):
        p = bucket.get('Policy')
        if p is None:
            return

        client = get_obs_client(self.manager.session_factory, bucket)
        self.update_statements(bucket, client)
        self.update_acl(bucket, client)

        return bucket

    def update_statements(self, bucket, client):
        bucket_name = bucket['name']

        if bucket.get(self.annotation_policy_key) is None:
            log.info("[actions]-[remove-cross-account-config] bucket [%s] does " +
            "not need update bucket policy" % bucket_name)
            return

        if not bucket[self.annotation_policy_key]:
            log.info('[actions]-[remove-cross-account-config] try to delete ' +
            'bucket resource [%s] bucket policy.' % (bucket_name))
            resp = client.deleteBucketPolicy(bucket_name)
        else:
            log.info('[actions]-[remove-cross-account-config] try to put ' +
            'bucket resource [%s] bucket policy.' % (bucket_name))
            policy = {'Statement': bucket[self.annotation_policy_key]}
            resp = client.setBucketPolicy(bucket_name, json.dumps(policy))

        if resp.status > 300:
            log.error('[actions]-[remove-cross-account-config] The resource:[bucket]' +
            ' with id:[%s] update bucket policy is failed. cause: %s'
            % (bucket_name, resp.reason))
            raise_exception(resp, 'updateBucketPolicy', bucket)
        else:
            log.info('[actions]-[remove-cross-account-config] The resource:[bucket]' +
            ' with id:[%s] update bucket policy is success.' % bucket_name)

    def update_acl(self, bucket, client):
        bucket_name = bucket['name']

        if bucket.get(self.annotation_acl_key) is None:
            log.info("[actions]-[remove-cross-account-config] bucket"
            " %s does not need update acl" % bucket_name)
            return

        resp = client.setBucketAcl(bucket_name, bucket[self.annotation_acl_key])

        if resp.status > 300:
            log.error('[actions]-[remove-cross-account-config] The resource:[bucket]' +
            ' with id:[%s] set bucket acl is failed. cause: %s'
            % (bucket_name, resp.reason))
            raise_exception(resp, 'setBucketAcl', bucket)
        else:
            log.info('[actions]-[remove-cross-account-config] The resource:[bucket]' +
            ' with id:[%s] set bucket acl is success.' % bucket_name)


# ----------------------OBS Fileter-------------------------------------------

@Obs.filter_registry.register("wildcard-statements")
class WildcardStatementFilter(Filter):
    """Filters for all obs buckets that include wildcard principals in bucket policy.
    such as "Principal": "*", or wildcard actions, such as "Action": "*".

    :example:

    .. code-block:: yaml

       policies:
         - name: remove-wildcard-statements
           resource: huaweicloud.obs
           filters:
            - type: wildcard-statements
           actions:
            - delete-wildcard-statements

    """

    schema = type_schema('wildcard-statements')

    annotation_key = 'c7n:WildcardStatements'

    def process(self, buckets, event=None):
        filtered_buckets = filter_region_bucket(self.manager.session_factory, buckets)
        with self.executor_factory(max_workers=5) as w:
            results = w.map(self.process_bucket, filtered_buckets)
            results = list(filter(None, list(results)))
            return results

    def process_bucket(self, bucket):
        self.get_bucket_policy(bucket)
        return self.filter_include_wildcard_statement_bucket_policy(bucket)

    def filter_include_wildcard_statement_bucket_policy(self, bucket):
        policy = bucket.get('Policy') or '{}'
        if not policy:
            log.info("[filters]-The filter:[wildcard-statements] " +
            "bucket [%s] not config bucket policy" % (bucket['name']))
            return None

        policy = json.loads(policy)
        bucket_statements = policy.setdefault('Statement', [])

        result = []
        for statement in bucket_statements:
            if statement.get('Effect') == 'Deny':
                log.debug('[filters]-[wildcard-statements] current bucket[%s] statement[%s]'
                ' is Deny statment.' % (bucket['name'], statement.get('Sid', '')))
                continue

            prinicipal_user = statement.get('Principal', {}).get("ID", [])
            action = statement.get('Action', [])
            if any("*" in s for s in prinicipal_user + action):
                result.append(statement)

        if result:
            set_annotation(bucket, self.annotation_key, result)
            log.info("[filters]-[wildcard-statements] filter resource " +
            "with id:[%s] success." % (bucket['name']))
            return bucket

        return None

    def get_bucket_policy(self, bucket):
        client = get_obs_client(self.manager.session_factory, bucket)
        resp = client.getBucketPolicy(bucket['name'])

        if resp.status < 300:
            policy = resp.body.policyJSON
            bucket['Policy'] = policy
        else:
            if 'NoSuchBucketPolicy' == resp.errorCode or 'Not Found' == resp.reason:
                bucket['Policy'] = {}
                log.debug('[filters]-:[wildcard-statements]- bucket'
                ' [%s] not set bucket policy.' % (bucket['name']))
            else:
                log.error('[filters]-The filter:[wildcard-statements]' +
                ' query bucket:[%s] bucket policy is failed. cause: %s'
                  % (bucket['name'], resp.reason))
                raise_exception(resp, 'getBucketPolicy', bucket)


@Obs.filter_registry.register("bucket-encryption")
class BucketEncryptionStateFilter(Filter):
    """Filters OBS buckets that not encrypted

    :example:

    .. code-block:: yaml

        policies:
            - name: encryption-bucket
              resource: huaweicloud.obs
              filters:
                - type: bucket-encryption
                  state: False

    """

    schema = type_schema(
        'bucket-encryption',
        state={'type': 'boolean'},
        crypto={'enum': ['kms', 'AES256']},
        required=['state']
    )

    annotation_key = 'c7n:BucketEncryptionCrypto'

    def process(self, buckets, event=None):
        filtered_buckets = filter_region_bucket(self.manager.session_factory, buckets)
        with self.executor_factory(max_workers=5) as w:
            results = w.map(self.process_bucket, filtered_buckets)
            results = list(filter(None, list(results)))
            return results

    def process_bucket(self, bucket):
        target_state = self.data.get('state', False)
        target_crypto = self.data.get('crypto', None)

        current_crypto = self.get_encryption_crypto(bucket)
        bucket[self.annotation_key] = current_crypto

        if not target_state:
            if target_crypto is None and current_crypto is None:
                log.info("[filters]-[bucket-encryption] filter resource " +
            "with id:[%s] success." % (bucket['name']))
                return bucket

            if target_crypto is not None and target_crypto != current_crypto:
                log.info("[filters]-[bucket-encryption] filter resource " +
            "with id:[%s] success." % (bucket['name']))
                return bucket
        else:
            if target_crypto is None and current_crypto is not None:
                log.info("[filters]-[bucket-encryption] filter resource " +
            "with id:[%s] success." % (bucket['name']))
                return bucket

            if target_crypto is not None and current_crypto is not None \
            and target_crypto == current_crypto:
                log.info("[filters]-[bucket-encryption] filter resource " +
            "with id:[%s] success." % (bucket['name']))
                return bucket
        return None

    def get_encryption_crypto(self, bucket):
        client = get_obs_client(self.manager.session_factory, bucket)
        resp = client.getBucketEncryption(bucket['name'])

        if resp.status < 300:
            encryption = resp.body.encryption

            return encryption
        else:
            error_code = resp.errorCode
            if 'NoSuchEncryptionConfiguration' == error_code or 'Not Found' == resp.reason:
                log.debug('[filters]-:[bucket-encryption]- bucket'
                ' [%s]: not set bucket encryption.' % (bucket['name']))
                return None
            else:
                log.error('[filters]-The filter:[bucket-encryption]' +
                ' query bucket:[%s] bucket encryption is failed. cause: %s'
                  % (bucket['name'], resp.reason))
                raise_exception(resp, 'getBucketEncryption', bucket)


@Obs.filter_registry.register('global-grants')
class GlobalGrantsFilter(Filter):
    """Filters for all obs buckets that have global-grants

    *Note* by default this filter allows for read access
    if the bucket has been configured as a website. This
    can be disabled per the example below.

    :example:

    .. code-block:: yaml

       policies:
         - name: remove-global-grants
           resource: huaweicloud.obs
           filters:
            - type: global-grants
           actions:
            - type: delete-global-grants

    """

    schema = type_schema(
        'global-grants',
        operator={'type': 'string', 'enum': ['or', 'and']},
        allow_website={'type': 'boolean'},
        permissions={
            'type': 'array',
            'items': {
                'type': 'string',
                'enum': ['READ', 'WRITE', 'WRITE_ACP', 'READ_ACP', 'FULL_CONTROL']}
            })

    annotation_key = 'c7n:GlobalPermissions'

    def process(self, buckets, event=None):
        filtered_buckets = filter_region_bucket(self.manager.session_factory, buckets)
        with self.executor_factory(max_workers=5) as w:
            results = w.map(self.process_bucket, filtered_buckets)
            results = list(filter(None, list(results)))
            return results

    def process_bucket(self, bucket):
        results = []
        allow_website = self.data.get('allow_website', True)
        perms = self.data.get('permissions', [])

        client = get_obs_client(self.manager.session_factory, bucket)
        self.query_bucket_acl(bucket, client)

        for grant in bucket['Acl']['grants']:
            if 'group' not in grant.get('grantee', {}):
                continue

            if grant['grantee']['group'] not in ['Everyone']:
                continue

            if allow_website and grant['permission'] == 'READ' and \
                self.is_website_bucket(bucket, client=client):
                log.info('[filters]-[global-grants]: bucket[%s] is website bucket.'
                          % (bucket['name']))
                continue

            if not perms or (perms and grant['permission'] in perms):
                results.append(grant['permission'])

        if results:
            set_annotation(bucket, 'globalPermissions', results)
            log.info("[filters]-[global-grants] filter resource " +
            "with id:[%s] success." % (bucket['name']))
            return bucket

        return None

    def query_bucket_acl(self, bucket, client):
        resp = client.getBucketAcl(bucket['name'])
        if resp.status < 300:
            acl = resp.body
            bucket['Acl'] = acl
        else:
            if 'Not Found' == resp.reason:
                bucket['Acl'] = {'grants': []}
                return

            log.error('[filters]-The filter:[global-grants]' +
                ' query bucket:[%s] bucket acl is failed. cause: %s'
                  % (bucket['name'], resp.reason))
            raise_exception(resp, 'getBucketWebsite', bucket)

    def is_website_bucket(self, bucket, client):
        resp = client.getBucketWebsite(bucket['name'])
        if resp.status < 300:
            website_config = resp.body
            if 'indexDocument' in website_config:
                bucket['website'] = True
                return True
            else:
                bucket['website'] = False
                return False
        else:
            if 'NoSuchWebsiteConfiguration' == resp.errorCode:
                bucket['website'] = False
                return False
            else:
                log.error('[filters]-The filter:[global-grants]' +
                ' query bucket:[%s] bucket website config is failed. cause: %s'
                  % (bucket['name'], resp.reason))
                raise_exception(resp, 'getBucketWebsite', bucket)


@Obs.filter_registry.register("check-public-block")
class FilterPublicBlock(Filter):
    """Filter for obs bucket public blocks

    If no filter paramaters are provided it checks to see if any are unset or False.

    If parameters are provided only the provided ones are checked.

    :example:

    .. code-block:: yaml

            policies:
              - name: CheckForPublicAclBlock-Off
                resource: huaweicloud.obs
                filters:
                  - type: check-public-block
                    blockPublicAcls: true
                    blockPublicPolicy: true
    """

    schema = type_schema(
        'check-public-block',
        blockPublicAcls={'type': 'boolean'},
        ignorePublicAcls={'type': 'boolean'},
        blockPublicPolicy={'type': 'boolean'},
        restrictPublicBuckets={'type': 'boolean'})

    keys = (
        'blockPublicPolicy', 'blockPublicAcls', 'ignorePublicAcls', 'restrictPublicBuckets')
    annotation_key = 'c7n:PublicAccessBlock'

    def process(self, buckets, event=None):
        filtered_buckets = filter_region_bucket(self.manager.session_factory, buckets)
        with self.executor_factory(max_workers=5) as w:
            results = w.map(self.process_bucket, filtered_buckets)
            results = list(filter(None, list(results)))
            return results

    def process_bucket(self, bucket):
        bucket_name = bucket['name']

        config = dict(bucket.get(self.annotation_key, {key: False for key in self.keys}))
        if self.annotation_key not in bucket:
            client = get_obs_client(self.manager.session_factory, bucket)
            resp = client.getBucketPublicAccessBlock(bucket_name)
            if resp.status < 300:
                config = resp.body
            else:
                log.error('[filters]-The filter:[check-public-block]' +
                ' query bucket:[%s] bucket public access block is failed. cause: %s'
                  % (bucket['name'], resp.reason))
                raise_exception(resp, 'BucketPublicAccessBlock', bucket)

            bucket[self.annotation_key] = config

        is_match = self.matches_filter(config)

        if is_match:
            log.info("[filters]-[check-public-block] filter resource " +
            "with id:[%s] success." % (bucket['name']))
            return bucket
        else:
            return None

    def matches_filter(self, config):
        key_set = [key for key in self.keys if key in self.data]
        if key_set:
            return all([self.data.get(key) is config[key] for key in key_set])
        else:
            return not all(config.values())


@Obs.filter_registry.register("support-https-request")
class SecureTransportFilter(Filter):
    """Find buckets with allow http protocol access

    :example:

    .. code-block:: yaml

            policies:
              - name: obs-bucket-https-request-only
                resource: huaweicloud.obs
                filters:
                  - type: support-https-request
                actions:
                    - type: set-statements
                      statements:
                        - Sid: DenyHttp
                          Effect: Deny
                          Principal:
                            ID: "*"
                          Action: "*"
                          Resource:
                            - "{bucket_name}"
                            - "{bucket_name}/*"
                          Condition:
                            Bool:
                                SecureTransport: "false"

    """
    schema = type_schema("support-https-request")

    required_template = {
            "Effect": "Deny",
            "Principal": {"ID": ["*"]},
            "Action": ["*"],
            "Condition": {"Bool": {"SecureTransport": ["false"]}}
        }

    resource_list_template = ["{bucket_name}", "{bucket_name}/*"]

    def process(self, buckets, event=None):
        filtered_buckets = filter_region_bucket(self.manager.session_factory, buckets)
        with self.executor_factory(max_workers=5) as w:
            results = w.map(self.process_bucket, filtered_buckets)
            results = list(filter(None, list(results)))
            return results

    def process_bucket(self, bucket):
        self.get_bucket_policy(bucket)

        is_dany_http = self.is_http_deny_enhanced(bucket)

        if not is_dany_http:
            log.info("[filters]-[support-https-request] filter resource " +
            "with id:[%s] success." % (bucket['name']))
            return bucket

        return None

    def is_http_deny_enhanced(self, bucket):
        resource_list = [item.format(bucket_name=bucket['name'])
                         for item in self.resource_list_template]

        policy = bucket.get('Policy') or '{}'
        if not policy:
            log.info('[filters]-[support-https-request]: bucket[%s] has not set bucket policy.'
                      % (bucket['name']))
            return False

        policy = json.loads(policy)
        bucket_statements = policy.setdefault('Statement', [])

        for s in bucket_statements:
            base_match = all(
                s.get(key) == value
                for key, value in self.required_template.items()
            )

            if not base_match:
                continue

            if self.contain_all_elements(list(s.get('Resource', [])), resource_list):
                return True

        log.info('[filters]-[support-https-request]: bucket[%s] bucket policy missing ' +
        'deny http request statement.' % (bucket['name']))
        return False

    def contain_all_elements(self, arr1, arr2):
        return set(arr2).issubset(set(arr1))

    def get_bucket_policy(self, bucket):
        client = get_obs_client(self.manager.session_factory, bucket)
        resp = client.getBucketPolicy(bucket['name'])

        if resp.status < 300:
            policy = resp.body.policyJSON
            bucket['Policy'] = policy
        else:
            if 'NoSuchBucketPolicy' == resp.errorCode or 'Not Found' == resp.reason:
                bucket['Policy'] = {}
                return

            log.error('[filters]-The filter:[support-https-request]' +
                ' query bucket:[%s] bucket policy is failed. cause: %s'
                  % (bucket['name'], resp.reason))
            raise_exception(resp, 'getBucketPolicy', bucket)


@Obs.filter_registry.register("cross-account")
class ObsCrossAccountFilter(Filter):
    """Filters cross-account access to obs buckets

    :example:

    .. code-block:: yaml

            policies:
              - name: find-cross-account-access
                resource: huaweicloud.obs
                filters:
                  - type: cross-account
    """
    schema = type_schema('cross-account', allow_website={'type': 'boolean'})

    black_listed_actions = ["PutBucketPolicy", "DeleteBucketPolicy",
     "PutBucketAcl", "PutEncryptionConfiguration", "PutObjectAcl", "*"]

    def process(self, buckets, event=None):
        filtered_buckets = filter_region_bucket(self.manager.session_factory, buckets)
        with self.executor_factory(max_workers=5) as w:
            results = w.map(self.process_bucket, filtered_buckets)
            results = list(filter(None, list(results)))
            return results

    def process_bucket(self, bucket):
        client = get_obs_client(self.manager.session_factory, bucket)

        self.get_bucket_policy(bucket, client)
        self.query_bucket_acl(bucket, client)
        self.query_bucket_website_config(bucket, client)

        policy_violating = self.check_is_cross_account_by_policy(bucket)
        acl_violating = self.check_is_cross_accout_by_acl(bucket)

        if policy_violating or acl_violating:
            log.info("[filters]-[cross-account] filter resource " +
            "with id:[%s] success." % (bucket['name']))
            return bucket

        return None

    def check_is_cross_account_by_policy(self, bucket):
        policy = bucket.get('Policy', {})
        if not policy:
            return False

        statements = json.loads(policy).get('Statement', [])
        legal_statements = []
        violating = False

        for stmt in statements:
            if self.is_violation(stmt, bucket['account_id']):
                violating = True
            else:
                legal_statements.append(stmt)

        if violating:
            bucket[RemoveCrossAccountAccessConfig.annotation_policy_key] = legal_statements
            log.info("[filters]-[cross-account]: bucket[%s]: has cross account" +
            " bucket policy." % (bucket['name']))
            return True

        return False

    def is_violation(self, stmt, current_account):
        if stmt.get('Effect') != 'Allow':
            return False

        principal_user = stmt.get('Principal', {}).get("ID", [])

        for user in principal_user:
            if current_account not in user:
                return True

        return False

    def check_is_cross_accout_by_acl(self, bucket):
        acl = bucket.get('Acl', {})
        if not acl:
            return False

        grants = acl.get('grants', [])
        legal_grants = []
        violating = False

        for grant in grants:
            grantee = grant.get('grantee', {})
            if not grantee:
                continue

            if 'group' in grantee:
                if grantee['group'] not in ['Everyone']:
                    legal_grants.append(grant)
                else:
                    if grant['permission'] == 'READ' and bucket['website']:
                        legal_grants.append(grant)
                        continue
                    else:
                        violating = True

            if 'grantee_id' in grantee:
                if grantee['grantee_id'] != bucket['account_id']:
                    violating = True
                else:
                    legal_grants.append(grant)

        if violating:
            owner = acl['owner']
            new_acl = ACL(owner, legal_grants)
            bucket[RemoveCrossAccountAccessConfig.annotation_acl_key] = new_acl
            log.info("[filters]-[cross-account]: bucket[%s]: has cross account" +
            " bucket acl." % (bucket['name']))

        return violating

    def get_bucket_policy(self, bucket, client):
        resp = client.getBucketPolicy(bucket['name'])

        if resp.status < 300:
            policy = resp.body.policyJSON
            bucket['Policy'] = policy
        else:
            if 'NoSuchBucketPolicy' == resp.errorCode or 'Not Found' == resp.reason:
                bucket['Policy'] = {}
                return

            log.error('[filters]-The filter:[cross-account]' +
                ' query bucket:[%s] bucket policy is failed. cause: %s'
                  % (bucket['name'], resp.reason))
            raise_exception(resp, 'getBucketPolicy', bucket)

        self.query_bucket_acl(bucket, client)

    def query_bucket_acl(self, bucket, client):
        resp = client.getBucketAcl(bucket['name'])
        if resp.status < 300:
            acl = resp.body
            bucket['Acl'] = acl
        else:
            if 'Not Found' == resp.reason:
                bucket['Acl'] = {'owner': {}, 'grants': []}
                return

            log.error('[filters]-The filter:[cross-account]' +
                ' query bucket:[%s] bucket acl is failed. cause: %s'
                  % (bucket['name'], resp.reason))
            raise_exception(resp, 'getBucketAcl', bucket)

    def query_bucket_website_config(self, bucket, client):
        allow_website = self.data.get('allow_website', True)
        if not allow_website:
            bucket['website'] = False
            return

        resp = client.getBucketWebsite(bucket['name'])
        if resp.status < 300:
            website_config = resp.body
            if 'indexDocument' in website_config:
                bucket['website'] = True
                log.info('[filters]-[cross-account] bucket[%s] is website bucket.'
                          % (bucket['name']))
                return True
            else:
                bucket['website'] = False
                log.info('[filters]-[cross-account] bucket[%s] is not website bucket.'
                          % (bucket['name']))
                return False
        else:
            if 'NoSuchWebsiteConfiguration' == resp.errorCode:
                bucket['website'] = False
                log.info('[filters]-[cross-account] bucket[%s] is not website bucket.'
                          % (bucket['name']))
                return False
            else:
                log.error('[filters]-The filter:[cross-account]' +
                ' query bucket:[%s] bucket website config is failed. cause: %s'
                  % (bucket['name'], resp.reason))
                raise_exception(resp, 'getBucketWebsite', bucket)


@Obs.filter_registry.register("obs-missing-tag-filter")
class OBSMissingTagFilter(Filter):
    """Detects and filters Huawei Cloud OBS buckets that are missing the designated tags.

    :example:

    .. code-block:: yaml

            policies:
              - name: missing-bucket-tags
                resource: huaweicloud.obs
                filters:
                  - type: obs-missing-tag-filter
                    tags:
                      - key: key1
                        value: value1
                      - key: key2
                        value: value2
                    match: missing-any
    """
    schema = type_schema(
        'obs-missing-tag-filter',
        required=['tags'],
        tags={
            'type': 'array',
            'items': {
                'type': 'object',
                'additionalProperties': False,
                'required': ['key'],
                'properties': {
                    'key': {'type': 'string', 'minLength': 1, 'maxLength': 35},
                    'value': {'type': 'string'}
                }
            }
        },
        match={'type': 'string', 'enum': ['missing-all', 'missing-any']}
    )

    expected_tags = []

    def process(self, buckets, event=None):
        filtered_buckets = filter_region_bucket(self.manager.session_factory, buckets)

        for t in self.data.get('tags', []):
            key = t.get('key')
            value = t.get('value')
            if isinstance(value, str) and value.startswith('^') and value.endswith('$'):
                try:
                    pattern = re.compile(value)
                    self.expected_tags.append((key, pattern))
                except re.error:
                    self.log.info('[filters]-[obs-missing-tag-filter]: failed to compile' +
                    ' the regular exception [%s].' % value)
                    self.expected_tags.append((key, value))
            else:
                self.expected_tags.append((key, value))

        with self.executor_factory(max_workers=5) as executor:
            results = list(filter(None, executor.map(
                self.process_bucket_wrapper, filtered_buckets)))
            return results

    def process_bucket_wrapper(self, bucket):
        """Wrapper function to process a single bucket with expected_tags."""
        return self.process_bucket(bucket, self.expected_tags)

    def process_bucket(self, bucket, expected_tags):
        match_mode = self.data.get('match', 'missing-any')

        bucket_tags = self.get_bucket_tags(bucket)
        if self._is_match(expected_tags, bucket_tags, match_mode, bucket['name']):
            self.log.info('[filters]-[obs-missing-tag-filter]: The bucket '
            '[%s] missing some tags' % (bucket['name']))
            log.info("[filters]-[obs-missing-tag-filter] filter resource " +
            "with id:[%s] success." % (bucket['name']))
            return bucket
        else:
            return None

    def get_bucket_tags(self, bucket):
        client = get_obs_client(self.manager.session_factory, bucket)
        resp = client.getBucketTagging(bucket['name'])
        if resp.status < 300:
            self.log.debug('[filters]-[obs-missing-tag-filter]: The bucket '
            '[%s] has tags: %s' % (bucket['name'], resp.body.get('tagSet', [])))
            return {(tag.key, tag.value) for tag in resp.body.get('tagSet', [])}
        else:
            if 'NoSuchTagSet' == resp.errorCode:
                self.log.debug('[filters]-[obs-missing-tag-filter]: The bucket '
            '[%s] has not set any tag.' % (bucket['name']))
                return set()

            self.log.error('[filters]-The filter:[obs-missing-tag-filter]' +
                ' query bucket:[%s] bucket tags is failed. cause: %s'
                  % (bucket['name'], resp.reason))
            raise_exception(resp, 'getBucketTagging', bucket)

    def _is_match(self, expected_tags, actual_tags, match_mode, bucket_name):
        """
        Verify if actual tags meet expectations
        :param expected_tags: List of (key, value) tuples,
        where value can be None/string/regex object
        :param actual_tags: Set of (key, value) tuples from the bucket
        :param match_mode: Matching mode ('missing-all' or 'missing-any')
        :return: Boolean indicating match status
        """
        actual_dict = {k: v for k, v in actual_tags}

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

            log.debug('[filters]-[obs-missing-tag-filter]: check bucket[%s] tag '
            '(%s, %s) result is [%s]' % (bucket_name, key, actual_value, results[-1]))

        if match_mode == 'missing-all':
            # all expected tags to NOT match
            return not any(results)
        elif match_mode == 'missing-any':
            # Require at least one expected tag to NOT match
            return not all(results)
        return False
