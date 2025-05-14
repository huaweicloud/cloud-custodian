# 华为云应用运维管理(AOM)服务适配Cloud Custodian文档

## 1. 华为云AOM资源类型

华为云应用运维管理服务主要涉及以下资源类型：

- `huaweicloud.aom-alarm`: AOM告警规则。对应管理和操作告警规则的能力。

## 2. 通用Filters (适用于所有AOM资源)

| Filter             | 说明                       | 是否可复用            | 开发状态 | 华为云API链接                                                                                | 涉及其他服务                                 |
| :----------------- | :------------------------- | :-------------------- |:-----| :------------------------------------------------------------------------------------------- | :------------------------------------------- |
| value              | 基于资源属性值的通用过滤器 | 可复用                | 已复用   | 不适用                                                                                       | 无                                           |
| list-item          | 列表元素过滤器             | 可复用                | 已复用   | 不适用                                                                                       | 无                                           |
| event              | 事件过滤器                 | 可复用                | 已复用   | 不适用                                                                                       | LTS (日志流服务) / CTS (云审计服务)          |
| reduce             | 聚合过滤器                 | 可复用                | 已复用   | 不适用                                                                                       | 无                                           |
| marked-for-op      | 标记操作过滤器             | 可复用                | 已复用   | 不适用                                                                                       | 无                                           |
| tag-count          | 标签数量过滤器             | 可复用                | 已复用   | 不适用                                                                                       | 无                                           |
| tms                | 标签过滤器                 | 可复用 `tms.py`       | 已复用   | [查询指定实例的标签信息](https://support.huaweicloud.com/api-aom/api-tag-view.html)        | TMS (标签管理服务)                           |
| finding            | 安全发现过滤器             | 需要适配              | 不开发   | 不适用                                                                                       | AWR (应用风险感知) / Config (配置审计服务)   |
| ops-item           | 运维项过滤器               | 需要适配              | 不开发   | 不适用                                                                                       | O&M (运维管理)                               |
| config-compliance  | 配置合规性过滤器           | 需要适配              | 不开发   | 不适用                                                                                       | Config (配置审计服务)                        |

## 3. AOM特定Filters (`huaweicloud.aom-alarm`)

| Filter             | 说明                      | 是否可复用 | 开发状态 | 华为云API链接                                                                              | 涉及其他服务 |
| :----------------- | :------------------------ | :--------- | :------- | :---------------------------------------------------------------------------------------- | :----------- |
| alarm-rule    | 告警规则过滤          | 需要开发   | 待开发   | [查询指标类或者事件类告警规则列表](https://support.huaweicloud.com/api-aom/ListMetricOrEventAlarmRule.html) | 无           |

## 4. 通用Actions (适用于所有AOM资源)

| Action           | 说明                | 是否可复用            | 开发状态 | 华为云API链接                                                                                | 涉及其他服务                                          |
| :--------------- | :------------------ | :-------------------- |:-----| :------------------------------------------------------------------------------------------- | :---------------------------------------------------- |
| tag              | 添加标签            | 可复用 `tms.py`       | 已复用   | [为指定实例添加标签](https://support.huaweicloud.com/api-aom/api-tag-create.html)         | TMS                                                   |
| remove-tag       | 删除标签            | 可复用 `tms.py`       | 已复用   | [删除资源标签](https://support.huaweicloud.com/api-aom/api-tag-delete.html)               | TMS                                                   |
| rename-tag       | 重命名标签键        | 需要适配 (基于删+添)  | 不开发   | [为指定实例批量添加或删除标签](https://support.huaweicloud.com/api-aom/api-tag-batch.html) | TMS                                                   |
| mark-for-op      | 标记待操作          | 可复用                | 已复用   | 不适用                                                                                       | 无                                                    |
| auto-tag-user    | 自动标记创建者      | 可复用 `autotag.py`   | 已复用   | [为指定实例添加标签](https://support.huaweicloud.com/api-aom/api-tag-create.html)         | TMS, IAM                                              |
| notify           | 发送通知            | 可复用                | 不开发   | 不适用                                                                                       | SMN (消息通知服务) / 第三方通知渠道                   |
| webhook          | 调用Webhook         | 可复用                | 不开发   | 不适用                                                                                       | 无                                                    |
| put-metric       | 发布监控指标        | 需要适配              | 不开发   | 不适用                                                                                       | CES (云监控服务)                                      |
| invoke-lambda    | 调用函数            | 需要适配              | 不开发   | 不适用                                                                                       | FunctionGraph (函数工作流)                            |
| invoke-sfn       | 调用状态机          | 需要适配              | 不开发   | 不适用                                                                                       | FunctionGraph (函数工作流) / DMS (分布式消息服务)     |
| post-finding     | 推送安全发现        | 需要适配              | 不开发   | 不适用                                                                                       | AWR / Config                                          |
| post-item        | 推送运维项          | 需要适配              | 不开发   | 不适用                                                                                       | O&M                                                   |

## 5. AOM特定Actions (`huaweicloud.aom-alarm`)

| Action               | 说明               | 是否可复用   | 开发状态 | 华为云API链接                                                                              | 涉及其他服务      |
| :------------------- | :----------------- | :----------- | :------- | :---------------------------------------------------------------------------------------- | :---------------- |
| delete               | 删除告警规则       | 需要开发     | 待开发   | [删除指标类或者事件类告警规则](https://support.huaweicloud.com/api-aom/DeleteMetricOrEventAlarmRule.html) | 无                |
| update               | 更新告警规则       | 需要开发     | 待开发   | [添加或修改指标类或事件类告警规则](https://support.huaweicloud.com/api-aom/AddOrUpdateMetricOrEventAlarmRule.html) | 无                |
| add            | 添加告警规则 | 需要开发     | 待开发   | [添加或修改指标类或事件类告警规则](https://support.huaweicloud.com/api-aom/AddOrUpdateMetricOrEventAlarmRule.html) | 无                |

## 6. 开发建议

1. **资源定义**: 创建主要资源类: `huaweicloud.aom-alarm`，对应华为云AOM的告警规则管理。
2. **复用与适配**: 优先复用通用filters和actions（如`value`, `list-item`, `tms`等）。对于标签相关功能，可复用`tms.py`中的实现。对于自动标记功能，可复用`autotag.py`中的实现。
3. **开发新功能**: 针对告警规则的特定操作和过滤条件，开发对应的filters和actions，调用相应的华为云AOM API。
4. **特别考虑**:
   * **告警规则类型**: 支持指标类和事件类的不同过滤和操作需求。
   * **关联服务**: AOM可能与CCE、RDS、EVS等其他服务进行事件关联，需要实现相应的过滤能力。
   * **通知规则**: 告警规则可绑定通知规则，实现通知功能，需要提供相应的绑定操作。
5. **其他服务集成**: 涉及的华为云服务包括TMS（标签管理服务）、SMN（消息通知服务）、CCE（云容器引擎）、IAM（身份认证服务）、CES（云监控服务）、LTS（日志服务）、CTS（云审计服务）等，确保开发和使用时有正确的配置和权限。
