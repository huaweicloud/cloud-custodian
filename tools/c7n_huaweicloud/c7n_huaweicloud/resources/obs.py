# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import json

from huaweicloudsdkcore.exceptions import exceptions

from c7n.utils import type_schema, set_annotation, local_session
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
        new_statements = self.process_policy(p.get('Statement', []))

        p['Statement'] = new_statements
        self.update_statements(bucket, p)

        bucket['State'] = 'delete-wildcard-statements'
        bucket['newStatements'] = new_statements
        return bucket

    def process_policy(self, bucket_statements):
        new_statements = []
        for statement in bucket_statements:
            prinicipal_user = statement.get('Principal', {}).get("ID", [])
            action = statement.get('Action', [])
            if "*" in prinicipal_user or "*" in action:
                continue

            new_statements.append(statement)

        return new_statements

    def update_statements(self, bucket, policy):
        bucket_name = bucket['name']
        client = get_obs_client(self.manager.session_factory, bucket)

        if not policy['Statement']:
            resp = client.deleteBucketPolicy(bucket_name)
        else:
            resp = client.setBucketPolicy(bucket_name, json.dumps(policy))

        if resp.status > 300:
            log.error("update bucket [%s] bucket policy failed." % bucket_name)
            sdk_error = ObsSdkError(resp.errorCode, resp.errorMessage, resp.requestId)
            raise exceptions.ClientRequestException(resp.status, sdk_error)


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
            return bucket
        else:
            sdk_error = ObsSdkError(resp.errorCode, resp.errorMessage, resp.requestId)
            raise exceptions.ClientRequestException(resp.status, sdk_error)


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
        with self.executor_factory(max_workers=5) as w:
            results = w.map(self.process_bucket, buckets)
            results = list(filter(None, list(results)))
            return results

    def process_bucket(self, bucket):
        self.get_bucket_policy(bucket)
        return self.filter_include_wildcard_statement_bucket_policy(bucket)

    def filter_include_wildcard_statement_bucket_policy(self, bucket):
        policy = bucket.get('Policy') or '{}'
        if not policy:
            log.info("bucket not config bucket policy")
            return None

        policy = json.loads(policy)
        bucket_statements = policy.setdefault('Statement', [])

        result = []
        for statement in bucket_statements:
            prinicipal_user = statement.get('Principal', {}).get("ID", [])
            action = statement.get('Action', [])
            if "*" in prinicipal_user or "*" in action:
                result.append(statement)

        if result:
            set_annotation(bucket, self.annotation_key, result)
            return bucket

        return None

    def get_bucket_policy(self, bucket):
        client = get_obs_client(self.manager.session_factory, bucket)
        resp = client.getBucketPolicy(bucket['name'])

        if resp.status < 300:
            policy = resp.body.policyJSON
            bucket['Policy'] = policy
        else:
            if 'NoSuchBucketPolicy' == resp.errorCode:
                bucket['Policy'] = {}
            else:
                log.error({"read bucket ": bucket['name'], " policy failed. request reason is ":
                            resp.reason, " request id is": resp.requestId})
                sdk_error = ObsSdkError(resp.errorCode, resp.errorMessage, resp.requestId)
                raise exceptions.ClientRequestException(resp.status, sdk_error)


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
        with self.executor_factory(max_workers=5) as w:
            results = w.map(self.process_bucket, buckets)
            results = list(filter(None, list(results)))
            return results

    def process_bucket(self, bucket):
        target_state = self.data.get('state', False)
        target_crypto = self.data.get('crypto', None)

        current_crypto = self.get_encryption_crypto(bucket)
        bucket[self.annotation_key] = current_crypto

        if not target_state:
            if target_crypto is None and current_crypto is None:
                return bucket

            if target_crypto is not None and target_crypto != current_crypto:
                return bucket
        else:
            if target_crypto is None and current_crypto is not None:
                return bucket

            if target_crypto is not None and current_crypto is not None \
            and target_crypto == current_crypto:
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
            if 'NoSuchEncryptionConfiguration' == error_code:
                return None
            else:
                log.error({"read bucket ": bucket['name'],
                           " encryption config failed. request reason is ":
                            resp.reason, " request id is": resp.requestId})
                sdk_error = ObsSdkError(resp.errorCode, resp.errorMessage, resp.requestId)
                raise exceptions.ClientRequestException(resp.status, sdk_error)
