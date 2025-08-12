# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import time
import re
import pytz

from c7n import utils
from c7n.exceptions import PolicyValidationError
from c7n.policy import execution, ServerlessExecutionMode, PullMode
from c7n.utils import type_schema, local_session
from c7n.version import version

from c7n_huaweicloud.cts import CloudTraceServiceEvents

log = logging.getLogger('c7n_huaweicloud.policy')


class FunctionGraphMode(ServerlessExecutionMode):
    schema = type_schema(
        'huaweicloud',
        log_level={
            'type': 'string',
            'default': 'WARNING',
            'enum': ['NOTSET', 'DEBUG', 'INFO', 'WARNING', 'WARN', 'ERROR', 'FATAL', 'CRITICAL'],
            'description': 'Log level when policy run in FunctionGraph functions.',
        },
        **{
            'execution-options': {'type': 'object'},
            'function-prefix': {'type': 'string'},
            'packages': {'type': 'array', 'items': {'type': 'string'}},
            # FunctionGraph pass through config
            'package': {'type': 'string'},
            'runtime': {'type': 'string', 'enum': ['Python3.9', 'Python3.10', 'Python3.12']},
            'timeout': {'type': 'number'},
            'handler': {'type': 'string'},
            'memory_size': {'type': 'number'},
            'xrole': {'type': 'string'},
            'func_vpc': {
                'oneOf': [
                    {
                        'type': 'object',
                        'required': ['vpc_name', 'subnet_name', 'cidr'],
                        'properties': {
                            'vpc_name': {'type': 'string'},
                            'subnet_name': {'type': 'string'},
                            'cidr': {'type': 'string'},
                            'is_safety': {'type': 'boolean'},
                        },
                    },
                    {
                        'type': 'object',
                        'required': ['vpc_id', 'subnet_id'],
                        'properties': {
                            'vpc_id': {'type': 'string'},
                            'subnet_id': {'type': 'string'},
                            'is_safety': {'type': 'boolean'},
                        },
                    },
                ],
            },
            'description': {'type': 'string'},
            'eg_agency': {'type': 'string'},
            'enable_lts_log': {'type': 'boolean'},
            'log_config': {
                'type': 'object',
                'required': ['group_name', 'stream_name'],
                'properties': {
                    'group_name': {'type': 'string'},
                    'stream_name': {'type': 'string'},
                    'group_id': {'type': 'string'},
                    'stream_id': {'type': 'string'},
                },
            },
            'func_tags': {
                'type': 'array',
                'items': {
                    'type': 'object',
                    'required': ['key', 'value'],
                    'properties': {
                        'key': {'type': 'string'},
                        'value': {'type': 'string'},
                    }
                }
            },
            'async_invoke_config': {
                'type': "object",
                'additionalProperties': False,
                'properties': {
                    'enable_async_status_log': {'type': 'boolean'},
                    'max_async_retry_attempts': {
                        'type': 'integer', 'default': 3, 'minimum': 0, 'maximum': 3,
                    },
                    'max_async_event_age_in_seconds': {
                        'type': 'integer', 'default': 3600, 'minimum': 1, 'maximum': 86400,
                    },
                    'log_group_id': {'type': 'string'},
                    'log_stream_id': {'type': 'string'},
                    'destination_config': {
                        'type': 'object',
                        'additionalProperties': False,
                        'properties': {
                            'on_success': {
                                'oneOf': [
                                    {
                                        'type': 'object',
                                        'additionalProperties': False,
                                        'properties': {
                                            'destination': {'type': 'string', 'enum': ['SMN']},
                                            'param': {
                                                'type': 'object',
                                                'additionalProperties': False,
                                                'properties': {
                                                    'topic_urn': {'type': 'string'},
                                                }
                                            }
                                        }
                                    },
                                    {
                                        'type': 'object',
                                        'additionalProperties': False,
                                        'properties': {
                                            'destination': {'type': 'string', 'enum': ['FunctionGraph']},  # noqa: E501
                                            'param': {
                                                'type': 'object',
                                                'additionalProperties': False,
                                                'properties': {
                                                    'func_urn': {'type': 'string'},
                                                }
                                            }
                                        }
                                    },
                                    {
                                        'type': 'object',
                                        'additionalProperties': False,
                                        'properties': {
                                            'destination': {'type': 'string', 'enum': ['DIS']},
                                            'param': {
                                                'type': 'object',
                                                'additionalProperties': False,
                                                'properties': {
                                                    'stream_name': {'type': 'string'},
                                                }
                                            }
                                        }
                                    },
                                    {
                                        'type': 'object',
                                        'additionalProperties': False,
                                        'properties': {
                                            'destination': {'type': 'string', 'enum': ['OBS']},
                                            'param': {
                                                'type': 'object',
                                                'additionalProperties': False,
                                                'properties': {
                                                    'bucket': {'type': 'string'},
                                                    'prefix': {'type': 'string'},
                                                    'expires': {
                                                        'type': 'integer',
                                                        'default': 0,
                                                        'minimum': 0,
                                                        'maximum': 365,
                                                    },
                                                }
                                            }
                                        }
                                    },
                                    {'type': 'null'},
                                ]
                            },
                            'on_failure': {
                                'oneOf': [
                                    {
                                        'type': 'object',
                                        'additionalProperties': False,
                                        'properties': {
                                            'destination': {'type': 'string', 'enum': ['SMN']},
                                            'param': {
                                                'type': 'object',
                                                'additionalProperties': False,
                                                'properties': {
                                                    'topic_urn': {'type': 'string'},
                                                }
                                            }
                                        }
                                    },
                                    {
                                        'type': 'object',
                                        'additionalProperties': False,
                                        'properties': {
                                            'destination': {'type': 'string', 'enum': ['FunctionGraph']},  # noqa: E501
                                            'param': {
                                                'type': 'object',
                                                'additionalProperties': False,
                                                'properties': {
                                                    'func_urn': {'type': 'string'},
                                                }
                                            }
                                        }
                                    },
                                    {
                                        'type': 'object',
                                        'additionalProperties': False,
                                        'properties': {
                                            'destination': {'type': 'string', 'enum': ['DIS']},
                                            'param': {
                                                'type': 'object',
                                                'additionalProperties': False,
                                                'properties': {
                                                    'stream_name': {'type': 'string'},
                                                }
                                            }
                                        }
                                    },
                                    {
                                        'type': 'object',
                                        'additionalProperties': False,
                                        'properties': {
                                            'destination': {'type': 'string', 'enum': ['OBS']},
                                            'param': {
                                                'type': 'object',
                                                'additionalProperties': False,
                                                'properties': {
                                                    'bucket': {'type': 'string'},
                                                    'prefix': {'type': 'string'},
                                                    'expires': {
                                                        'type': 'integer',
                                                        'default': 0,
                                                        'minimum': 0,
                                                        'maximum': 365,
                                                    },
                                                }
                                            }
                                        }
                                    },
                                    {'type': 'null'},
                                ]
                            }
                        }
                    }
                }
            },
            'user_data_encrypt_kms_key_id': {'type': 'string'},
            'code_encrypt_kms_key_id': {'type': 'string'},
        }
    )

    # action名称与yaml中action的type并非一致，添加请注意！
    actions_without_resources = ["notifymessagefromevent"]

    def validate(self):
        super(FunctionGraphMode, self).validate()
        prefix = self.policy.data['mode'].get('function-prefix', 'custodian-')
        MAX_FUNCTIONGRAPH_NAME_LENGTH = 64
        if len(prefix + self.policy.name) > MAX_FUNCTIONGRAPH_NAME_LENGTH:
            raise PolicyValidationError(
                "Custodian FunctionGraph policies[%s] has a max length with prefix of %s, "
                "prefix:%s" % (
                    self.policy.name,
                    MAX_FUNCTIONGRAPH_NAME_LENGTH,
                    prefix
                )
            )

    def resolve_resources(self, event):
        mode = self.policy.data.get('mode', {})
        resource_ids = CloudTraceServiceEvents.get_ids(event, mode)
        if resource_ids is None:
            raise ValueError("Unknown push event mode %s", self.data)
        if not resource_ids:
            log.warning("Could not find resource ids")
            return []
        log.info(f'[{self.policy.execution_mode}]-The resources ID list is: {resource_ids}')
        resources = self.policy.resource_manager.get_resources(resource_ids)
        if 'debug' in event:
            log.info("Resources %s", resources)
        events_in_mode = []
        sources_in_mode = []
        for e in mode.get('events'):
            events_in_mode.append(e['event'])
            sources_in_mode.append(e['source'])
        log.info(f'[{self.policy.execution_mode}]-The event occurred by {events_in_mode}, '
                 f'There are [{len(resources)}] resources in total.')
        return resources

    def run(self, event, context):
        if not self.policy.is_runnable(event):
            return
        actions = self.policy.resource_manager.actions
        # 判断actions，若只包含非资源类action无需查询资源
        if self.only_actions_without_resources(actions):
            with self.policy.ctx as ctx:
                if 'debug' in event:
                    self.policy.log.info(
                        "Invoking actions %s", self.policy.resource_manager.actions
                    )

                for action in actions:
                    self.policy.log.info(
                        "policy:%s invoking action:%s without resources",
                        self.policy.name,
                        action.name,
                    )
                    results = action.process(event)
                    ctx.output.write_file("action-%s" % action.name, utils.dumps(results))
                return
        resources = self.resolve_resources(event)
        if not resources:
            # 根据resource_ids未获取到资源
            return resources
        resources = self.policy.resource_manager.filter_resources(resources, event)
        log.info(f'[{self.policy.execution_mode}]-The filtered resources '
                 f'has [{len(resources)}] in total.')
        if not resources:
            # 根据filter未获取到资源
            return
        resources_list = []
        for resource in resources:
            resources_list.append(resource['id'])
        log.info(f'[{self.policy.execution_mode}]-The filtered resources ID list is: '
                 f'{resources_list}')

        return self.run_resource_set(event, resources)

    def only_actions_without_resources(self, actions):
        # 循环判断actions中action名称
        for action in actions:
            if action.name not in self.actions_without_resources:
                # 有任一action不在非资源类action列表中则返回false
                return False

        return True

    def run_resource_set(self, event, resources):
        from c7n.actions import EventAction

        with self.policy.ctx as ctx:
            ctx.metrics.put_metric(
                'ResourceCount', len(resources), 'Count', Scope="Policy", buffer=False
            )

            if 'debug' in event:
                self.policy.log.info(
                    "Invoking actions %s", self.policy.resource_manager.actions
                )

            ctx.output.write_file('resources.json', utils.dumps(resources, indent=2))

            for action in self.policy.resource_manager.actions:
                self.policy.log.info(
                    "policy:%s invoking action:%s resources:%d",
                    self.policy.name,
                    action.name,
                    len(resources),
                )
                if isinstance(action, EventAction):
                    results = action.process(resources, event)
                elif action.name in self.actions_without_resources:
                    results = action.process(event)
                else:
                    results = action.process(resources)
                ctx.output.write_file("action-%s" % action.name, utils.dumps(results))
        return resources

    @property
    def policy_functiongraph(self):
        from c7n_huaweicloud import mu
        return mu.PolicyFunctionGraph

    def provision(self):
        # auto tag function policies with mode and version, we use the
        # version in mugc to effect cleanups.
        tags = self.policy.data['mode'].setdefault('tags', {})
        tags['custodian-info'] = "mode=%s:version=%s" % (
            self.policy.data['mode']['type'], version)
        # auto tag with schedule name and group to link function to
        # EventBridge schedule when using schedule mode
        if self.policy.data['mode']['type'] == 'schedule':
            prefix = self.policy.data['mode'].get('function-prefix', 'custodian-')
            name = self.policy.data['name']
            group = self.policy.data['mode'].get('group-name', 'default')
            tags['custodian-schedule'] = f'name={prefix + name}:group={group}'

        from c7n_huaweicloud import mu
        with self.policy.ctx:
            self.policy.log.info(
                "Provisioning policy FunctionGraph: %s region: %s", self.policy.name,
                local_session(self.policy.session_factory).region)
            manager = mu.FunctionGraphManager(self.policy.session_factory)
            return manager.publish(
                self.policy_functiongraph(self.policy),
                role=self.policy.options.assume_role)

    def get_logs(self, start, end):
        pass


@execution.register('cloudtrace')
class CloudTraceMode(FunctionGraphMode):
    schema = type_schema(
        'cloudtrace',
        delay={'type': 'integer', 'description': 'sleep for delay seconds before processing an event'},  # noqa: E501
        trigger_name={'type': 'string'},
        events={'type': 'array', 'items': {
            'oneOf': [
                {'type': 'string'},
                {'type': 'object',
                 'required': ['event', 'source', 'ids'],
                 'properties': {
                     'source': {'type': 'string'},
                     'event': {'type': 'string'},
                     'ids': {'type': 'string'},
                     'code': {'type': 'integer'},
                 }}]
        }},
        rinherit=FunctionGraphMode.schema)

    def resolve_resources(self, event):
        delay = self.policy.data.get('mode', {}).get('delay')
        if delay:
            time.sleep(delay)
        return super().resolve_resources(event)


@execution.register('huaweicloud-periodic')
class PeriodicMode(FunctionGraphMode, PullMode):
    schema = type_schema(
        'huaweicloud-periodic',
        rinherit=FunctionGraphMode.schema,
        schedule={'type': 'string',
                  'description': 'When the schedule type is "Rate", this parameter means scheduled rule. '  # noqa: E501
                                 'When the schedule type is "Cron", this parameter means cron expression.'},  # noqa: E501
        schedule_type={'type': 'string',
                       'description': 'Rate: specifies the frequency (minutes, hours, or days) at which the function '  # noqa: E501
                                      'is invoked. If the unit is minute, the value cannot exceed 60. If the unit is '  # noqa: E501
                                      'hour, the value cannot exceed 24. If the unit is day, the value cannot exceed '  # noqa: E501
                                      '30. Cron: specifies a Cron expression to periodically invoke a function.',  # noqa: E501
                       'enum': ['Rate', 'Cron']},
        trigger_name={'type': 'string'},
        status={'type': 'string', 'enum': ['ACTIVE', 'DISABLED']},
        cron_tz={'type': 'string'},
        required=['schedule', 'schedule_type'],
    )

    def validate(self):
        mode = self.policy.data['mode']
        schedule_type = mode['schedule_type']
        if schedule_type == 'Rate':
            self.validate_rate(mode)
        elif schedule_type == 'Cron':
            self.validate_cron(mode)
        else:
            raise PolicyValidationError(
                "Custodian FunctionGraph policies[%s] has a invalid schedule_type [%s]." % (
                    self.policy.name,
                    schedule_type,
                )
            )

    def validate_rate(self, mode):
        rules = {
            'm': {'name': 'Minute', 'min': 1, 'max': 60},
            'h': {'name': 'Hour', 'min': 1, 'max': 24},
            'd': {'name': 'Date', 'min': 1, 'max': 30},
        }
        schedule = mode.get('schedule')
        unit = schedule[-1]
        if unit not in rules.keys():
            raise PolicyValidationError(
                "Custodian FunctionGraph policies[%s] has a invalid unit '%s', "
                "only support %s." % (
                    self.policy.name,
                    unit,
                    list(rules.keys()),
                )
            )
        try:
            num = int(schedule[:-1])
        except ValueError as e:
            raise PolicyValidationError(
                "Custodian FunctionGraph policies[%s] has a invalid Rate schedule number '%s', "
                "error message: %s." % (
                    self.policy.name,
                    schedule[:-1],
                    str(e),
                )
            )
        rule = rules[unit]
        if num > rule['max'] or num < rule['min']:
            raise PolicyValidationError(
                "Custodian FunctionGraph policies[%s] has a invalid Rate schedule "
                "number[%d] out of range %s: [%d, %d]" % (
                    self.policy.name,
                    num,
                    rule['name'],
                    rule['min'],
                    rule['max'],
                )
            )

    def validate_cron(self, mode):
        cron_tz = mode.get('cron_tz', "")
        # 1. 校验时区部分（如果存在）
        if cron_tz:
            self._validate_cron_timezone(cron_tz)

        schedule = mode.get('schedule')
        if schedule.startswith("@every"):
            # 2. 校验@every格式
            self._validate_at_every(schedule)
        else:
            # 3. 校验标准cron格式
            self._validate_cron_expression(schedule)

    def _validate_cron_timezone(self, timezone_str: str):
        """
        校验时区是否合法（如 "Asia/Shanghai"）
        """
        try:
            pytz.timezone(timezone_str)
            return
        except pytz.UnknownTimeZoneError:
            raise PolicyValidationError(
                "Custodian FunctionGraph policies[%s] has a invalid cron_tz [%s]." % (
                    self.policy.name,
                    timezone_str,
                )
            )

    def _validate_at_every(self, expression: str):
        """
        校验 @every 格式（如 @every 1h30m）
        """
        pattern = r"^@every\s+(?=\d+[hms])(?:(\d+h))?(?:(\d+m))?(?:(\d+s))?$"
        if not bool(re.match(pattern, expression)):
            raise PolicyValidationError(
                "Custodian FunctionGraph policies[%s] has a invalid @every cron expression [%s]." % (  # noqa: E501
                    self.policy.name,
                    expression,
                )
            )
        return

    def _validate_cron_expression(self, expression: str):
        """
        自定义校验 cron 表达式（支持 5 或 6 字段）
        """
        # 定义每个字段的规则（正则表达式）
        field_rules = {
            5: [
                r"^(\*|(\d+|\*/\d+|\d+-\d+)(/\d+)?(,\d+(-\d+)?(/\d+)?)*)$",  # 秒
                r"^(\*|(\d+|\*/\d+|\d+-\d+)(/\d+)?(,\d+(-\d+)?(/\d+)?)*)$",  # 分钟
                r"^(\*|(\d+|\*/\d+|\d+-\d+)(/\d+)?(,\d+(-\d+)?(/\d+)?)*)$",  # 小时
                r"^(\*|(\d+|\*/\d+|\d+-\d+)(/\d+)?(,\d+(-\d+)?(/\d+)?)*)$",  # 日
                r"^(\*|(\d+|\*/\d+|\d+-\d+)(/\d+)?(,\d+(-\d+)?("
                r"/\d+)?)*|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)$",  # 月（支持英文缩写）

            ],
            6: [
                r"^(\*|(\d+|\*/\d+|\d+-\d+)(/\d+)?(,\d+(-\d+)?(/\d+)?)*)$",  # 秒
                r"^(\*|(\d+|\*/\d+|\d+-\d+)(/\d+)?(,\d+(-\d+)?(/\d+)?)*)$",  # 分钟
                r"^(\*|(\d+|\*/\d+|\d+-\d+)(/\d+)?(,\d+(-\d+)?(/\d+)?)*)$",  # 小时
                r"^(\*|(\d+|\*/\d+|\d+-\d+)(/\d+)?(,\d+(-\d+)?(/\d+)?)*)$",  # 日
                r"^(\*|(\d+|\*/\d+|\d+-\d+)(/\d+)?(,\d+(-\d+)?("
                r"/\d+)?)*|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)$",  # 月（支持英文缩写）
                # 周（支持英文缩写）
                r"^(\*|(\d+|\*/\d+|\d+-\d+)(/\d+)?(,\d+(-\d+)?(/\d+)?)*|mon|tue|wed|thu|fri|sat|sun)$",
            ]
        }

        # 预处理英文缩写
        preprocessed_expression = self._preprocess_cron(expression)
        # 按空格分割字段
        fields = preprocessed_expression.split()
        num_fields = len(fields)
        if num_fields not in field_rules.keys():
            raise PolicyValidationError(
                "Custodian FunctionGraph policies[%s] has a invalid cron expression [%s]." % (
                    self.policy.name,
                    expression,
                )
            )

        # 校验基础格式
        for i, field in enumerate(fields):
            pattern = field_rules[num_fields][i]
            if not re.match(pattern, field.lower()):
                raise PolicyValidationError(
                    "Custodian FunctionGraph policies[%s] has a invalid cron expression [%s]"
                    "in position[%d], value is [%s]." % (
                        self.policy.name,
                        expression,
                        i + 1,
                        field
                    )
                )
        # 校验数值范围
        is_valid, error_message = self._validate_cron_ranges(preprocessed_expression, num_fields)
        if not is_valid:
            raise PolicyValidationError(
                "Custodian FunctionGraph policies[%s] has a invalid cron expression [%s], "
                "%s." % (
                    self.policy.name,
                    expression,
                    error_message,
                )
            )

        return

    @staticmethod
    def _validate_cron_ranges(expression: str, num_fields: int = 5) -> (bool, str):
        """
        校验各字段的数值范围
        """
        # 字段配置：名称、最小值、最大值
        field_config = [
            {'name': 'Second', 'min': 0, 'max': 59},
            {'name': 'Minute', 'min': 0, 'max': 59},
            {'name': 'Hour', 'min': 0, 'max': 23},
            {'name': 'Date', 'min': 1, 'max': 31},
            {'name': 'Month', 'min': 1, 'max': 12},
        ]
        if num_fields == 6:
            field_config.insert(5, {'name': 'Week', 'min': 0, 'max': 7})

        fields = expression.split()
        for i, field in enumerate(fields):
            config = field_config[i]
            for part in field.split(','):
                # 处理步长（如 */15 或 1-30/5）
                part = part.split('/')[0]
                if '-' in part:
                    start, end = map(int, part.split('-'))
                else:
                    start = end = int(part) if part != '*' else config['min']

                # 检查范围
                if start < config['min'] or end > config['max']:
                    return False, f'{config["name"]} out of range {config["min"]}-{config["max"]}: {field}'  # noqa: E501
        return True, ""

    @staticmethod
    def _preprocess_cron(expression: str) -> str:
        """
        将月份和周缩写替换为数字（如 JAN→1, MON→1）
        """
        month_map = {'JAN': 1, 'FEB': 2, 'MAR': 3, 'APR': 4, 'MAY': 5, 'JUN': 6,
                     'JUL': 7, 'AUG': 8, 'SEP': 9, 'OCT': 10, 'NOV': 11, 'DEC': 12}
        day_map = {'SUN': 0, 'MON': 1, 'TUE': 2, 'WED': 3, 'THU': 4, 'FRI': 5, 'SAT': 6}

        fields = expression.upper().split()
        if len(fields) >= 5:  # 替换月份
            fields[4] = ','.join([str(month_map.get(p, p)) for p in fields[4].split(',')])
        if len(fields) >= 6:  # 替换星期
            fields[5] = ','.join([str(day_map.get(p, p)) for p in fields[5].split(',')])
        return ' '.join(fields)

    def run(self, event, context):
        return PullMode.run(self)
