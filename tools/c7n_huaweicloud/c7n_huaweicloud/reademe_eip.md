# 华为云弹性公网IP(EIP)服务适配Cloud Custodian文档

## 1. 华为云EIP资源类型

华为云弹性公网IP服务主要涉及以下资源类型：

- `huaweicloud.eip`: 弹性公网IP。对应AWS的`aws.elastic-ip`。

## 2. 通用Filters (适用于所有EIP资源)

| Filter             | 说明                       | 是否可复用            | 开发状态 | 华为云API链接                                                                                   | 涉及其他服务                                 |
| :----------------- | :------------------------- | :-------------------- |:-----| :------------------------------------------------------------------------------------------- | :------------------------------------------- |
| value              | 基于资源属性值的通用过滤器 | 可复用                | 已复用   | 不适用                                                                                         | 无                                           |
| list-item          | 列表元素过滤器             | 可复用                | 已复用   | 不适用                                                                                         | 无                                           |
| event              | 事件过滤器                 | 可复用                | 已复用   | 不适用                                                                                         | LTS (日志流服务) / CTS (云审计服务)          |
| reduce             | 聚合过滤器                 | 可复用                | 已复用   | 不适用                                                                                         | 无                                           |
| marked-for-op      | 标记操作过滤器             | 可复用                | 已复用   | 不适用                                                                                         | 无                                           |
| tag-count          | 标签数量过滤器             | 可复用                | 已复用   | 不适用                                                                                         | 无                                           |
| tms                | 标签过滤器                 | 可复用 `tms.py`       | 已复用   | [查询指定实例的标签信息](https://support.huaweicloud.com/api-eip/eip_tag_0002.html)       | TMS (标签管理服务)                           |
| finding            | 安全发现过滤器             | 需要适配              | 不开发   | 不适用                                                                                         | AWR (应用风险感知) / Config (配置审计服务)   |
| ops-item           | 运维项过滤器               | 需要适配              | 不开发   | 不适用                                                                                         | O&M (运维管理)                               |
| config-compliance  | 配置合规性过滤器           | 需要适配              | 不开发   | 不适用                                                                                         | Config (配置审计服务)                        |

## 3. EIP特定Filters (`huaweicloud.eip`)

| Filter             | 说明                      | 是否可复用 | 开发状态 | 华为云API链接                                                                              | 涉及其他服务 |
| :----------------- | :------------------------ | :--------- | :------- | :---------------------------------------------------------------------------------------- | :----------- |
| associate-instance-type | 关联的实例类型过滤   | 需要开发   | 待开发   | [查询弹性公网IP列表](https://support.huaweicloud.com/api-eip/ListPublicipsV3.html)       | 无           |

## 4. 通用Actions (适用于所有EIP资源)

| Action           | 说明                | 是否可复用            | 开发状态 | 华为云API链接                                                                                | 涉及其他服务                                          |
| :--------------- | :------------------ | :-------------------- |:-----| :------------------------------------------------------------------------------------------- | :---------------------------------------------------- |
| tag              | 添加标签            | 可复用 `tms.py`       | 已复用   | [添加标签](https://support.huaweicloud.com/api-eip/eip_tag_0001.html)                    | TMS                                                   |
| remove-tag       | 删除标签            | 可复用 `tms.py`       | 已复用   | [删除标签](https://support.huaweicloud.com/api-eip/eip_tag_0003.html)                    | TMS                                                   |
| rename-tag       | 重命名标签键        | 需要适配 (基于删+添)  | 不开发   | [批量添加或删除标签](https://support.huaweicloud.com/api-eip/eip_tag_0004.html)          | TMS                                                   |
| mark-for-op      | 标记待操作          | 可复用                | 已复用   | 不适用                                                                                       | 无                                                    |
| auto-tag-user    | 自动标记创建者      | 可复用 `autotag.py`   | 已复用   | [添加标签](https://support.huaweicloud.com/api-eip/eip_tag_0001.html)                    | TMS, IAM                                              |
| copy-related-tag | 复制相关标签        | 需要适配              | 不开发   | [批量添加或删除标签](https://support.huaweicloud.com/api-eip/eip_tag_0004.html)          | TMS                                                   |
| notify           | 发送通知            | 可复用                | 不开发   | 不适用                                                                                       | SMN (消息通知服务) / 第三方通知渠道                   |
| webhook          | 调用Webhook         | 可复用                | 不开发   | 不适用                                                                                       | 无                                                    |
| put-metric       | 发布监控指标        | 需要适配              | 不开发   | 不适用                                                                                       | CES (云监控服务)                                      |
| invoke-lambda    | 调用函数            | 需要适配              | 不开发   | 不适用                                                                                       | FunctionGraph (函数工作流)                            |
| invoke-sfn       | 调用状态机          | 需要适配              | 不开发   | 不适用                                                                                       | FunctionGraph (函数工作流) / DMS (分布式消息服务)     |
| post-finding     | 推送安全发现        | 需要适配              | 不开发   | 不适用                                                                                       | AWR / Config                                          |
| post-item        | 推送运维项          | 需要适配              | 不开发   | 不适用                                                                                       | O&M                                                   |

## 5. EIP特定Actions (`huaweicloud.eip`)

| Action                 | 说明               | 是否可复用 | 开发状态 | 华为云API链接                                                                              | 涉及其他服务 |
| :--------------------- | :----------------- | :--------- | :------- | :---------------------------------------------------------------------------------------- | :----------- |
| delete                 | 删除弹性公网IP     | 需要开发   | 待开发   | [删除弹性公网IP](https://support.huaweicloud.com/api-eip/eip_api_0005.html)              | 无           |
| disassociate           | 解绑弹性公网IP     | 需要开发   | 待开发   | [解绑弹性公网IP](https://support.huaweicloud.com/api-eip/DisassociatePublicips.html)     | 无           |

## 6. 开发建议

1. **资源定义**: 创建一个主要资源类: `huaweicloud.eip`, 对应华为云弹性公网IP服务。
2. **复用与适配**: 优先复用通用filters和actions（如`value`, `list-item`, `tms`等）。对于标签相关功能，可复用`tms.py`中的实现。对于自动标记功能，可复用`autotag.py`中的实现。
3. **开发新功能**: 针对弹性公网IP的特定操作和过滤条件，开发对应的filters和actions，调用相应的华为云EIP API。
4. **特别考虑**:
   * **带宽管理**: 华为云EIP支持独享带宽和共享带宽两种模式，需要支持相关的过滤和操作。
   * **实例关联**: 支持EIP与不同类型实例（如ECS、负载均衡器等）的绑定与解绑。
   * **IP版本管理**: 考虑IPv4和IPv6不同版本的管理。
5. **其他服务集成**: 涉及的华为云服务包括TMS（标签管理服务）、VPC（虚拟私有云）、CES（云监控服务）、SMN（消息通知服务）、FunctionGraph（函数工作流）、IAM（身份认证服务）、LTS（日志服务）、CTS（云审计服务）等，确保开发和使用时有正确的配置和权限。
