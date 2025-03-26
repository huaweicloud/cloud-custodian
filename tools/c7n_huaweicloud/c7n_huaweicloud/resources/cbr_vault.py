import logging

from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkcbr.v1 import (
    BatchCreateAndDeleteVaultTagsRequest,
    BulkCreateAndDeleteVaultTagsReq, Tag,
    ListPoliciesRequest, AssociateVaultPolicyRequest,
    VaultAssociate, CreatePolicyRequest,
    PolicyTriggerPropertiesReq,
    PolicyTriggerReq, PolicyoODCreate,
    PolicyCreate, PolicyCreateReq
)

from c7n.filters import Filter
from c7n.utils import type_schema, local_session
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

log = logging.getLogger("custodian.huaweicloud.resources.cbr-vault")


@resources.register('cbr-vault')
class CbrVault(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'cbr-vault'
        enum_spec = ('list_vault', 'vaults', 'offset')
        id = 'id'
        tag_resource_type = 'vault'


@CbrVault.action_registry.register('add_tags')
class CbrVaultAddTags(HuaweiCloudBaseAction):
    '''
    Check if a backup is tagged. Input tags to add to the backup not tagged.

    :Example:

    .. code-block:: yaml

        policies:
        - name: add_tag_vault_untagged
          resource: huaweicloud.cbr-vault
          filters:
            - 'tags': empty
          actions:
            - type: add_tags
              keys: ['1', '2']
              values: ['1', '2']

    '''

    schema = type_schema('add_tags',
                         keys={'type': 'array',
                               'items': {'type': 'string'}},
                         values={'type': 'array',
                                 'items': {'type': 'string'}})

    def perform_action(self, resource):

        client = self.manager.get_client()
        try:
            request = BatchCreateAndDeleteVaultTagsRequest()
            request.vault_id = resource['id']
            listTagsbody = []
            for k, v in zip(self.data.get('keys'), self.data.get('values')):
                listTagsbody.append(Tag(key=k, value=v))
            request.body = BulkCreateAndDeleteVaultTagsReq(
                action="create",
                tags=listTagsbody
            )
            response = client.batch_create_and_delete_vault_tags(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return response


@CbrVault.filter_registry.register('unassociated')
# class CbrVaultFilter(AssociatedVaultsFilter):
#     schema = type_schema('associated_vaults', op={'enum': ['ni', 'in']})
class CbrVaultFilter(Filter):
    schema = type_schema('unassociated')

    def process(self, resources, event=None):
        results = []
        client = self.manager.get_client()
        for r in resources:
            try:
                request = ListPoliciesRequest()
                request.vault_id = r['id']
                response = client.list_policies(request).to_dict()['policies']
                if not response:
                    results.append(r)
            except exceptions.ClientRequestException as e:
                log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
                raise
        return results


@CbrVault.action_registry.register('associate_vault_policy')
class CbrAssociateVaultPolicy(HuaweiCloudBaseAction):
    '''
    Checks if a vault of which protect type is backup is associated with a policy.
    Create a policy which is default created weekly and associate
    it with the vault not associated with any policy.

    : Example:

    .. code-block:: yaml

        policies:
            - name: associate_vault_policy_unprotected
              resource: huaweicloud.cbr-vault
              filters:
                - and:
                  - "policy_id": absent
                  - type: value
                    key: billing.protect_type
                    value: "backup"
              actions:
                - type: associate_vault_policy
                  day_backups: 0
                  week_backups: 0
                  month_backups: 0
                  year_backups: 0
                  max_backups: -1
                  retention_duration_days: 30
                  full_backup_interval: -1
                  timezone: "UTC+08:00"


    '''

    schema = type_schema('associate_vault_policy',
                         day_backups={'type': 'integer'},
                         week_backups={'type': 'integer'},
                         month_backups={'type': 'integer'},
                         year_backups={'type': 'integer'},
                         max_backups={'type': 'integer'},
                         retention_duration_days={'type': 'integer'},
                         full_backup_interval={'type': 'integer'},
                         timezone={'type': 'string'},
                         )

    def perform_action(self, resource):
        client = self.manager.get_client()
        try:
            request = AssociateVaultPolicyRequest()
            request.vault_id = resource['id']
            request.body = VaultAssociate(
                policy_id=self.create_policy(
                    day_backups=self.data.get('day_backups'),
                    week_backups=self.data.get('week_backups'),
                    month_backups=self.data.get('month_backups'),
                    year_backups=self.data.get('year_backups'),
                    max_backups=self.data.get('max_backups'),
                    retention_duration_days=self.data.get('retention_duration_days'),
                    full_backup_interval=self.data.get('full_backup_interval'),
                    timezone=self.data.get('timezone'),
                    operation_type=resource['billing']['protect_type']
                )['policy']['id']
            )
            response = client.associate_vault_policy(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return response

    def create_policy(self,
                      day_backups,
                      week_backups,
                      month_backups,
                      year_backups,
                      max_backups,
                      retention_duration_days,
                      full_backup_interval,
                      timezone,
                      operation_type):
        client = local_session(self.manager.get_client()).client('cbr-policy')

        try:
            request = CreatePolicyRequest()
            listPatternProperties = [
                "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR,SA,SU;BYHOUR=09;BYMINUTE=00",
                "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR,SA,SU;BYHOUR=10;BYMINUTE=00"
            ]
            propertiesTrigger = PolicyTriggerPropertiesReq(
                pattern=listPatternProperties
            )
            triggerPolicy = PolicyTriggerReq(
                properties=propertiesTrigger
            )
            operationDefinitionPolicy = PolicyoODCreate(
                day_backups=day_backups,
                max_backups=max_backups,
                month_backups=month_backups,
                retention_duration_days=retention_duration_days,
                timezone=timezone,
                week_backups=week_backups,
                year_backups=year_backups,
                full_backup_interval=full_backup_interval
            )
            policybody = PolicyCreate(
                enabled=True,
                name="weekly_create_backup",
                operation_definition=operationDefinitionPolicy,
                operation_type=operation_type,
                trigger=triggerPolicy
            )
            request.body = PolicyCreateReq(
                policy=policybody
            )
            response = client.create_policy(request)
        except exceptions.ClientRequestException as e:
            log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
            raise
        return response.to_dict()
