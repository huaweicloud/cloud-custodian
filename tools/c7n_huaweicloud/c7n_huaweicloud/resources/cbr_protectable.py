import logging
import random
import time
import re
import uuid
from datetime import datetime
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkcbr.v1 import (
    CreateVaultRequest, BillingCreate,
    VaultCreate, VaultCreateReq,
    ResourceCreate, ListVaultRequest,
    AddVaultResourceRequest, VaultAddResourceReq,
    ListPoliciesRequest
)

from c7n.utils import type_schema
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo


log = logging.getLogger("custodian.huaweicloud.resources.cbr-protectable")


@resources.register('cbr-protectable')
class CbrProtectable(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'cbr-protectable'
        enum_spec = ('list_protectable', 'instances', 'offset')
        id = 'id'
        tag_resource_type = ''

    def get_resources(self, resource_ids):
        resources = (
                self.augment(self.source.get_resources(self.get_resource_query())) or []
        )
        result = []
        for resource in resources:
            add_tags = []
            if resource.get('detail'):
                tags = resource.get('detail').get('tags')
                for t in tags:
                    if '=' in t:
                        add_tags.append(t)
            resource['tags'] = add_tags
            if resource["id"] in resource_ids:
                result.append(resource)
        return result

    def _fetch_resources(self, query):
        resources = (
                self.augment(self.source.get_resources(query)) or []
        )
        for r in resources:
            add_tags = []
            if r.get('detail'):
                tags = r.get('detail').get('tags')
                for t in tags:
                    if '=' in t:
                        add_tags.append(t)
            r['tags'] = add_tags
        return resources


@CbrProtectable.action_registry.register('associate_server_with_vault')
class CbrAssociateServerVault(HuaweiCloudBaseAction):
    '''
        Checks if the legally tagged servers is protected by a vault.
        if not, associate it with an existing vault.
        if the number of instances in all existing vaults has reached the upper limit,
        create a new vaults with periodical backup policy to protect them.
    : Example:

    .. code-block:: yaml

        policies:
          - name: cbr_protectable_associate_server_with_vault
            resource: huaweicloud.cbr-protectable
            filters:
              - and:
                - type: value
                  op: contains
                  key: detail.tags
                  value: "backup_policy=45Dd"
                - type: value
                  key: protectable.vault
                  value: empty
            actions:
              - type: associate_server_with_vault
                name: "new_vault"

    '''
    max_count = 200  # the maximum count of instance of vault
    UUID_PATTERN = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
    action_name = "associate_server_with_vault"
    resource_type = "cbr-protectable"

    schema = type_schema('associate_server_with_vault',
                        backup_policy={'type': 'string'},
                        consistent_level={'type': 'string'},
                        object_type={'type': 'string'},
                        protect_type={'type': 'string'},
                        size={'type': 'integer'},
                        charging_mode={'type': 'string'},
                        is_multi_az={'type': 'boolean'},
                        is_auto_renew={'type': 'boolean'},
                        is_auto_pay={'type': 'boolean'},
                        name={'type': 'string'}
                        )

    def process(self, resources):
        for s in resources:
            log.debug(f"[actions-[{self.action_name}]] the resource:[{self.resource_type}] info:"
                      f" resource id:{s.get('id')}, tags:{s.get('tags')}")
        try:
            self.perform_action(resources)
        except exceptions.ClientRequestException as ex:
            resource_ids = [f.get('id') for f in resources]
            log.error(f"[actions]-[{self.action_name}] the resource:[{self.resource_type}]"
                      f" with id:[{resource_ids}] associate to vault failed,"
                      f" cause:request id:{ex.request_id}, msg: {ex.error_msg}")
            self.handle_exception(resources)
            raise
        return self.process_result(resources)

    def handle_exception(self, resources):
        self.failed_resources.extend(resources)

    def perform_action(self, resources):
        random_time = random.randint(0, 12)
        time.sleep(random_time * 3)
        client = self.manager.get_client()
        try:
            request = ListVaultRequest()
            request.object_type = "server"
            response = client.list_vault(request)
            vaults = response.to_dict()['vaults']
            log.debug(f"[actions]-[{self.action_name}] query the exist vaults:{vaults} success.")
        except exceptions.ClientRequestException as e:
            log.error(f"[actions]-[{self.action_name}] query the exist vaults failed, cause:"
                      f"request id:{e.request_id}, msg:{e.error_msg}")
            raise
        policy_id = self.get_policy_for_new_vault(vaults)

        vault_num = 0
        server_ids = []
        while resources and vault_num < len(vaults):
            server_ids.clear()
            try:
                request = AddVaultResourceRequest()
                request.vault_id = vaults[vault_num]['id']
                num_resource = len(vaults[vault_num]['resources'])
                space = self.max_count - num_resource
                if space <= 0:
                    log.info(f"[actions]-[{self.action_name}] "
                              f"unable to add resource to {vaults[vault_num]['id']},"
                              "because the number of instances in the vault"
                              f" {vaults[vault_num]['id']} has reached the upper limit.")
                else:
                    listResourcesbody = []
                    server_ids = []
                    for _ in range(min(space, len(resources))):
                        server = resources.pop()
                        listResourcesbody.append(
                            ResourceCreate(
                                id=server['id'],
                                type="OS::Nova::Server"
                            )
                        )
                        server_ids.append(server['id'])
                    request.body = VaultAddResourceReq(
                        resources=listResourcesbody
                    )
                    response = client.add_vault_resource(request)
                    log.info(f"[actions]-[{self.action_name}] the resource:[{self.resource_type}]"
                              f" with id:{server_ids} associate to vault:"
                              f"{vaults[vault_num]['id']} success.")
            except exceptions.ClientRequestException as e:
                if str(e.error_code) == "BackupService.6302":
                    log.warning(f"[actions]-[{self.action_name}] add resource "
                                f"id:[{server_ids}] to vault id:{vaults[vault_num]['id']}"
                                f" failed, cause request id:{e.request_id}, msg:{e.error_msg}")
                    m = re.search(self.UUID_PATTERN, e.error_msg, re.IGNORECASE)
                    if m:
                        error_resource = str(uuid.UUID(m.group()))
                        resources.extend([sid for sid in server_ids if sid != error_resource])
                        continue
                else:
                    log.error(f"[actions]-[{self.action_name}] add resource "
                              f"id:[{server_ids}] to vault id:{vaults[vault_num]['id']}"
                              f" failed, cause request id:{e.request_id}, msg:{e.error_msg}")
                    raise
            vault_num += 1

        if resources:
            vault_billing = {}
            if len(vaults) > 0:
                vault_billing['consistent_level'] = vaults[0]['billing']['consistent_level']
                vault_billing['object_type'] = vaults[0]['billing']['object_type']
                vault_billing['protect_type'] = vaults[0]['billing']['protect_type']
                vault_billing['size'] = vaults[0]['billing']['size']
                vault_billing['charging_mode'] = vaults[0]['billing']['charging_mode']
                vault_billing['is_multi_az'] = vaults[0]['billing']['is_multi_az']
            vault_prefix = self.data.get('name') or 'vault'
            vault_index = self.get_exist_vault_index_by_prefix(vaults, vault_prefix)
            self.bind_resource_to_new_vault(resources, policy_id,
                                            vault_billing, vault_prefix, vault_index)

    def bind_resource_to_new_vault(self, resources, policy_id,
                                   vault_billing, vault_prefix, vault_index):
        offset = vault_index + 1
        resources = list(resources)
        while resources:
            server_list = resources[:self.max_count]
            del resources[:self.max_count]
            vault_name = f"{vault_prefix}{offset:04d}"
            log.debug(f"[actions]-[{self.action_name}] all existing vaults are "
                      f"unable to be associated, a new vault[{vault_name}] will be created.")
            try:
                self.create_new_vault(server_list, policy_id, vault_name, vault_billing)
            except exceptions.ClientRequestException as e:
                log.warning(f"[actions]-[{self.action_name}] add resource id:[{server_list}] to "
                            f"vault failed, cause request id:{e.request_id}, msg:{e.error_msg}")
                if str(e.error_code) == "BackupService.6302":
                    m = re.search(self.UUID_PATTERN, e.error_msg, re.IGNORECASE)
                    if m:
                        error_resource = str(uuid.UUID(m.group()))
                        resources.extend([sid for sid in server_list if sid != error_resource])
                        continue
                else:
                    raise
            offset += 1

    def get_exist_vault_index_by_prefix(self, exist_vaults, prefix):
        serial_number = -1
        for exist_vault in exist_vaults:
            if str(exist_vault['name']).startswith(prefix):
                suffix = str(exist_vault['name'])[len(prefix):]
                if suffix.isdigit():
                    index = int(suffix)
                    if serial_number <= index:
                        serial_number = index
        return serial_number

    def create_new_vault(self, resources, policy_id, vault_name, vault_billing):
        client = self.manager.get_client()
        resource_ids = []
        try:
            request = CreateVaultRequest()
            listResourcesVault = []
            for server in resources:
                listResourcesVault.append(
                    ResourceCreate(
                        id=server['id'],
                        type="OS::Nova::Server"
                    )
                )
                resource_ids.append(server.get('id'))
            # prioritize existing repositories
            if vault_billing:
                consistent_level = vault_billing['consistent_level']
                object_type = vault_billing['object_type']
                protect_type = vault_billing['protect_type']
                size = vault_billing['size']
                charging_mode = vault_billing['charging_mode']
                is_multi_az = vault_billing['is_multi_az']
            else:
                consistent_level = self.data.get('consistent_level', 'crash_consistent')
                object_type = self.data.get('object_type', 'server')
                protect_type = self.data.get('protect_type', 'backup')
                size = self.data.get('size', 100)
                charging_mode = self.data.get('charging_mode', 'post_paid')
                is_multi_az = self.data.get('is_multi_az', False)
            is_auto_renew = self.data.get('is_auto_renew', True)
            is_auto_pay = self.data.get('is_auto_pay', True)

            billing_vault = BillingCreate(
                consistent_level=consistent_level,
                object_type=object_type,
                protect_type=protect_type,
                size=size,
                charging_mode=charging_mode,
                is_multi_az=is_multi_az,
                is_auto_renew=is_auto_renew,
                is_auto_pay=is_auto_pay
            )
            if vault_name is None or vault_name == '' or policy_id is None or policy_id == '':
                error_msg = "param error, policy_id:{}, vault_name:{}, billing_vault:{}".format(
                    policy_id, vault_name, billing_vault)
                log.error(f"[actions]-[{self.action_name}] failed to create vault to "
                          f"associate {self.resource_type} resource, cause policy_id:{policy_id}"
                          f"vault_name:{vault_name}, billing_vault:{billing_vault}")
                raise Exception(error_msg)

            vault_body = VaultCreate(
                backup_policy_id=policy_id,
                billing=billing_vault,
                name=vault_name,
                resources=listResourcesVault
            )
            request.body = VaultCreateReq(
                vault=vault_body
            )
            response = client.create_vault(request)
            new_vault_id = response.vault.id
            log.info(f"[actions]-[{self.action_name}] the resource:[{self.resource_type}]"
                     f" with id:[{resource_ids}] create new backup vault:{new_vault_id},"
                     " and associate the servers to it success")
        except exceptions.ClientRequestException as e:
            log.error(f"[actions]-[{self.action_name}] create vault failed, cause "
                      f"request id:{e.request_id}, status code:{e.status_code}, msg:{e.error_msg}")
            raise
        return response

    def get_policy_for_new_vault(self, vaults):
        '''
        get the backup policy to be inherited based on the queried vaults
        '''
        policy_id = None
        if vaults and len(vaults) > 0:
            sort_vault = sorted(vaults, key=lambda x: datetime.strptime(x['created_at'],
                                                                        "%Y-%m-%dT%H:%M:%S.%f"))
            client = self.manager.get_client()
            for vault_item in sort_vault:
                try:
                    request = ListPoliciesRequest()
                    request.operation_type = "backup"
                    request.vault_id = vault_item['id']
                    response = client.list_policies(request)
                    if response.to_dict()['policies'] and len(response.to_dict()['policies']) > 0:
                        policy_id = response.to_dict()['policies'][0]['id']
                        log.debug(f"[actions]-{[self.action_name]} "
                                  f"query policy:{policy_id} by vault:{vault_item['id']} success.")
                        break
                except exceptions.ClientRequestException as e:
                    log.error(f"[actions]-[{self.action_name}]"
                              f" query policy by vault:{vault_item['id']} failed,"
                              f" cause request id:{e.request_id}, msg:{e.error_msg}")
                    raise
        if not policy_id:
            # if inherit policy failed, list exists policy
            log.debug(f"[actions]-[{self.action_name}]"
                      f"inherit policy from vault failed, need inherit from exist policy")
            try:
                client = self.manager.get_client()
                request = ListPoliciesRequest()
                request.operation_type = "backup"
                response = client.list_policies(request)
                if response.to_dict()['policies'] and len(response.to_dict()['policies']) > 0:
                    policy_id = response.to_dict()['policies'][0]['id']
                    log.debug(f"[actions]-[{self.action_name}] use exist policy:{policy_id}")
                else:
                    policy_id = self.data.get('backup_policy', None)
                    log.debug(f"[actions]-[{self.action_name}] use config policy:{policy_id}")
            except exceptions.ClientRequestException as e:
                log.error(f"[actions]-[{self.action_name}]"
                          f" query exist policy list failed,"
                          f" cause request id:{e.request_id}, msg:{e.error_msg}")
                raise
        return policy_id
