# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.filters.vpc import SecurityGroupFilter
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from dateutil.parser import parse
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkrocketmq.v2.model import (
    DeleteInstanceRequest,
    BatchCreateOrDeleteRocketmqTagRequest,
    BatchCreateOrDeleteTagReq,
    ShowRocketmqTagsRequest,
)
from huaweicloudsdkrocketmq.v2.model import TagEntity as SDKTagEntity

from c7n.filters import Filter, ValueFilter, OPERATORS
from c7n.filters.core import ListItemFilter
from c7n.utils import type_schema, local_session

log = logging.getLogger("custodian.huaweicloud.resources.rocketmq")


@resources.register('reliabilitys')
class RocketMQ(QueryResourceManager):
    """华为云RocketMQ实例资源管理器。
    
    负责发现、过滤和管理华为云上的RocketMQ实例资源。
    继承自QueryResourceManager，使用其能力来查询和处理资源列表。
    
    :example:
    定义一个简单的策略来获取所有RocketMQ实例:
    
    .. code-block:: yaml

        policies:
          - name: rocketmq-instances-discovery  # 策略名称
            resource: huaweicloud.reliabilitys  # 指定资源类型为华为云RocketMQ
    """

    class resource_type(TypeInfo):
        """定义RocketMQ资源元数据和类型信息"""
        service = 'reliabilitys'  # 指定对应的华为云服务名称
        # 指定API操作、结果列表键和分页参数，用于枚举资源
        # 'list_instances'是API方法名
        # 'instances'是响应中包含实例列表的字段名
        # 'offset'是分页参数名
        enum_spec = ('list_instances', 'instances',
                     'offset', 10)
        id = 'instance_id'  # 指定资源唯一标识符字段名
        name = 'name'  # 指定资源名称字段名
        date = 'created_at'  # 指定资源创建时间字段名
        tag = True  # 指示此资源支持标签
        tag_resource_type = 'rocketmq'  # 指定查询标签的资源类型

    def augment(self, resources):
        """
        增强从API获取的原始资源数据。
        
        主要用于将华为云API返回的标签列表格式（通常是包含'key'和'value'字段的字典列表）
        转换为Cloud Custodian内部使用的AWS兼容格式（包含'Key'和'Value'字段的字典列表）。
        这提高了跨云提供商策略的一致性。
        
        :param resources: 从API获取的原始资源字典列表
        :return: 增强的资源字典列表，其中标签在'Tags'键下转换为AWS兼容格式
        """
        for r in resources:
            # 检查原始资源字典中是否存在'tags'键
            if 'tags' not in r:
                continue  # 如果没有标签，跳过此资源
            tags = []
            # 遍历原始标签列表
            for tag_entity in r['tags']:
                # 将每个标签转换为{'Key': ..., 'Value': ...}格式
                tags.append({'Key': tag_entity.get('key'), 'Value': tag_entity.get('value')})
            # 向资源字典添加转换后的标签列表，键名为'Tags'
            r['Tags'] = tags
        return resources


@RocketMQ.filter_registry.register('security-group')
class RocketMQSecurityGroupFilter(SecurityGroupFilter):
    """
    基于关联安全组过滤RocketMQ实例。
    
    允许用户根据RocketMQ实例使用的安全组的属性（如名称、ID）来过滤实例。
    继承自通用的`SecurityGroupFilter`。
    
    :example:
    查找使用名为'allow-public'的安全组的RocketMQ实例：
    
    .. code-block:: yaml

        policies:
          - name: rocketmq-with-public-sg
            resource: huaweicloud.reliabilitys
            filters:
              - type: security-group        # 过滤器类型
                key: name              # 要匹配的安全组属性（例如，name、Id）
                value: allow-public         # 要匹配的值
    """
    # 指定RocketMQ资源字典中包含安全组ID的字段名
    RelatedIdsExpression = "security_group_id"


@RocketMQ.filter_registry.register('age')
class RocketMQAgeFilter(Filter):
    """
    基于创建时间（年龄）过滤RocketMQ实例。
    
    允许用户过滤出早于或晚于指定时间创建的实例。
    
    :example:
    查找创建时间超过30天的RocketMQ实例：
    
    .. code-block:: yaml

        policies:
          - name: rocketmq-older-than-30-days
            resource: huaweicloud.reliabilitys
            filters:
              - type: age                   # 过滤器类型
                days: 30                    # 指定天数
                op: gt                      # 操作，gt表示"大于"（older than）
                                            # 其他可用符号：lt（younger than）、ge、le
    """
    # 定义此过滤器的输入模式（schema）
    schema = type_schema(
        'age',  # 过滤器类型名称
        # 定义比较操作，引用通用过滤器定义
        op={'$ref': '#/definitions/filters_common/comparison_operators'},
        # 定义时间单位参数
        days={'type': 'number'},  # 天数
        hours={'type': 'number'},  # 小时
        minutes={'type': 'number'}  # 分钟
    )
    schema_alias = True

    # 指定资源字典中表示创建时间的字段名
    date_attribute = "created_at"

    def validate(self):
        return self

    def process(self, resources, event=None):
        # 获取操作符和时间
        op = self.data.get('op', 'greater-than')
        if op not in OPERATORS:
            raise ValueError(f"Invalid operator: {op}")
        operator = OPERATORS[op]
        
        # 计算比较日期
        from datetime import datetime, timedelta
        from dateutil.tz import tzutc
        
        days = self.data.get('days', 0)
        hours = self.data.get('hours', 0)
        minutes = self.data.get('minutes', 0)
        
        now = datetime.now(tz=tzutc())
        threshold_date = now - timedelta(days=days, hours=hours, minutes=minutes)
        
        # 筛选资源
        matched = []
        for resource in resources:
            created_str = resource.get(self.date_attribute)
            if not created_str:
                continue
                
            # 转换创建时间
            try:
                # 如果是毫秒时间戳，转换为秒后创建datetime
                if isinstance(created_str, (str, int)) and str(created_str).isdigit():
                    try:
                        # 假设是毫秒时间戳，转换为秒
                        timestamp_ms = int(created_str)
                        timestamp_s = timestamp_ms / 1000.0
                        # 从时间戳创建datetime对象（UTC）
                        created_date = datetime.utcfromtimestamp(timestamp_s).replace(tzinfo=tzutc())
                    except (ValueError, TypeError, OverflowError) as e:
                        log.debug(
                            f"无法将值 '{created_str}' 解析为毫秒时间戳: {e}")
                        # 如果解析失败，继续尝试使用dateutil.parser
                        created_date = parse(str(created_str))
                else:
                    # 如果不是纯数字或解析毫秒时间戳失败，尝试使用dateutil.parser解析通用时间字符串
                    created_date = parse(str(created_str))
                
                # 确保datetime有时区信息
                if not created_date.tzinfo:
                    created_date = created_date.replace(tzinfo=tzutc())
                    
                # 比较日期
                if operator(created_date, threshold_date):
                    matched.append(resource)
            except Exception as e:
                log.warning(
                    f"无法解析RocketMQ实例 {resource.get('instance_id', '未知ID')} "
                    f"的创建时间 '{created_str}': {e}")
                
        return matched


@RocketMQ.filter_registry.register('list-item')
class RocketMQListItemFilter(ListItemFilter):
    """
    过滤资源属性中的列表项。
    
    此过滤器允许检查资源字典中的键（必须是列表）的值，并基于列表中的项进行过滤。
    例如，可以检查实例是否部署在特定的可用区中，或者是否包含特定的标签。
    继承自核心`ListItemFilter`。
    
    :example:
    查找部署在'cn-north-4a'或'cn-north-4b'可用区的RocketMQ实例：
    
    .. code-block:: yaml

        policies:
          - name: rocketmq-multi-az
            resource: huaweicloud.reliabilitys
            filters:
              - type: list-item             # 过滤器类型
                key: available_zones        # 资源属性键名（值应该是列表）
                # key_path: "[].name"       # （可选）用于提取值的JMESPath表达式
                                            # 如果列表项是简单类型，不需要key_path
                op: in                      # 比较运算符(in, not-in, contains, eq, ...)
                value: ["cn-north-4a", "cn-north-4b"] # 要比较的值或值列表

    可以用于过滤的列表属性示例（取决于API返回的字段）:
    - `available_zones`: 可用区列表（通常是字符串列表）
    - `tags`: 标签列表（通常是字典列表，需要使用`key_path`，例如
      `[?key=='Environment'].value | [0]`，或者在`augment`后使用`Tags`）
    """
    # 定义此过滤器的输入模式（schema）
    schema = type_schema(
        'list-item',  # 过滤器类型名
        # --- 以下参数继承自ListItemFilter ---
        # count: 匹配项的数量
        count={'type': 'integer', 'minimum': 0},
        # count_op: 数量的比较运算符(eq, ne, gt, ge, lt, le)
        count_op={'enum': list(OPERATORS.keys())},
        # op: 列表项值的比较运算符
        op={'enum': list(OPERATORS.keys())},
        # value: 用于比较的值，可以是单个值或列表
        value={'oneOf': [
            {'type': 'array'},
            {'type': 'string'},
            {'type': 'boolean'},
            {'type': 'number'},
            {'type': 'object'}
        ]},
        # key: 要检查的资源属性键名，值必须是列表
        key={'oneOf': [
            {'type': 'string'},
            {'type': 'integer', 'minimum': 0},  # 键也可以是整数（如果资源字典键是整数）
            {'type': 'array', 'items': {'type': 'string'}}  # 或路径列表
        ]},
        # key_path: （可选）JMESPath表达式，用于从列表项中提取比较值
        key_path={'type': 'string'},
        # 声明'key'参数是必需的
        required=['key']
    )


@RocketMQ.filter_registry.register('marked-for-op')
class RocketMQMarkedForOpFilter(Filter):
    """
    基于特定"标记操作"标签过滤RocketMQ实例。
    
    此过滤器用于查找那些被`mark-for-op`操作标记为在将来某个时间执行特定
    操作（如删除、停止）的实例。
    它检查指定的标签键（`tag`），从标签值中解析操作类型和计划执行时间，
    并与当前时间进行比较。
    
    :example:
    查找所有标记为删除的RocketMQ实例，标签键为'custodian_cleanup'：
    
    .. code-block:: yaml

        policies:
          - name: find-rocketmq-marked-for-deletion
            resource: huaweicloud.reliabilitys
            filters:
              - type: marked-for-op          # 过滤器类型
                op: delete                  # 要查找的操作类型（'delete', 'stop', 'restart'）
                tag: custodian_cleanup      # 用于标记操作的标签键
                # skew: 1                   # （可选）时间偏移（天）
                # skew_hours: 2             # （可选）时间偏移（小时）
    """
    # 定义此过滤器的输入模式（schema）
    schema = type_schema(
        'marked-for-op',  # 过滤器类型名称
        # 要查找的操作类型
        op={'type': 'string', 'enum': ['delete', 'stop', 'restart']},
        # 用于标记操作的标签键，默认为'mark-for-op-custodian'
        tag={'type': 'string', 'default': 'mark-for-op-custodian'},
        # （可选）时间偏移（天），允许提前N天匹配，默认为0
        skew={'type': 'number', 'default': 0},
        # （可选）时间偏移（小时），允许提前N小时匹配，默认为0
        skew_hours={'type': 'number', 'default': 0},
        # 时区，默认为'utc'
        tz={'type': 'string', 'default': 'utc'},
    )
    schema_alias = True
    DEFAULT_TAG = "mark-for-op-custodian"

    def __init__(self, data, manager=None):
        super(RocketMQMarkedForOpFilter, self).__init__(data, manager)
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
        """处理标签值，确定是否满足过滤条件"""
        if not tag_value:
            return False

        # 处理RocketMQMarkForOpAction创建的值格式"operation@timestamp"
        if '@' in tag_value:
            action, action_date_str = tag_value.strip().split('@', 1)
        # 兼容旧格式"operation_timestamp"
        elif '_' in tag_value:
            action, action_date_str = tag_value.strip().split('_', 1)
        else:
            return False
        if action != self.op:
            return False

        try:
            # 尝试直接解析RocketMQMarkForOpAction生成的标准时间戳格式
            # '%Y/%m/%d %H:%M:%S UTC'
            from dateutil.parser import parse
            action_date = parse(action_date_str)
        except Exception:
            # 如果标准解析失败，尝试使用旧格式转换逻辑
            try:
                # 旧时间格式转换逻辑
                modified_date_str = self._replace_nth_regex(action_date_str, "-", " ", 3)
                modified_date_str = self._replace_nth_regex(modified_date_str, "-", ":", 3)
                modified_date_str = self._replace_nth_regex(modified_date_str, "-", " ", 3)

                action_date = parse(modified_date_str)
            except Exception as nested_e:
                self.log.warning(f"无法解析标签值: {tag_value}, 错误: {str(nested_e)}")
                return False

        from datetime import datetime, timedelta
        if action_date.tzinfo:
            # 如果action_date有时区，转换为指定时区
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
            # 处理原始tags列表，各种可能的格式
            elif 'tags' in resource:
                raw_tags = resource['tags']
                if isinstance(raw_tags, dict):
                    tags = raw_tags
                elif isinstance(raw_tags, list):
                    if all(isinstance(item, dict) and 'key' in item and 'value' in item
                           for item in raw_tags):
                        # 兼容华为云特定的[{key: k1, value: v1}]格式
                        for item in raw_tags:
                            tags[item['key']] = item['value']
                    elif all(isinstance(item, dict) and len(item) == 1 for item in raw_tags):
                        # 兼容[{k1: v1}, {k2: v2}]格式
                        for item in raw_tags:
                            key, value = list(item.items())[0]
                            tags[key] = value
            return tags
        except Exception as e:
            self.log.error(f"解析资源标签失败: {str(e)}")
            return {}


@RocketMQ.action_registry.register('mark-for-op')
class RocketMQMarkForOpAction(HuaweiCloudBaseAction):
    """
    向RocketMQ实例添加"标记操作"标签。
    
    此操作用于标记资源，以便其他策略（使用`marked-for-op`过滤器）可以在将来某个时间识别和执行。
    它会在资源上创建一个标签，标签值包含指定的操作（`op`）和执行时间戳。
    
    :example:
    标记创建超过90天的RocketMQ实例，让它们在7天后被删除：
    
    .. code-block:: yaml

        policies:
          - name: mark-old-rocketmq-for-deletion
            resource: huaweicloud.reliabilitys
            filters:
              - type: age
                days: 90
                op: gt
            actions:
              - type: mark-for-op          # 操作类型
                op: delete                  # 标记的操作('delete', 'stop', 'restart')
                days: 7                     # 延迟执行天数（从现在开始）
                # hours: 0                  # （可选）延迟执行小时数（从现在开始）
                tag: custodian_cleanup      # 标记标签键（应与过滤器的标签匹配）
    """
    # 定义此操作的输入模式（schema）
    schema = type_schema(
        'mark-for-op',  # 操作类型名称
        # 标记的操作类型
        op={'enum': ['delete', 'stop', 'restart']},
        # 延迟执行天数（从当前时间起）
        days={'type': 'number', 'minimum': 0, 'default': 0},
        # 延迟执行小时数（从当前时间起）
        hours={'type': 'number', 'minimum': 0, 'default': 0},
        # 标记标签键，默认为'mark-for-op-custodian'
        tag={'type': 'string', 'default': 'mark-for-op-custodian'},
        # 声明'op'参数是必需的
        required=['op']
    )

    def perform_action(self, resource):
        """
        对单个资源执行标记操作。
        
        :param resource: 要标记的RocketMQ实例资源字典
        :return: 无或API响应（但通常没有特定结果）
        """
        # 从策略定义中获取参数
        op = self.data.get('op')
        tag_key = self.data.get('tag', 'mark-for-op-custodian')
        days = self.data.get('days', 0)
        hours = self.data.get('hours', 0)

        instance_id = resource.get('instance_id')
        if not instance_id:
            log.error(
                f"无法标记缺少'instance_id'的RocketMQ资源: "
                f"{resource.get('name', '未知名称')}")
            return None

        # 计算计划执行时间（UTC）
        from datetime import datetime, timedelta
        try:
            action_time = datetime.utcnow() + timedelta(days=days, hours=hours)
            # 格式化时间戳字符串，必须与TagActionFilter解析格式一致
            action_time_str = action_time.strftime('%Y/%m/%d %H:%M:%S UTC')
        except OverflowError:
            log.error(
                f"无效的标记操作时间戳计算，RocketMQ实例 {instance_id} "
                f"(days={days}, hours={hours})")
            return None

        # 构建标签值，格式为"operation_timestamp"
        tag_value = f"{op}@{action_time_str}"  # 使用@作为分隔符，更清晰

        # 调用内部方法创建标签
        self._create_or_update_tag(resource, tag_key, tag_value)

        return None  # 通常标记操作不返回特定结果

    def _create_or_update_tag(self, resource, key, value):
        """
        为指定资源创建或更新标签。
        
        :param resource: 目标资源字典
        :param key: 标签键
        :param value: 标签值
        """
        instance_id = resource['instance_id']
        instance_name = resource.get('name', '未知名称')
        # 获取华为云RocketMQ客户端
        client = self.manager.get_client()
        # 构造标签实体（使用华为云SDK的TagEntity类）
        tag_entity = SDKTagEntity(key=key, value=value)
        try:
            # 构造批量创建/删除标签请求
            request = BatchCreateOrDeleteRocketmqTagRequest()
            request.instance_id = instance_id
            request.body = BatchCreateOrDeleteTagReq()
            # 华为云批量接口没有直接的"更新"操作。
            # 当前实现假设'create'会覆盖现有标签。
            request.body.action = "create"
            request.body.tags = [tag_entity]
            # 调用API执行操作
            client.batch_create_or_delete_rocketmq_tag(request)
            log.info(
                f"为RocketMQ实例 {instance_name} ({instance_id}) 添加或更新标签: "
                f"{key}={value}")
        except exceptions.ClientRequestException as e:
            # 处理API请求异常
            log.error(
                f"无法为RocketMQ实例 {instance_name} ({instance_id}) 添加或更新标签 {key}: "
                f"{e.error_msg} (状态码: {e.status_code})"
            )
        except Exception as e:
            # 处理其他潜在异常
            log.error(
                f"无法为RocketMQ实例 {instance_name} ({instance_id}) 添加或更新标签 {key}: "
                f"{str(e)}")


@RocketMQ.action_registry.register('auto-tag-user')
class RocketMQAutoTagUser(HuaweiCloudBaseAction):
    """
    （概念性）自动向RocketMQ实例添加创建者用户标签。
    
    **重要说明:** 此操作依赖于资源数据中包含创建者信息
    （例如此处的'user_name'字段）。
    华为云API返回的RocketMQ实例信息**通常不直接包含创建者IAM用户名**。
    因此，此操作的有效性取决于`QueryResourceManager`
    或其`augment`方法是否能通过其他方式获取并填充`user_name`字段
    （例如查询CTS操作日志服务）。如果无法获取，标签值将为'unknown'。
    
    :example:
    为缺少此标签的RocketMQ实例添加'Creator'标签，
    值为创建者用户名（如果能获取）：
    
    .. code-block:: yaml

        policies:
          - name: tag-rocketmq-creator-if-missing
            resource: huaweicloud.reliabilitys
            filters:
              - "tag:Creator": absent       # 过滤没有'Creator'标签的实例
            actions:
              - type: auto-tag-user         # 操作类型
                tag: Creator                # 要添加的标签键（默认是'CreatorName'）
    """
    # 定义此操作的输入模式（schema）
    schema = type_schema(
        'auto-tag-user',  # 操作类型名称
        # 指定要添加的标签键，默认为'CreatorName'
        tag={'type': 'string', 'default': 'CreatorName'},
        # 此操作的模式模式，默认为'resource'
        # 可选'account'（可能表示当前执行策略的账户，但没有实际意义）
        mode={'type': 'string', 'enum': ['resource', 'account'], 'default': 'resource'},
        # 如果模式为'resource'，指定获取用户名的资源字典键
        user_key={'type': 'string', 'default': 'creator'},
        # 改为'creator'可能更通用
        # 是否更新现有标签，默认为True
        update={'type': 'boolean', 'default': True},
        required=[]  # 没有必需参数（因为所有参数都有默认值）
    )

    # 权限声明（如果获取用户信息需要特定权限）
    # permissions = ('cts:listOperations',) # 例如，如果需要检查CTS日志

    def perform_action(self, resource):
        """
        对单个资源执行自动标记用户操作。
        
        :param resource: 要标记的RocketMQ实例资源字典
        :return: 无
        """
        tag_key = self.data.get('tag', 'CreatorName')
        mode = self.data.get('mode', 'resource')
        user_key = self.data.get('user_key', 'creator')
        update = self.data.get('update', True)

        instance_id = resource.get('instance_id')
        instance_name = resource.get('name', '未知名称')
        if not instance_id:
            log.error(f"无法标记缺少'instance_id'的RocketMQ资源: {instance_name}")
            return None

        # 检查是否需要更新，以及标签是否已存在
        if not update and tag_key in [t.get('Key') for t in resource.get('Tags', [])]:
            log.debug(
                f"RocketMQ实例 {instance_name} ({instance_id}) 已存在标签 '{tag_key}' "
                f"且不允许更新，跳过。")
            return None

        user_name = 'unknown'  # 默认值
        if mode == 'resource':
            # 尝试从资源字典中获取用户名
            user_name = resource.get(user_key, 'unknown')
            if user_name == 'unknown':
                # 如果默认的'creator'键未找到，也尝试原始代码的'user_name'
                user_name = resource.get('user_name', 'unknown')

                # 如果仍然未知，可以考虑添加查询CTS日志的逻辑
                if user_name == 'unknown':
                    log.warning(
                        f"无法为RocketMQ实例 {instance_name} ({instance_id}) 查找创建者信息"
                        f"（尝试的键：'{user_key}', 'user_name'）。"
                        f"使用'unknown'。")
        elif mode == 'account':
            log.warning("RocketMQAutoTagUser中的'account'模式尚未完全实现。")
            user_name = 'unknown'

        # 复用RocketMQMarkForOpAction的辅助方法
        rocketmq_marker = RocketMQMarkForOpAction(self.data, self.manager)
        rocketmq_marker._create_or_update_tag(resource, tag_key, user_name)

        return None


@RocketMQ.action_registry.register('tag')
class RocketMQTag(HuaweiCloudBaseAction):
    """
    向RocketMQ实例添加或更新指定标签。
    
    这是一个通用的添加标签操作，允许用户直接指定标签键和值。
    如果同名标签键已存在，默认会覆盖其值。
    
    :example:
    为生产环境中的所有RocketMQ实例添加'Environment=Production'标签：
    
    .. code-block:: yaml

        policies:
          - name: tag-rocketmq-production-env
            resource: huaweicloud.reliabilitys
            # 可能需要过滤器来识别生产环境实例
            # filters:
            #   - ...
            actions:
              - type: tag                   # 操作类型
                key: Environment            # 要添加/更新的标签键
                value: Production           # 要设置的标签值
    """
    # 定义此操作的输入模式（schema）
    schema = type_schema(
        'tag',  # 操作类型名称
        key={'type': 'string'},  # 标签键
        value={'type': 'string'},  # 标签值
        # 声明'key'和'value'参数是必需的
        required=['key', 'value']
    )

    def perform_action(self, resource):
        """
        对单个资源执行添加/更新标签操作。
        
        :param resource: 要标记的RocketMQ实例资源字典
        :return: 无
        """
        key = self.data.get('key')
        value = self.data.get('value')

        instance_id = resource.get('instance_id')
        if not instance_id:
            log.error(
                f"无法标记缺少'instance_id'的RocketMQ资源: "
                f"{resource.get('name', '未知名称')}")
            return None

        # 复用RocketMQMarkForOpAction的辅助方法
        rocketmq_marker = RocketMQMarkForOpAction(self.data, self.manager)
        rocketmq_marker._create_or_update_tag(resource, key, value)

        return None


@RocketMQ.action_registry.register('remove-tag')
class RocketMQRemoveTag(HuaweiCloudBaseAction):
    """
    从RocketMQ实例移除一个或多个指定标签。
    
    允许用户根据标签键从实例中移除标签。
    
    :example:
    从所有RocketMQ实例中移除'Temporary'标签：
    
    .. code-block:: yaml

        policies:
          - name: remove-temp-rocketmq-tags
            resource: huaweicloud.reliabilitys
            # 可以添加过滤器，确保只操作包含此标签的实例
            filters:
              - "tag:Temporary": present
            actions:
              - type: remove-tag            # 操作类型
                key: Temporary              # 要移除的标签键（必需）
              # 可以指定多个键来一次性移除多个标签
              # - type: remove-tag
              #   keys: ["Temp1", "Temp2"]
    """
    # 定义此操作的输入模式（schema）
    schema = type_schema(
        'remove-tag',  # 操作类型名称
        # 可以指定单个键或键列表
        key={'type': 'string'},  # 要移除的单个标签键
        keys={'type': 'array', 'items': {'type': 'string'}},  # 要移除的标签键列表
        # required=['keys'] # 至少需要key或keys
        # 更好的方式是使用oneOf或anyOf，但Custodian的schema可能不支持
        # 临时允许key和keys可选，在代码中处理
    )

    def perform_action(self, resource):
        """
        对单个资源执行移除标签操作。
        
        :param resource: 要从中移除标签的RocketMQ实例资源字典
        :return: 无
        """
        # 获取要移除的标签键列表
        tags_to_remove = self.data.get('keys', [])
        single_key = self.data.get('key')
        if single_key and single_key not in tags_to_remove:
            tags_to_remove.append(single_key)

        if not tags_to_remove:
            log.warning("在remove-tag操作中未指定标签键（key或keys）。")
            return None

        instance_id = resource.get('instance_id')
        instance_name = resource.get('name', '未知名称')
        if not instance_id:
            log.error(
                f"无法移除标签，RocketMQ资源缺少'instance_id': {instance_name}")
            return None

        # 检查实例上实际存在的标签，避免尝试删除不存在的标签
        # （虽然API可能允许，但会产生不必要的调用）
        current_tags = {t.get('Key') for t in resource.get('Tags', [])}
        keys_that_exist = [k for k in tags_to_remove if k in current_tags]

        if not keys_that_exist:
            log.debug(
                f"RocketMQ实例 {instance_name} ({instance_id}) 没有要移除的标签: "
                f"{tags_to_remove}")
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

        # 为每个要删除的键创建TagEntity（仅提供键）
        tag_entities = [SDKTagEntity(key=k) for k in keys_to_delete]

        try:
            # 构造批量删除标签请求
            request = BatchCreateOrDeleteRocketmqTagRequest()
            request.instance_id = instance_id
            request.body = BatchCreateOrDeleteTagReq()
            request.body.action = "delete"  # 指定操作为delete
            request.body.tags = tag_entities  # 包含要删除的标签
            # 调用API执行删除
            client.batch_create_or_delete_rocketmq_tag(request)
            log.info(
                f"从RocketMQ实例 {instance_name} ({instance_id}) 移除了标签: "
                f"{keys_to_delete}")
        except exceptions.ClientRequestException as e:
            log.error(
                f"无法从RocketMQ实例 {instance_name} ({instance_id}) 移除标签 {keys_to_delete}: "
                f"{e.error_msg} (状态码: {e.status_code})"
            )
        except Exception as e:
            log.error(
                f"无法从RocketMQ实例 {instance_name} ({instance_id}) 移除标签 {keys_to_delete}: "
                f"{str(e)}")


@RocketMQ.action_registry.register('rename-tag')
class RocketMQRenameTag(HuaweiCloudBaseAction):
    """
    重命名RocketMQ实例上的标签键。
    
    此操作实际上是"复制和删除"：
    1. 读取具有旧键（`old_key`）的标签的值。
    2. 使用新键（`new_key`）和旧值创建新标签。
    3. 删除具有旧键（`old_key`）的标签。
    
    :example:
    将所有实例上的'Env'标签重命名为'Environment'：
    
    .. code-block:: yaml

        policies:
          - name: standardize-env-tag-rocketmq
            resource: huaweicloud.reliabilitys
            filters:
              - "tag:Env": present          # 确保只操作带有'Env'标签的实例
            actions:
              - type: rename-tag            # 操作类型
                old_key: Env                # 旧标签键
                new_key: Environment        # 新标签键
    """
    # 定义此操作的输入模式（schema）
    schema = type_schema(
        'rename-tag',  # 操作类型名称
        old_key={'type': 'string'},  # 旧标签键
        new_key={'type': 'string'},  # 新标签键
        # 声明'old_key'和'new_key'参数是必需的
        required=['old_key', 'new_key']
    )

    def perform_action(self, resource):
        """
        对单个资源执行重命名标签操作。
        
        :param resource: 要重命名标签的RocketMQ实例资源字典
        :return: 无
        """
        old_key = self.data.get('old_key')
        new_key = self.data.get('new_key')

        if old_key == new_key:
            log.warning(
                f"旧标签键'{old_key}'和新标签键'{new_key}'"
                f"相同，无需重命名。")
            return None

        instance_id = resource.get('instance_id')
        instance_name = resource.get('name', '未知名称')
        if not instance_id:
            log.error(
                f"无法重命名标签，RocketMQ资源缺少'instance_id': {instance_name}")
            return None

        # 查找旧标签值
        old_value = None
        if 'Tags' in resource:
            for tag in resource['Tags']:
                if tag.get('Key') == old_key:
                    old_value = tag.get('Value')
                    break

        # 如果旧标签不存在，无操作
        if old_value is None:
            log.info(
                f"RocketMQ实例 {instance_name} ({instance_id}) 未找到标签 '{old_key}', "
                f"跳过重命名。")
            return None

        # 检查新标签是否已存在
        if 'Tags' in resource:
            for tag in resource['Tags']:
                if tag.get('Key') == new_key:
                    log.warning(
                        f"RocketMQ实例 {instance_name} ({instance_id}) 已存在"
                        f"目标标签键 '{new_key}'。重命名操作将覆盖其"
                        f"现有值（如果继续执行）。")
                    break

        # 1. 添加新标签（使用旧值）
        rocketmq_marker = RocketMQMarkForOpAction(self.data, self.manager)
        rocketmq_marker._create_or_update_tag(resource, new_key, old_value)

        # 2. 移除旧标签
        remover = RocketMQRemoveTag(self.data, self.manager)
        remover._remove_tags_internal(resource, [old_key])

        log.info(
            f"已重命名RocketMQ实例 {instance_name} ({instance_id}) "
            f"标签 '{old_key}' 为 '{new_key}'")

        return None


@RocketMQ.action_registry.register('delete')
class DeleteRocketMQ(HuaweiCloudBaseAction):
    """
    删除指定的RocketMQ实例。
    
    **警告:** 这是一个破坏性操作，将永久删除RocketMQ实例及其数据。
    请谨慎使用。
    
    :example:
    删除创建时间超过90天且标记为删除的RocketMQ实例:
    
    .. code-block:: yaml

        policies:
          - name: delete-old-marked-rocketmq
            resource: huaweicloud.reliabilitys
            filters:
              - type: marked-for-op
                op: delete
                tag: custodian_cleanup # 假设使用此标签进行标记
              - type: age
                days: 90
                op: gt
            actions:
              - type: delete             # 操作类型
    """
    # 定义此操作的输入模式（schema）
    schema = type_schema(
        'delete',  # 操作类型名称
        # 如果API支持强制删除，可以添加force=True等参数
        # force={'type': 'boolean', 'default': False}
    )

    # 定义执行此操作所需的IAM权限
    permissions = ('rocketmq:deleteInstance',)

    def perform_action(self, resource):
        """
        对单个资源执行删除操作。
        
        :param resource: 要删除的RocketMQ实例资源字典
        :return: API调用响应（可能包含任务ID等）或None（如果失败）
        """
        instance_id = resource.get('instance_id')
        instance_name = resource.get('name', '未知名称')
        if not instance_id:
            log.error(f"无法删除缺少'instance_id'的RocketMQ资源: {instance_name}")
            return None

        # 获取华为云RocketMQ客户端
        client = self.manager.get_client()

        try:
            # 构造删除实例请求
            request = DeleteInstanceRequest(instance_id=instance_id)
            # 调用API执行删除操作
            response = client.delete_instance(request)
            log.info(
                f"已开始删除RocketMQ实例 {instance_name} ({instance_id}) 操作。"
                f"响应: {response}")
            return response  # 返回API响应
        except exceptions.ClientRequestException as e:
            log.error(
                f"无法删除RocketMQ实例 {instance_name} ({instance_id}): "
                f"{e.error_msg} (状态码: {e.status_code})")
            return None  # 如果删除失败，返回None
        except Exception as e:
            log.error(f"无法删除RocketMQ实例 {instance_name} ({instance_id}): {str(e)}")
            return None
