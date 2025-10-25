# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import json
import logging
import os
import uuid
from datetime import datetime, timezone

from c7n.config import Config
from c7n.policy import PolicyCollection
from c7n.resources import load_resources
from c7n.structure import StructureParser
from c7n.utils import reset_session_cache
# Load resource plugins
from c7n_huaweicloud.entry import initialize_huaweicloud
from c7n_huaweicloud.provider import HuaweiCloud

initialize_huaweicloud()

log = logging.getLogger('custodian.huaweicloud.functions')

logging.getLogger().setLevel(logging.INFO)


def run(event, context=None):
    start_time = datetime.now(timezone.utc)
    start_time_str = start_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    log.info('#[start_time@%s]#.', start_time_str)

    # policies file should always be valid in functions so do loading naively
    with open('/opt/function/code/config.json') as f:
        policy_config = json.load(f)

    if not policy_config or not policy_config.get('policies'):
        log.error('Invalid policy config')
        return False

    options_overrides = \
        policy_config['policies'][0].get('mode', {}).get('execution-options', {})

    # if output_dir specified use that, otherwise make a temp directory
    if 'output_dir' not in options_overrides:
        options_overrides['output_dir'] = get_tmp_output_dir()

    options_overrides['access_key_id'] = context.getSecurityAccessKey()
    options_overrides['secret_access_key'] = context.getSecuritySecretKey()
    options_overrides['security_token'] = context.getSecurityToken()
    options_overrides['region'] = context.getUserData('HUAWEI_DEFAULT_REGION')
    options_overrides['domain_id'] = context.getUserData('DOMAIN_ID')
    options_overrides['account_id'] = context.getUserData('DOMAIN_ID')
    options_overrides['account_name'] = context.getUserData('DOMAIN_NAME')

    # merge all our options in
    options = Config.empty(**options_overrides)

    load_resources(StructureParser().get_resource_types(policy_config))

    options = HuaweiCloud().initialize(options)
    policies = PolicyCollection.from_data(policy_config, options)
    log.debug(f'policies: {policies}')
    if policies:
        for p in policies:
            log.info(f'[{p.execution_mode}]-User with account: '
                     f'#[account@{context.getUserData("DOMAIN_NAME")}/'
                     f'{context.getUserData("DOMAIN_ID")}]#')
            log.info(f'[{p.execution_mode}]-generated a CTS event '
                     f'#[cts_id@{event["cts"]["trace_id"]}]# influenced the [{p.resource_type}],')
            log.info(f'[{p.execution_mode}]- and triggered the policy #[policy_name@{p.name}]#.')
            # Extend "account_name" in policy execution conditions with UserData
            p.conditions.env_vars['account_name'] = context.getUserData('DOMAIN_NAME')
            p.validate()
            p.push(event, context)

    reset_session_cache()
    finish_time = datetime.now(timezone.utc)
    finish_time_str = finish_time.strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    log.info('#[finish_time@%s]#.', finish_time_str)
    return True


def get_tmp_output_dir():
    output_dir = '/tmp/' + str(uuid.uuid4())  # nosec
    if not os.path.exists(output_dir):
        try:
            os.mkdir(output_dir)
        except OSError as error:
            log.warning("Unable to make output directory: {}".format(error))
    return output_dir
