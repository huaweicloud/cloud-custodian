# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
# 文件版权信息和许可证标识符

import logging  # 导入日志记录模块

from dateutil.parser import parse  # 从dateutil库导入parse函数，用于解析日期时间字符串
# 导入华为云核心SDK的异常类
from huaweicloudsdkcore.exceptions import exceptions
# 导入华为云Kafka V2 SDK中的模型类，用于构建API请求和处理响应
from huaweicloudsdkkafka.v2.model import (
    DeleteInstanceRequest,  # 删除实例请求
    # 查询实例详情请求
    # 查询实例列表请求
    # 更新实例请求 (可能已废弃或用于特定场景)
    # 更新实例请求体
    BatchCreateOrDeleteKafkaTagRequest,  # 批量创建或删除Kafka标签请求
    BatchCreateOrDeleteTagReq,  # 批量创建或删除标签请求体
    ModifyInstanceConfigsRequest,  # 修改实例配置请求
    ModifyInstanceConfigsReq,  # 修改实例配置请求体
    # 修改实例配置项
    ShowInstanceConfigsRequest,  # 查询实例配置请求
    # 重置管理员密码请求 (当前代码未使用)
    # 查询Kafka标签请求 (当前代码未使用)
    # 创建实例Topic请求 (当前代码未使用)
    # 查询实例Topic详情请求 (当前代码未使用)
    # 标签实体，用于表示标签的键值对 (此文件也定义了一个本地版本)
)
# 为避免与本地定义的TagEntity冲突，将导入的TagEntity重命名为SDKTagEntity
from huaweicloudsdkkafka.v2.model import TagEntity as SDKTagEntity

import c7n_huaweicloud.filters.revisions  # 导入华为云版本差异过滤器
# 导入Cloud Custodian核心过滤器和工具类
from c7n.filters import ValueFilter, AgeFilter, Filter, OPERATORS  # 导入值过滤器、时间过滤器、基础过滤器和操作符常量
from c7n.filters.core import ListItemFilter  # 导入列表项过滤器
from c7n.utils import type_schema, local_session  # 导入类型模式定义工具和获取本地会话的函数
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction  # 导入华为云基础Action类
from c7n_huaweicloud.filters.vpc import SecurityGroupFilter  # 导入安全组和子网过滤器
from c7n_huaweicloud.provider import resources  # 导入华为云资源注册器
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo  # 导入查询资源管理器和类型信息基类

# 获取一个日志记录器实例，用于记录与此模块相关的日志信息
log = logging.getLogger("custodian.huaweicloud.resources.kafka")


# 定义一个本地的TagEntity类，用于简化标签操作。
# 注意：华为云SDK也提供了TagEntity，这里可能是为了特定场景或兼容性。
class TagEntity:
    """简单的标签结构，用于表示键值对"""

    def __init__(self, key, value=None):
        """
        初始化标签实体。
        :param key: 标签键 (必填)
        :param value: 标签值 (可选)
        """
        self.key = key
        self.value = value


@resources.register('kafka')
class Kafka(QueryResourceManager):
    """华为云分布式消息服务 Kafka (DMS Kafka) 实例的资源管理器。

    此类负责发现、过滤和管理华为云上的Kafka实例资源。
    它继承自QueryResourceManager，利用其能力来查询和处理资源列表。

    :example:
    定义一个简单的策略来获取所有Kafka实例：

    .. code-block:: yaml

        policies:
          - name: kafka-instances-discovery # 策略名称
            resource: huaweicloud.kafka      # 指定资源类型为华为云Kafka
    """

    class resource_type(TypeInfo):
        """定义Kafka资源的元数据和类型信息"""
        service = 'kafka'  # 指定对应的华为云服务名称
        # 指定用于枚举资源的API操作、结果列表键和分页参数(如果有)
        # 'list_instances' 是API方法名
        # 'instances' 是响应中包含实例列表的字段名
        # 'offset' 是用于分页的参数名
        enum_spec = ('list_instances', 'instances', 'offset', 10)
        id = 'instance_id'  # 指定资源唯一标识符的字段名
        name = 'name'  # 指定资源名称的字段名
        date = 'created_at'  # 指定表示资源创建时间的字段名
        tag = True  # 指示此资源支持标签
        tag_resource_type = 'kafka'  # 指定用于查询标签的资源类型 (通常与service一致)

    def augment(self, resources):
        """
        增强从API获取的原始资源数据。

        此方法主要用于将华为云API返回的标签列表格式（通常是包含 'key' 和 'value' 字段的字典列表）
        转换为Cloud Custodian内部更常用的AWS兼容格式（包含 'Key' 和 'Value' 字段的字典列表）。
        这提高了跨云提供商策略的一致性。

        :param resources: 从API获取的原始资源字典列表
        :return: 增强后的资源字典列表，其中标签已转换为 'Tags' 键下的AWS兼容格式
        """
        for r in resources:
            # 检查原始资源字典中是否存在 'tags' 键
            if 'tags' not in r:
                continue  # 如果没有标签，则跳过此资源
            tags = []
            # 遍历原始标签列表
            for tag_entity in r['tags']:
                # 将每个标签转换为 {'Key': ..., 'Value': ...} 格式
                tags.append({'Key': tag_entity.get('key'), 'Value': tag_entity.get('value')})
            # 将转换后的标签列表添加到资源字典中，键名为 'Tags'
            r['Tags'] = tags
        return resources


@Kafka.filter_registry.register('security-group')
class KafkaSecurityGroupFilter(SecurityGroupFilter):
    """
    根据关联的安全组过滤Kafka实例。

    允许用户基于Kafka实例使用的安全组的属性（如名称、ID）来筛选实例。
    继承自通用的 `SecurityGroupFilter`。

    :example:
    查找使用了名为 'allow-public' 的安全组的Kafka实例：

    .. code-block:: yaml

        policies:
          - name: kafka-with-public-sg
            resource: huaweicloud.kafka
            filters:
              - type: security-group        # 过滤器类型
                key: name              # 要匹配的安全组属性 (例如 name, Id)
                value: allow-public         # 要匹配的值
    """
    # 指定Kafka资源字典中包含安全组ID的字段名
    RelatedIdsExpression = "security_group_id"


@Kafka.filter_registry.register('age')
class KafkaAgeFilter(AgeFilter):
    """
    根据Kafka实例的创建时间（年龄）进行过滤。

    允许用户筛选出比指定时间更早或更晚创建的实例。
    继承自通用的 `AgeFilter`。

    :example:
    查找创建时间超过30天的Kafka实例：

    .. code-block:: yaml

        policies:
          - name: kafka-older-than-30-days
            resource: huaweicloud.kafka
            filters:
              - type: age                   # 过滤器类型
                days: 30                    # 指定天数
                op: gt                      # 操作符，gt 表示 '大于' (older than)
                                            # 其他可用操作符如 lt (younger than), ge, le
    """
    # 定义此过滤器的输入模式 (schema)
    schema = type_schema(
        'age',  # 过滤器类型名称
        # 定义比较操作符，引用通用过滤器定义
        op={'$ref': '#/definitions/filters_common/comparison_operators'},
        # 定义时间单位参数
        days={'type': 'number'},  # 天数
        hours={'type': 'number'},  # 小时数
        minutes={'type': 'number'}  # 分钟数
    )

    # 指定资源字典中表示创建时间的字段名
    date_attribute = "created_at"

    def get_resource_date(self, resource):
        """
        从资源字典中获取并解析创建时间。

        :param resource: 单个Kafka实例的资源字典
        :return: 解析后的datetime对象，如果无法获取或解析则返回None
        """
        from datetime import datetime
        # 检查资源字典中是否存在指定的日期属性
        date_value = resource.get(self.date_attribute)
        if not date_value:
            return None

        # 尝试将值解析为毫秒时间戳
        if isinstance(date_value, (str, int)) and str(date_value).isdigit():
            try:
                # 假设是毫秒时间戳，转换为秒
                timestamp_ms = int(date_value)
                timestamp_s = timestamp_ms / 1000.0
                # 从时间戳创建datetime对象 (UTC)
                return datetime.utcfromtimestamp(timestamp_s)
            except (ValueError, TypeError, OverflowError) as e:
                log.debug(f"将值 '{date_value}' 作为毫秒时间戳解析失败: {e}")
                # 如果作为毫秒时间戳解析失败，继续尝试使用 dateutil.parser

        # 如果不是纯数字或者作为毫秒时间戳解析失败，尝试使用dateutil.parser解析通用时间字符串
        try:
            return parse(str(date_value))  # 确保输入是字符串
        except Exception as e:
            # 如果解析失败，记录错误并返回None
            log.warning(f"无法解析Kafka实例 {resource.get('instance_id', '未知ID')} 的创建时间 '{date_value}': {e}")
            return None


@Kafka.filter_registry.register('list-item')
class KafkaListItemFilter(ListItemFilter):
    """
    对资源属性中的列表项进行过滤。

    此过滤器允许检查资源字典中某个键对应的值（必须是列表），并根据列表中的项进行过滤。
    例如，可以检查实例是否部署在特定的可用区，或者是否包含特定的标签。
    继承自核心的 `ListItemFilter`。

    :example:
    查找部署在 'cn-north-4a' 或 'cn-north-4b' 可用区的Kafka实例：

    .. code-block:: yaml

        policies:
          - name: kafka-multi-az
            resource: huaweicloud.kafka
            filters:
              - type: list-item             # 过滤器类型
                key: available_zones        # 要检查的资源属性键名 (该键对应的值应为列表)
                # key_path: "[].name"       # (可选) JMESPath 表达式，用于从列表项字典中提取用于比较的值
                                            # 如果列表项是简单类型（如字符串），则不需要 key_path
                op: in                      # 比较操作符 (例如 in, not-in, contains, eq, ...)
                value: ["cn-north-4a", "cn-north-4b"] # 要比较的值或值列表

    可以过滤的列表属性示例 (具体取决于API返回的字段):
    - `available_zones`: 可用区列表 (通常是字符串列表)
    - `tags`: 标签列表 (通常是字典列表, 需要 `key_path` 如 `[?key=='Environment'].value | [0]` 或配合 `augment` 后的 `Tags` 使用)
    - `ipv6_connect_addresses`: IPv6连接地址列表
    """
    # 定义此过滤器的输入模式 (schema)
    schema = type_schema(
        'list-item',  # 过滤器类型名称
        # --- 以下参数继承自 ListItemFilter ---
        # count: 匹配项的数量
        count={'type': 'integer', 'minimum': 0},
        # count_op: 对数量进行比较的操作符 (eq, ne, gt, ge, lt, le)
        count_op={'enum': list(OPERATORS.keys())},
        # op: 对列表项的值进行比较的操作符
        op={'enum': list(OPERATORS.keys())},
        # value: 用于比较的值，可以是单个值或列表
        value={'oneOf': [
            {'type': 'array'},
            {'type': 'string'},
            {'type': 'boolean'},
            {'type': 'number'},
            {'type': 'object'}
        ]},
        # key: 要检查的资源属性键名，其值必须是列表
        key={'oneOf': [
            {'type': 'string'},
            {'type': 'integer', 'minimum': 0},  # 键也可以是整数（如果资源字典的键是整数）
            {'type': 'array', 'items': {'type': 'string'}}  # 或路径列表
        ]},
        # key_path: (可选) JMESPath 表达式，用于从列表项中提取比较值
        key_path={'type': 'string'},
        # 声明 'key' 参数是必需的
        required=['key']
    )

    def process(self, resources, event=None):
        """
        处理资源列表，对列表类型的属性项进行过滤。

        重写 ListItemFilter 的 process 方法，解决字符串列表处理问题。

        :param resources: 要过滤的资源列表
        :param event: 可选的事件上下文
        :return: 过滤后的资源列表
        """
        # 从过滤器配置获取参数
        key = self.data.get('key')
        key_path = self.data.get('key_path')
        count = self.data.get('count')
        count_op = self.data.get('count_op')

        # 获取比较操作符和比较值
        op_name = self.data.get('op', 'in')
        op = OPERATORS.get(op_name)
        value = self.data.get('value')

        # 初始化结果列表
        results = []

        # 处理每个资源
        for resource in resources:
            # 获取要检查的列表属性
            if isinstance(key, list):
                list_values = self.get_resource_value_list(resource, key)
            else:
                list_values = resource.get(key, [])

            if not list_values:
                continue

            # 跟踪匹配的列表项数量
            matches = 0

            # 遍历列表中的每一项
            for list_value in list_values:
                # 获取用于比较的值
                if key_path:
                    import jmespath
                    # 如果指定了key_path，尝试从列表项中提取
                    if isinstance(list_value, dict):
                        compare_value = jmespath.search(key_path, list_value)
                    else:
                        # 如果列表项不是字典且指定了key_path，可能无法正确提取
                        # 在这种情况下，记录警告并跳过
                        self.log.warning(
                            f"指定了key_path '{key_path}'，但列表项不是字典: {list_value}")
                        continue
                else:
                    # 否则直接使用列表项本身
                    compare_value = list_value

                # 执行比较操作，根据操作符和值类型进行适当处理
                match = False

                # 特殊处理eq和ne操作符当value是列表的情况
                if op_name == 'eq' and isinstance(value, list):
                    # 当op为eq且value为列表时，检查compare_value是否在value列表中
                    match = compare_value in value
                elif op_name == 'ne' and isinstance(value, list):
                    # 当op为ne且value为列表时，检查compare_value是否不在value列表中
                    match = compare_value not in value
                # 对于需要单值比较的操作符(gt, lt, ge, le)当value为列表时的处理
                elif op_name in ('gt', 'lt', 'ge', 'le') and isinstance(value, list):
                    self.log.warning(
                        f"操作符 '{op_name}' 不适合与列表值 {value} 比较，将跳过此比较")
                    match = False
                # 正常的操作符执行
                else:
                    match = op(compare_value, value)

                if match:
                    matches += 1

            # 如果指定了count，检查匹配的数量是否符合条件
            if count is not None and count_op:
                count_matched = OPERATORS[count_op](matches, count)
                if count_matched:
                    results.append(resource)
            # 否则，如果至少有一个匹配项，则包含此资源
            elif matches > 0:
                results.append(resource)

        return results


@Kafka.filter_registry.register('config-compliance')
class KafkaConfigComplianceFilter(ValueFilter):
    """
    检查Kafka实例的特定配置项是否符合期望值。

    此过滤器会调用华为云API查询指定Kafka实例的配置信息，
    然后将指定的配置项 (`key`) 的实际值与期望值 (`value`) 进行比较。

    :example:
    查找 'auto.create.topics.enable' 配置项未设置为 'false' 的Kafka实例：

    .. code-block:: yaml

        policies:
          - name: kafka-with-auto-topic-creation
            resource: huaweicloud.kafka
            filters:
              - type: config-compliance      # 过滤器类型
                key: auto.create.topics.enable # 要检查的Kafka配置项名称
                op: ne                      # 比较操作符 (ne 表示 '不等于')
                value: false                # 期望的值
    """
    # 定义此过滤器的输入模式 (schema)
    schema = type_schema(
        'config-compliance',  # 过滤器类型名称
        rinherit=ValueFilter.schema,
        # 以下属性是对ValueFilter.schema的扩展
        key={'type': 'string'},  # 要检查的配置项名称
        op={'enum': list(OPERATORS.keys()), 'default': 'eq'},  # 比较操作符，默认为 'eq' (等于)
        # 期望的值，可以是字符串、布尔值或数字
        value={'oneOf': [
            {'type': 'string'},
            {'type': 'boolean'},
            {'type': 'number'}
        ]},
        # 声明 'key' 和 'value' 参数是必需的
        required=['key', 'value']
    )
    schema_alias = True

    def get_permissions(self):
        return ('kafka:showInstanceConfigs',)

    def process(self, resources, event=None):
        # 初始化基础配置
        key = self.data.get('key')
        op = self.data.get('op', 'eq')
        value = self.data.get('value')

        # 获取华为云Kafka服务的客户端
        client = local_session(self.manager.session_factory).client('kafka')
        results = []
        for resource in resources:
            instance_id = resource.get('instance_id')
            if not instance_id:
                log.warning(f"跳过缺少 'instance_id' 的Kafka资源: {resource.get('name', '未知名称')}")
                continue

            try:
                # 构造查询实例配置的请求
                request = ShowInstanceConfigsRequest(instance_id=instance_id)
                # 调用API获取配置信息
                response = client.show_instance_configs(request)
                configs = response.kafka_configs  # 获取配置列表

                # 为资源添加配置信息以便ValueFilter处理
                config_found = False
                for config in configs:
                    if config.name == key:
                        config_found = True
                        actual_value_str = config.value  # API返回的值通常是字符串
                        actual_value = actual_value_str  # 默认使用字符串值
                        # 根据期望值的类型尝试转换实际值
                        if isinstance(value, bool):
                            # 将字符串转换为布尔值 ('true' -> True, 其他 -> False)
                            actual_value = actual_value_str.lower() == 'true'
                        elif isinstance(value, (int, float)):
                            # 尝试将字符串转换为期望的数字类型
                            try:
                                actual_value = type(value)(actual_value_str)
                            except (ValueError, TypeError):
                                log.warning(
                                    f"无法将Kafka实例 {instance_id} 的配置项 '{key}' 的值 '{actual_value_str}' "
                                    f"转换为类型 {type(value).__name__}。将使用字符串进行比较。"
                                )
                                actual_value = actual_value_str  # 回退到字符串比较

                        # 将配置值添加到资源中
                        resource['KafkaConfig'] = {key: actual_value}
                        break

                if not config_found:
                    log.warning(f"未能在Kafka实例 {instance_id} 中找到配置项 '{key}'")
                    resource['KafkaConfig'] = {key: None}

            except exceptions.ClientRequestException as e:
                # 处理API请求异常
                log.error(f"获取Kafka实例 {instance_id} 的配置失败: {e.error_msg} (状态码: {e.status_code})")
                continue
            except Exception as e:
                # 处理其他潜在异常
                log.error(f"处理Kafka实例 {instance_id} 时发生未知错误: {str(e)}")
                continue

        # 使用父类的match方法对资源进行过滤
        original_key = self.data.get('key')
        self.data['key'] = f'KafkaConfig."{original_key}"'

        try:
            filtered = super(KafkaConfigComplianceFilter, self).process(resources, event)
        finally:
            # 恢复原始键，避免影响其他过滤器
            self.data['key'] = original_key
        return filtered


# 不做
@Kafka.filter_registry.register('json-diff')
class KafkaJsonDiffFilter(c7n_huaweicloud.filters.revisions.JsonDiff):
    """
    对比Kafka实例配置与历史版本的差异。

    此过滤器利用华为云Config服务来追踪和提供资源的详细历史配置记录以供比较。
    用于检测资源的配置是否发生了变化。

    :example:
    检测Kafka实例的配置自上一个版本以来是否发生变化：

    .. code-block:: yaml

        policies:
          - name: kafka-config-changed-check
            resource: huaweicloud.kafka
            filters:
              - type: json-diff             # 过滤器类型
                selector: previous          # 选择比较对象 ('previous' 或 'date')
                # path: "config.replication.factor" # (可选) 指定要比较的JSON路径
    """

    def get_permissions(self):
        return ('config:showResourceHistory',)


@Kafka.filter_registry.register('marked-for-op')
class KafkaMarkedForOpFilter(Filter):
    """
    根据特定的"标记操作"标签过滤Kafka实例。

    此过滤器用于查找那些被 `mark-for-op` action 标记了将在未来某个时间执行特定操作（如删除、停止）的实例。
    它会检查指定的标签键 (`tag`)，解析标签值中包含的操作类型和预定执行时间，并与当前时间比较。
    
    :example:
    查找所有被标记为将在未来（或已到期）删除，且标签键为 'custodian_cleanup' 的Kafka实例：

    .. code-block:: yaml

        policies:
          - name: find-kafka-marked-for-deletion
            resource: huaweicloud.kafka
            filters:
              - type: marked-for-op          # 过滤器类型
                op: delete                  # 要查找的操作类型 ('delete', 'stop', 'restart')
                tag: custodian_cleanup      # 用于标记操作的标签键
                # skew: 1                   # (可选) 时间偏移量（天），允许提前 N 天匹配
                # skew_hours: 2             # (可选) 时间偏移量（小时）
    """
    # 定义此过滤器的输入模式 (schema)
    schema = type_schema(
        'marked-for-op',  # 过滤器类型名称
        # 要匹配的操作类型
        op={'type': 'string', 'enum': ['delete', 'stop', 'restart']},
        # 用于标记操作的标签键，默认为 'mark-for-op-custodian'
        tag={'type': 'string', 'default': 'mark-for-op-custodian'},
        # (可选) 时间偏移量（天），允许在预定时间前N天匹配，默认为0
        skew={'type': 'number', 'default': 0},
        # (可选) 时间偏移量（小时），允许在预定时间前N小时匹配，默认为0
        skew_hours={'type': 'number', 'default': 0},
        # 时区，默认为 'utc'
        tz={'type': 'string', 'default': 'utc'},
    )
    schema_alias = True
    DEFAULT_TAG = "mark-for-op-custodian"

    def __init__(self, data, manager=None):
        super(KafkaMarkedForOpFilter, self).__init__(data, manager)
        self.tag = self.data.get('tag', self.DEFAULT_TAG)
        self.op = self.data.get('op')
        self.skew = self.data.get('skew', 0)
        self.skew_hours = self.data.get('skew_hours', 0)
        from dateutil import tz as tzutil
        from c7n.filters.offhours import Time
        self.tz = tzutil.gettz(Time.TZ_ALIASES.get(self.data.get('tz', 'utc')))

    def process(self, resources, event=None):
        results = []
        for resource in resources:
            tags = self._get_tags_from_resource(resource)
            if not tags:
                continue

            tag_value = tags.get(self.tag)
            if not tag_value:
                continue

            if self._process_tag_value(tag_value):
                results.append(resource)

        return results

    def _process_tag_value(self, tag_value):
        """处理标签值，判断是否符合过滤条件"""
        if not tag_value:
            return False

        # 处理KafkaMarkForOpAction创建的值格式 "操作@时间戳"
        if '@' in tag_value:
            action, action_date_str = tag_value.strip().split('@', 1)
        # 兼容旧格式 "操作_时间戳"
        elif '_' in tag_value:
            action, action_date_str = tag_value.strip().split('_', 1)
        else:
            return False
        if action != self.op:
            return False

        try:
            # 尝试直接解析KafkaMarkForOpAction生成的标准时间戳格式 '%Y/%m/%d %H:%M:%S UTC'
            from dateutil.parser import parse
            action_date = parse(action_date_str)
        except Exception as e:
            # 如果标准解析失败，尝试使用旧的格式转换逻辑
            try:
                # 旧的时间格式转换逻辑
                modified_date_str = self._replace_nth_regex(action_date_str, "-", " ", 3)
                modified_date_str = self._replace_nth_regex(modified_date_str, "-", ":", 3)
                modified_date_str = self._replace_nth_regex(modified_date_str, "-", " ", 3)

                action_date = parse(modified_date_str)
            except Exception as nested_e:
                self.log.warning(f"无法解析标签值: {tag_value}, 错误: {str(nested_e)}")
                return False

        from datetime import datetime, timedelta
        if action_date.tzinfo:
            # 如果action_date带时区，转换到指定时区
            action_date = action_date.astimezone(self.tz)
            current_date = datetime.now(tz=self.tz)
        else:
            current_date = datetime.now()
        return current_date >= (
                action_date - timedelta(days=self.skew, hours=self.skew_hours))

    def _replace_nth_regex(self, s, old, new, n):
        """替换字符串中第n次出现的old为new"""
        import re
        pattern = re.compile(re.escape(old))
        matches = list(pattern.finditer(s))
        if len(matches) < n:
            return s
        match = matches[n - 1]
        return s[:match.start()] + new + s[match.end():]

    def _get_tags_from_resource(self, resource):
        """从资源中获取标签字典"""
        try:
            tags = {}
            # 处理原始Tags列表，转换为字典形式
            if 'Tags' in resource:
                for tag in resource.get('Tags', []):
                    if isinstance(tag, dict) and 'Key' in tag and 'Value' in tag:
                        tags[tag['Key']] = tag['Value']
            # 处理原始tags列表，多种可能格式
            elif 'tags' in resource:
                raw_tags = resource['tags']
                if isinstance(raw_tags, dict):
                    tags = raw_tags
                elif isinstance(raw_tags, list):
                    if all(isinstance(item, dict) and 'key' in item and 'value' in item for item in raw_tags):
                        # 兼容华为云特有的 [{key: k1, value: v1}] 格式
                        for item in raw_tags:
                            tags[item['key']] = item['value']
                    elif all(isinstance(item, dict) and len(item) == 1 for item in raw_tags):
                        # 兼容 [{k1: v1}, {k2: v2}] 格式
                        for item in raw_tags:
                            key, value = list(item.items())[0]
                            tags[key] = value
            return tags
        except Exception as e:
            self.log.error(f"解析资源标签失败: {str(e)}")
            return {}


@Kafka.action_registry.register('mark-for-op')
class KafkaMarkForOpAction(HuaweiCloudBaseAction):
    """
    为Kafka实例添加一个"标记操作"标签。

    此动作用于标记资源，以便稍后由其他策略（使用 `marked-for-op` 过滤器）识别并执行指定的操作。
    它会在资源上创建一个标签，标签的值包含了指定的操作类型 (`op`) 和一个未来的执行时间戳。

    :example:
    标记创建时间超过90天的Kafka实例，让它们在7天后被删除 (需要另一个策略配合 `marked-for-op` 过滤器和 `delete` action 来实际删除)：

    .. code-block:: yaml

        policies:
          - name: mark-old-kafka-for-deletion
            resource: huaweicloud.kafka
            filters:
              - type: age
                days: 90
                op: gt
            actions:
              - type: mark-for-op          # 动作类型
                op: delete                  # 要标记的操作 ('delete', 'stop', 'restart')
                days: 7                     # 延迟执行的天数 (从现在开始)
                # hours: 0                  # (可选) 延迟执行的小时数
                tag: custodian_cleanup      # 用于标记的标签键 (应与 `marked-for-op` 过滤器中的tag一致)
    """
    # 定义此动作的输入模式 (schema)
    schema = type_schema(
        'mark-for-op',  # 动作类型名称
        # 要标记的操作类型
        op={'enum': ['delete', 'stop', 'restart']},
        # 延迟执行的天数 (从当前时间算起)
        days={'type': 'number', 'minimum': 0, 'default': 0},
        # 延迟执行的小时数 (从当前时间算起)
        hours={'type': 'number', 'minimum': 0, 'default': 0},
        # 用于标记操作的标签键，默认为 'mark-for-op-custodian'
        tag={'type': 'string', 'default': 'mark-for-op-custodian'},
        # 声明 'op' 参数是必需的
        required=['op']
    )

    def perform_action(self, resource):
        """
        对单个资源执行标记操作。

        :param resource: 要标记的Kafka实例资源字典
        :return: None 或 API响应 (根据基类要求，但此操作通常不直接返回)
        """
        # 从策略定义中获取参数
        op = self.data.get('op')
        tag_key = self.data.get('tag', 'mark-for-op-custodian')
        days = self.data.get('days', 0)
        hours = self.data.get('hours', 0)

        instance_id = resource.get('instance_id')
        if not instance_id:
            log.error(f"无法标记缺少 'instance_id' 的Kafka资源: {resource.get('name', '未知名称')}")
            return None

        # 计算预定的执行时间 (UTC)
        from datetime import datetime, timedelta
        try:
            action_time = datetime.utcnow() + timedelta(days=days, hours=hours)
            # 格式化时间戳字符串，格式必须与 TagActionFilter 解析的格式一致
            action_time_str = action_time.strftime('%Y/%m/%d %H:%M:%S UTC')
        except OverflowError:
            log.error(f"为 Kafka 实例 {instance_id} 计算的标记操作时间戳无效 (天数={days}, 小时数={hours})")
            return None

        # 构建标签值，格式为 "操作_时间戳"
        tag_value = f"{op}@{action_time_str}"  # 使用 @ 作为分隔符，更清晰

        # 调用内部方法创建标签
        self._create_or_update_tag(resource, tag_key, tag_value)

        return None  # 通常标记操作不返回特定结果

    def _create_or_update_tag(self, resource, key, value):
        """
        为指定资源创建或更新标签。
        (此辅助方法与后续的 Tag/AutoTagUser/RenameTag 中的 _create_tag 类似，
         可以考虑提取到基类或共享工具类中以减少重复代码)

        :param resource: 目标资源字典
        :param key: 标签键
        :param value: 标签值
        """
        instance_id = resource['instance_id']
        instance_name = resource.get('name', '未知名称')
        # 获取华为云Kafka客户端
        client = self.manager.get_client()
        # 构造标签实体 (使用华为云SDK的TagEntity类)
        tag_entity = SDKTagEntity(key=key, value=value)
        try:
            # 构造批量创建/删除标签的请求
            request = BatchCreateOrDeleteKafkaTagRequest()
            request.instance_id = instance_id
            request.body = BatchCreateOrDeleteTagReq()
            # 注意：华为云的批量接口通常用于创建或删除，没有直接的"更新"操作。
            # 如果标签键已存在，此"create"操作可能会覆盖现有值，或者在某些服务中失败。
            # 这里的行为依赖于华为云Kafka API的具体实现。
            # 稳妥起见，可以先尝试删除同名标签，再创建新标签，但这会增加API调用次数。
            # 当前实现假设 'create' 会覆盖。
            request.body.action = "create"
            request.body.tags = [tag_entity]  # 包含要创建/更新的标签
            # 调用API执行操作
            client.batch_create_or_delete_kafka_tag(request)
            log.info(f"已为Kafka实例 {instance_name} ({instance_id}) 添加或更新标签: {key}={value}")
        except exceptions.ClientRequestException as e:
            # 处理API请求异常
            log.error(
                f"为Kafka实例 {instance_name} ({instance_id}) 添加或更新标签 {key} 失败: "
                f"{e.error_msg} (状态码: {e.status_code})"
            )
        except Exception as e:
            # 处理其他潜在异常
            log.error(f"为Kafka实例 {instance_name} ({instance_id}) 添加或更新标签 {key} 时发生未知错误: {str(e)}")


@Kafka.action_registry.register('auto-tag-user')
class KafkaAutoTagUser(HuaweiCloudBaseAction):
    """
    (概念性) 自动为Kafka实例添加创建者用户标签。

    **重要提示:** 此动作依赖于资源数据中包含创建者信息（如此处假设的 'user_name' 字段）。
    华为云API返回的Kafka实例信息**通常不直接包含创建者的IAM用户名**。
    因此，此动作的有效性取决于 `QueryResourceManager` 或其 `augment` 方法是否能通过其他途径
    （如查询操作日志服务 CTS）获取并填充 `user_name` 字段。如果无法获取，标签值将是 'unknown'。

    :example:
    为缺少 'Creator' 标签的Kafka实例添加该标签，值为创建者用户名（如果能获取到）：

    .. code-block:: yaml

        policies:
          - name: tag-kafka-creator-if-missing
            resource: huaweicloud.kafka
            filters:
              - "tag:Creator": absent       # 筛选出没有 'Creator' 标签的实例
            actions:
              - type: auto-tag-user         # 动作类型
                tag: Creator                # 要添加的标签键 (默认为 'CreatorName')
    """
    # 定义此动作的输入模式 (schema)
    schema = type_schema(
        'auto-tag-user',  # 动作类型名称
        # 指定要添加的标签键，默认为 'CreatorName'
        tag={'type': 'string', 'default': 'CreatorName'},
        # 此动作用于获取用户ID的模式，默认为 'resource' (即尝试从资源字典获取)
        # 可选 'account' (可能表示当前执行策略的账户，但在此上下文意义不大)
        mode={'type': 'string', 'enum': ['resource', 'account'], 'default': 'resource'},
        # 如果 mode 为 'resource'，指定从资源字典中获取用户名的键，默认为 'creator'
        user_key={'type': 'string', 'default': 'creator'},  # 改为 'creator' 可能更通用
        # 是否更新已存在的标签，默认为 True
        update={'type': 'boolean', 'default': True},
        required=[]  # 没有必需参数 (因为都有默认值)
    )

    # 权限声明 (如果需要特定权限才能获取用户信息)
    # permissions = ('cts:listOperations',) # 例如，如果需要查CTS日志

    def perform_action(self, resource):
        """
        对单个资源执行自动标记用户操作。

        :param resource: 要标记的Kafka实例资源字典
        :return: None
        """
        tag_key = self.data.get('tag', 'CreatorName')
        mode = self.data.get('mode', 'resource')
        user_key = self.data.get('user_key', 'creator')  # 使用 schema 中的 user_key
        update = self.data.get('update', True)

        instance_id = resource.get('instance_id')
        instance_name = resource.get('name', '未知名称')
        if not instance_id:
            log.error(f"无法自动标记缺少 'instance_id' 的Kafka资源: {instance_name}")
            return None

        # 检查是否需要更新，以及标签是否已存在
        if not update and tag_key in [t.get('Key') for t in resource.get('Tags', [])]:
            log.debug(f"Kafka实例 {instance_name} ({instance_id}) 已存在标签 '{tag_key}' 且不允许更新，跳过。")
            return None

        user_name = 'unknown'  # 默认值
        if mode == 'resource':
            # 尝试从资源字典中获取用户名
            user_name = resource.get(user_key, 'unknown')
            if user_name == 'unknown':
                # 如果默认的 'creator' 键找不到，也尝试一下原始代码中的 'user_name'
                user_name = resource.get('user_name', 'unknown')

            # 如果仍然是 unknown，可以考虑增加查询 CTS 日志的逻辑 (需要额外实现和权限)
            if user_name == 'unknown':
                log.warning(
                    f"无法从资源数据中找到Kafka实例 {instance_name} ({instance_id}) 的创建者信息 "
                    f"(尝试过键: '{user_key}', 'user_name'). 将使用 'unknown'。"
                )
        elif mode == 'account':
            # 获取执行策略的账户信息 (此处逻辑需要根据实际情况实现)
            # user_name = local_session(self.manager.session_factory).get_current_user_id() or 'unknown'
            log.warning("'account' 模式在 KafkaAutoTagUser 中尚未完全实现。")
            user_name = 'unknown'

        # 调用内部方法创建或更新标签
        # (复用 KafkaMarkForOpAction 中的辅助方法)
        kafka_marker = KafkaMarkForOpAction(self.data, self.manager)
        kafka_marker._create_or_update_tag(resource, tag_key, user_name)

        return None

    # _create_or_update_tag 方法已在 KafkaMarkForOpAction 中定义，此处不再重复


@Kafka.action_registry.register('tag')
class KafkaTag(HuaweiCloudBaseAction):
    """
    为Kafka实例添加或更新一个指定的标签。

    这是一个通用的标签添加动作，允许用户直接指定要添加的标签键和值。
    如果同名标签键已存在，默认会覆盖其值。

    :example:
    为所有生产环境的Kafka实例添加 'Environment=Production' 标签：

    .. code-block:: yaml

        policies:
          - name: tag-kafka-production-env
            resource: huaweicloud.kafka
            # 可能需要一个过滤器来识别生产环境实例
            # filters:
            #   - ...
            actions:
              - type: tag                   # 动作类型
                key: Environment            # 要添加/更新的标签键
                value: Production           # 要设置的标签值
    """
    # 定义此动作的输入模式 (schema)
    schema = type_schema(
        'tag',  # 动作类型名称
        key={'type': 'string'},  # 标签键
        value={'type': 'string'},  # 标签值
        # 声明 'key' 和 'value' 参数是必需的
        required=['key', 'value']
    )

    def perform_action(self, resource):
        """
        对单个资源执行添加/更新标签操作。

        :param resource: 要标记的Kafka实例资源字典
        :return: None
        """
        key = self.data.get('key')
        value = self.data.get('value')

        instance_id = resource.get('instance_id')
        if not instance_id:
            log.error(f"无法标记缺少 'instance_id' 的Kafka资源: {resource.get('name', '未知名称')}")
            return None

        # 调用内部方法创建或更新标签
        # (复用 KafkaMarkForOpAction 中的辅助方法)
        kafka_marker = KafkaMarkForOpAction(self.data, self.manager)
        kafka_marker._create_or_update_tag(resource, key, value)

        return None

    # _create_or_update_tag 方法已在 KafkaMarkForOpAction 中定义，此处不再重复


@Kafka.action_registry.register('remove-tag')
class KafkaRemoveTag(HuaweiCloudBaseAction):
    """
    移除Kafka实例的一个或多个指定标签。

    允许用户根据标签键来删除实例上的标签。

    :example:
    移除所有Kafka实例上的 'Temporary' 标签：

    .. code-block:: yaml

        policies:
          - name: remove-temp-kafka-tags
            resource: huaweicloud.kafka
            # 可以加过滤器确保只对包含该标签的实例操作，提高效率
            filters:
              - "tag:Temporary": present
            actions:
              - type: remove-tag            # 动作类型
                key: Temporary              # 要移除的标签键 (必填)
              # 可以指定多个 key 来一次移除多个标签
              # - type: remove-tag
              #   keys: ["Temp1", "Temp2"]
    """
    # 定义此动作的输入模式 (schema)
    schema = type_schema(
        'remove-tag',  # 动作类型名称
        # 可以指定单个 key 或一个 keys 列表
        key={'type': 'string'},  # 要移除的单个标签键
        keys={'type': 'array', 'items': {'type': 'string'}},  # 要移除的标签键列表
        # required=['keys'] # 应该至少需要 key 或 keys 中的一个
        # 更好的方式是使用 oneOf 或 anyOf，但 Custodian 的 schema 可能不支持
        # 暂时允许 key 和 keys 都可选，在代码中处理
    )

    def perform_action(self, resource):
        """
        对单个资源执行移除标签操作。

        :param resource: 要移除标签的Kafka实例资源字典
        :return: None
        """
        # 获取要移除的标签键列表
        tags_to_remove = self.data.get('keys', [])
        single_key = self.data.get('key')
        if single_key and single_key not in tags_to_remove:
            tags_to_remove.append(single_key)

        if not tags_to_remove:
            log.warning("在 remove-tag 动作中未指定要移除的标签键 (key 或 keys)。")
            return None

        instance_id = resource.get('instance_id')
        instance_name = resource.get('name', '未知名称')
        if not instance_id:
            log.error(f"无法移除标签，缺少 'instance_id' 的Kafka资源: {instance_name}")
            return None

        # 检查实例上实际存在的标签，避免尝试删除不存在的标签 (虽然API可能允许，但会产生不必要的调用)
        current_tags = {t.get('Key') for t in resource.get('Tags', [])}
        keys_that_exist = [k for k in tags_to_remove if k in current_tags]

        if not keys_that_exist:
            log.debug(f"Kafka实例 {instance_name} ({instance_id}) 上没有需要移除的标签: {tags_to_remove}")
            return None

        # 调用内部方法移除标签
        self._remove_tags_internal(resource, keys_that_exist)

        return None

    def _remove_tags_internal(self, resource, keys_to_delete):
        """
        内部辅助方法，调用API移除指定的标签键列表。

        :param resource: 目标资源字典
        :param keys_to_delete: 要删除的标签键字符串列表
        """
        instance_id = resource['instance_id']
        instance_name = resource.get('name', '未知名称')
        client = self.manager.get_client()

        # 为每个要删除的键创建一个TagEntity (只需提供key)
        tag_entities = [SDKTagEntity(key=k) for k in keys_to_delete]

        try:
            # 构造批量删除标签的请求
            request = BatchCreateOrDeleteKafkaTagRequest()
            request.instance_id = instance_id
            request.body = BatchCreateOrDeleteTagReq()
            request.body.action = "delete"  # 指定动作为删除
            request.body.tags = tag_entities  # 包含要删除的标签键
            # 调用API执行删除
            client.batch_create_or_delete_kafka_tag(request)
            log.info(f"已从Kafka实例 {instance_name} ({instance_id}) 移除标签: {keys_to_delete}")
        except exceptions.ClientRequestException as e:
            log.error(
                f"从Kafka实例 {instance_name} ({instance_id}) 移除标签 {keys_to_delete} 失败: "
                f"{e.error_msg} (状态码: {e.status_code})"
            )
        except Exception as e:
            log.error(f"从Kafka实例 {instance_name} ({instance_id}) 移除标签 {keys_to_delete} 时发生未知错误: {str(e)}")


@Kafka.action_registry.register('rename-tag')
class KafkaRenameTag(HuaweiCloudBaseAction):
    """
    重命名Kafka实例上的一个标签键。

    此操作实际上是"复制并删除"：
    1. 读取具有旧键 (`old_key`) 的标签的值。
    2. 使用新键 (`new_key`) 和旧值创建一个新标签。
    3. 删除具有旧键 (`old_key`) 的标签。

    :example:
    将所有实例上的 'Env' 标签重命名为 'Environment'：

    .. code-block:: yaml

        policies:
          - name: standardize-env-tag-kafka
            resource: huaweicloud.kafka
            filters:
              - "tag:Env": present          # 确保只对有'Env'标签的实例操作
            actions:
              - type: rename-tag            # 动作类型
                old_key: Env                # 旧的标签键
                new_key: Environment        # 新的标签键
    """
    # 定义此动作的输入模式 (schema)
    schema = type_schema(
        'rename-tag',  # 动作类型名称
        old_key={'type': 'string'},  # 旧的标签键
        new_key={'type': 'string'},  # 新的标签键
        # 声明 'old_key' 和 'new_key' 参数是必需的
        required=['old_key', 'new_key']
    )

    def perform_action(self, resource):
        """
        对单个资源执行重命名标签操作。

        :param resource: 要重命名标签的Kafka实例资源字典
        :return: None
        """
        old_key = self.data.get('old_key')
        new_key = self.data.get('new_key')

        if old_key == new_key:
            log.warning(f"旧标签键 '{old_key}' 和新标签键 '{new_key}' 相同，无需重命名。")
            return None

        instance_id = resource.get('instance_id')
        instance_name = resource.get('name', '未知名称')
        if not instance_id:
            log.error(f"无法重命名标签，缺少 'instance_id' 的Kafka资源: {instance_name}")
            return None

        # 查找旧标签的值
        old_value = None
        if 'Tags' in resource:
            for tag in resource['Tags']:
                if tag.get('Key') == old_key:
                    old_value = tag.get('Value')
                    break  # 找到即停止

        # 如果旧标签不存在，则无需操作
        if old_value is None:
            log.info(f"Kafka实例 {instance_name} ({instance_id}) 没有找到标签 '{old_key}'，跳过重命名。")
            return None

        # 检查新标签是否已存在 (可选，但有助于避免覆盖)
        new_key_exists = False
        if 'Tags' in resource:
            for tag in resource['Tags']:
                if tag.get('Key') == new_key:
                    new_key_exists = True
                    log.warning(f"Kafka实例 {instance_name} ({instance_id}) 已存在目标标签键 '{new_key}'。"
                                f"重命名操作将覆盖其现有值 (如果继续执行)。")
                    break

        # 1. 添加新标签 (使用旧值)
        # 复用 KafkaMarkForOpAction 中的辅助方法来创建新标签
        kafka_marker = KafkaMarkForOpAction(self.data, self.manager)
        kafka_marker._create_or_update_tag(resource, new_key, old_value)

        # 2. 移除旧标签
        # 复用 KafkaRemoveTag 中的辅助方法来删除旧标签
        # (这里需要实例化 KafkaRemoveTag 类，或者将 _remove_tags_internal 设为静态或移到共享位置)
        # 为了简单，直接在这里调用API或复制逻辑
        remover = KafkaRemoveTag(self.data, self.manager)
        remover._remove_tags_internal(resource, [old_key])

        log.info(f"已将Kafka实例 {instance_name} ({instance_id}) 的标签 '{old_key}' 重命名为 '{new_key}'")

        return None

    # _create_or_update_tag 和 _remove_tags_internal 方法由复用的类提供


# 待测试
@Kafka.action_registry.register('delete')
class DeleteKafka(HuaweiCloudBaseAction):
    """
    删除指定的Kafka实例。

    **警告:** 这是一个破坏性操作，将永久删除Kafka实例及其数据。请谨慎使用。

    :example:
    删除创建时间超过90天且已被标记删除的Kafka实例：

    .. code-block:: yaml

        policies:
          - name: delete-old-marked-kafka
            resource: huaweicloud.kafka
            filters:
              - type: marked-for-op
                op: delete
                tag: custodian_cleanup # 假设使用此标签标记
              - type: age
                days: 90
                op: gt
            actions:
              - type: delete             # 动作类型
    """
    # 定义此动作的输入模式 (schema)
    schema = type_schema(
        'delete',  # 动作类型名称
        # 可以添加 force=True 之类的参数，如果API支持强制删除
        # force={'type': 'boolean', 'default': False}
    )

    # 定义执行此操作所需的IAM权限
    permissions = ('kafka:deleteInstance',)

    def perform_action(self, resource):
        """
        对单个资源执行删除操作。

        :param resource: 要删除的Kafka实例资源字典
        :return: API调用的响应 (可能包含任务ID等信息) 或 None (如果失败)
        """
        instance_id = resource.get('instance_id')
        instance_name = resource.get('name', '未知名称')
        if not instance_id:
            log.error(f"无法删除缺少 'instance_id' 的Kafka资源: {instance_name}")
            return None

        # 获取华为云Kafka客户端
        client = self.manager.get_client()

        try:
            # 构造删除实例的请求
            request = DeleteInstanceRequest(instance_id=instance_id)
            # 调用API执行删除操作
            response = client.delete_instance(request)
            log.info(f"已启动删除Kafka实例 {instance_name} ({instance_id}) 的操作。响应: {response}")
            return response  # 返回API响应
        except exceptions.ClientRequestException as e:
            log.error(
                f"删除Kafka实例 {instance_name} ({instance_id}) 失败: "
                f"{e.error_msg} (状态码: {e.status_code})"
            )
            return None  # 删除失败返回None
        except Exception as e:
            log.error(f"删除Kafka实例 {instance_name} ({instance_id}) 时发生未知错误: {str(e)}")
            return None


@Kafka.action_registry.register('set-monitoring')
class SetKafkaMonitoring(HuaweiCloudBaseAction):
    """
    修改Kafka实例的配置项。

    此动作允许更新Kafka实例的各种配置参数，例如日志收集、访问控制等。
    需要提供一个包含要修改的配置项及其新值的字典。

    **注意:** 请参考华为云DMS Kafka API文档了解支持修改的具体配置项及其有效值。
    错误的配置可能导致实例功能异常。

    :example:
    为 'enable.log.collection' 配置为 false 的实例启用日志收集：

    .. code-block:: yaml

        policies:
          - name: enable-kafka-log-collection
            resource: huaweicloud.kafka
            filters:
              - type: config-compliance     # 使用配置合规性过滤器查找需要修改的实例
                key: enable.log.collection
                op: eq
                value: false
            actions:
              - type: set-monitoring        # 动作类型 (名称可能不太准确，改为 'set-config'?)
                config:                     # 包含要修改的配置项的字典
                  enable.log.collection: "true" # 注意：API可能期望字符串形式的布尔值
                  # access.user.enable: "true" # 可以同时修改多个配置项
    """
    # 定义此动作的输入模式 (schema)
    schema = type_schema(
        'set-monitoring',  # 动作类型名称
        # 包含配置键值对的字典，至少需要一个属性
        config={'type': 'object', 'minProperties': 1,
                'additionalProperties': {'type': ['string', 'number', 'boolean']}},
        # 声明 'config' 参数是必需的
        required=['config']
    )

    # 定义执行此操作所需的IAM权限
    permissions = ('kafka:modifyInstanceConfigs',)

    def perform_action(self, resource):
        """
        对单个资源执行修改配置操作。

        :param resource: 要修改配置的Kafka实例资源字典
        :return: API调用的响应或 None (如果失败)
        """
        instance_id = resource.get('instance_id')
        instance_name = resource.get('name', '未知名称')
        if not instance_id:
            log.error(f"无法修改配置，缺少 'instance_id' 的Kafka资源: {instance_name}")
            return None

        # 获取策略中定义的配置项字典
        config_data = self.data.get('config', {})
        if not config_data:
            log.warning(f"在 set-monitoring 动作中未提供 'config' 数据，跳过实例 {instance_name} ({instance_id})。")
            return None

        # 获取华为云Kafka客户端
        client = self.manager.get_client()

        try:
            # 构造修改实例配置的请求
            request = ModifyInstanceConfigsRequest()
            request.instance_id = instance_id
            # 创建请求体
            request.body = ModifyInstanceConfigsReq()

            # 为请求准备配置项列表
            # 华为云Kafka API期望的是一个包含name/value配置项的列表而不是直接在请求体上设置属性
            from huaweicloudsdkkafka.v2.model import ModifyInstanceConfig
            kafka_configs = []

            # 将配置字典中的键值对转换为ModifyInstanceConfig对象
            for key, value in config_data.items():
                # 数据类型转换 (根据API要求)
                if isinstance(value, bool):
                    processed_value = str(value).lower()  # 布尔值转为"true"或"false"
                elif isinstance(value, (int, float)):
                    processed_value = str(value)  # 数字转为字符串
                else:
                    processed_value = value  # 其他类型直接使用

                # 创建配置对象并添加到列表
                config_item = ModifyInstanceConfig(name=key, value=processed_value)
                kafka_configs.append(config_item)

            # 设置请求体的kafka_configs属性
            request.body.kafka_configs = kafka_configs

            if not kafka_configs:
                log.warning(f"没有有效的配置项提供给 set-monitoring 动作，跳过实例 {instance_name} ({instance_id})。")
                return None

            # 记录准备好的配置项 (用于日志)
            processed_configs = {c.name: c.value for c in kafka_configs}
            log.debug(
                f"为Kafka实例 {instance_name} ({instance_id}) 准备的配置项: {[f'{c.name}={c.value}' for c in kafka_configs]}")

            # 调用API执行修改配置操作
            response = client.modify_instance_configs(request)
            log.info(f"已为Kafka实例 {instance_name} ({instance_id}) 更新配置: {processed_configs}。响应: {response}")
            return response  # 返回API响应
        except exceptions.ClientRequestException as e:
            log.error(
                f"更新Kafka实例 {instance_name} ({instance_id}) 配置 {config_data} 失败: "
                f"{e.error_msg} (状态码: {e.status_code})"
            )
            return None  # 更新失败返回None
        except Exception as e:
            log.error(f"更新Kafka实例 {instance_name} ({instance_id}) 配置时发生未知错误: {str(e)}")
            return None
