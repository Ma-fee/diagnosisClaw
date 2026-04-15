# 阿里云 ACK 集群 GPU 监控工具开发指南

## 1. 阿里云 ACK 集群 GPU 监控体系架构

### 1.1 ACK 集群 GPU 监控整体架构

阿里云容器服务 Kubernetes 版（ACK）构建了完整的 GPU 监控体系，基于 Exporter+Prometheus+Grafana 架构实现丰富的 GPU 可观测性场景。ACK 集群通过多种组件协同工作，实现对 GPU 资源的全方位监控，包括 GPU 设备插件（NVIDIA Device Plugin）、GPU Exporter、Prometheus Server 以及 ARMS 平台的集成[(191)](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/observability-best-practices)。

在 ACK 集群中，GPU 监控采用了多层次的数据采集架构。首先，NVIDIA GPU 设备通过 NVIDIA DCGM（Data Center GPU Manager）标准协议暴露底层硬件指标，包括显存使用量、GPU 利用率、温度、功耗等关键信息。这些原始指标通过 ACK 部署的 GPU Exporter 组件进行采集，该组件兼容开源 DCGM Exporter 的同时，根据阿里云的业务场景增加了自定义指标[(14)](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/introduction-to-metrics)。

ACK GPU 监控 2.0 版本提供了两种部署模式：独占 GPU 模式和共享 GPU 模式。在独占 GPU 模式下，每个 Pod 独占一张或多张完整的 GPU 卡；在共享 GPU 模式下，多个 Pod 可以共享同一张 GPU 卡的显存和算力资源[(70)](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/cgpu-overview)。这两种模式都支持完整的监控指标采集，包括显存使用量、GPU 利用率、显存占用率等核心指标[(77)](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/best-practices-for-monitoring-gpu-resources)。

### 1.2 ACK 默认监控数据采集机制

ACK 集群默认的 GPU 监控数据采集通过多个关键组件协同完成。主要包括以下几个核心组件：

\*\*GPU 设备插件（NVIDIA Device Plugin）\*\* 作为 Kubernetes 集群中用于管理 GPU 的核心组件，以 DaemonSet 方式部署在每个 GPU 节点上。该组件负责向 Kubernetes 报告节点上 GPU 的数量、型号、健康状态等信息，使得 Kubernetes 能够像管理 CPU 和内存一样管理 GPU 资源。在 ACK 1.32 及以上版本中，该组件通过控制台组件管理，支持手动升级；而在 1.20 至 1.31 版本中，则采用 Static Pod 方式部署，随节点池自动升级。

**ACK GPU Exporter**是阿里云自主开发的监控组件，负责采集 GPU 相关的详细指标。该组件基于开源 DCGM Exporter 开发，提供了兼容 NVIDIA DCGM 标准的监控指标集，同时增加了阿里云特有的自定义指标[(191)](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/observability-best-practices)。通过该组件，可以获取 GPU 利用率、显存使用量、内存带宽利用率、温度、功耗等详细指标数据。

**Prometheus 监控系统**作为时序数据采集和存储的核心，负责从各个 Exporter 拉取监控指标并进行存储[(83)](https://blog.csdn.net/weixin_42795092/article/details/154662359)。在 ACK 集群中，Prometheus 可以通过阿里云托管的 Prometheus 服务或自建 Prometheus 两种方式部署。默认情况下，ACK 集群会自动部署阿里云托管的 Prometheus 服务，提供开箱即用的监控能力[(192)](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/use-alibaba-cloud-prometheus-service-to-monitor-an-ack-cluster)。

**ARMS 平台集成**是将监控数据进行统一展示和告警的关键环节。ACK 集群采集的所有监控指标都会通过 ARMS 平台进行统一管理，用户可以在 ARMS 控制台中查看 GPU 监控大盘、创建告警规则、配置通知等[(191)](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/observability-best-practices)。ARMS 平台提供了预置的 GPU 监控大盘，包括集群维度和节点维度的监控面板，展示了 GPU 使用率、显存使用量、温度等关键指标[(188)](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/panels)。

### 1.3 ARMS 平台 GPU 监控指标体系

ARMS 平台的 GPU 监控指标体系包含 DCGM 支持的标准指标和阿里云自定义指标两大类。

**DCGM 标准指标**主要包括以下几个维度：

利用率指标方面，DCGM\_FI\_DEV\_GPU\_UTIL 表示 GPU 利用率，即在一个周期时间内（1 秒或 1/6 秒，根据 GPU 产品而定），一个或多个核函数处于 Active 的时间百分比。DCGM\_FI\_DEV\_MEM\_COPY\_UTIL 表示内存带宽利用率，DCGM\_FI\_DEV\_ENC\_UTIL 和 DCGM\_FI\_DEV\_DEC\_UTIL 分别表示编码器和解码器利用率。

内存指标方面，DCGM\_FI\_DEV\_FB\_FREE 表示帧缓存（显存）剩余数，单位为 MiB；DCGM\_FI\_DEV\_FB\_USED 表示帧缓存已使用数，该值与 nvidia-smi 命令中 Memory-Usage 的已使用值对应。

剖析指标方面，包括 DCGM\_FI\_PROF\_GR\_ENGINE\_ACTIVE（Graphics 或 Compute 引擎活跃度）、DCGM\_FI\_PROF\_SM\_ACTIVE（SM 流式多处理器活跃度）、DCGM\_FI\_PROF\_SM\_OCCUPANCY（SM 占用率）、DCGM\_FI\_PROF\_PIPE\_TENSOR\_ACTIVE（Tensor Core 利用率）等，这些指标用于深入分析 GPU 的计算性能和资源利用情况。

**阿里云自定义指标**针对容器化场景进行了优化，主要包括：

DCGM\_CUSTOM\_PROCESS\_SM\_UTIL 表示 GPU 线程的 SM 利用率，DCGM\_CUSTOM\_PROCESS\_MEM\_COPY\_UTIL 表示 GPU 线程的内存拷贝利用率，DCGM\_CUSTOM\_PROCESS\_ENCODE\_UTIL 和 DCGM\_CUSTOM\_PROCESS\_DECODE\_UTIL 分别表示 GPU 线程的编码器和解码器利用率。

DCGM\_CUSTOM\_PROCESS\_MEM\_USED 表示 GPU 线程当前使用的显存，DCGM\_CUSTOM\_CONTAINER\_MEM\_ALLOCATED 表示为容器分配的显存，DCGM\_CUSTOM\_CONTAINER\_CP\_ALLOCATED 表示为容器分配的一张 GPU 卡上部分算力占该 GPU 卡总算力的比例，值的区间为 \[0, 1]。

此外，还包括 DCGM\_CUSTOM\_DEV\_FB\_TOTAL（GPU 卡的总显存）、DCGM\_CUSTOM\_DEV\_FB\_ALLOCATED（GPU 卡已分配显存占总显存的比例）等指标，这些指标为容器化 GPU 资源管理提供了更精细的监控能力。

## 2. GPU 监控数据采集技术实现

### 2.1 GPU 指标数据流转路径

GPU 监控数据在 ACK 集群中的流转遵循标准化的路径，确保数据的准确采集和可靠传输。整个数据流转过程可以分为以下几个关键环节：

**数据采集层**：GPU 硬件通过 NVIDIA 驱动暴露底层指标，这些指标通过 DCGM 协议接口提供访问。ACK 部署的 GPU Exporter 作为数据采集代理，通过调用 DCGM API 获取原始监控数据。在边缘场景下，当 Prometheus Server 无法直接访问 GPU 节点时，通过 Raven 组件实现公网场景下边缘节点的可观测性，Raven Agent 与目标节点建立加密通道，访问 GPU 采集端口获取监控数据。

**数据传输层**：采集到的数据通过 Prometheus 的 Pull 模型进行传输。Prometheus Server 按照配置的抓取间隔定期从各个 Exporter 拉取数据，默认抓取间隔为 15 秒[(87)](https://juejin.cn/post/7474554863448604722)。在 ACK 集群中，Prometheus 通过节点名称而非节点 IP 来采集指标，CoreDNS 配置了 hosts 插件，将节点名称解析到相应的服务地址。

**数据存储层**：Prometheus 负责时序数据的高效存储，采用自定义的时间序列数据库格式。数据在 Prometheus 中以时间序列的形式存储，每个时间序列由指标名称和一组标签（Labels）唯一标识。在 ARMS 平台中，指标数据可以选择存储 30、90、180 或 365 天，调用链数据可选择存储 15、30、60 或 90 天[(90)](https://help.aliyun.com/zh/arms/application-monitoring/product-overview/billing-faq)。

**数据展示层**：存储在 Prometheus 或 ARMS 中的数据通过 Grafana 等可视化工具进行展示。ACK 提供了预置的 GPU 监控大盘，包括集群维度和节点维度的监控面板，展示了 GPU 使用率、显存使用量、温度等关键指标的实时数据和历史趋势[(188)](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/panels)。

### 2.2 基于 Label 和注解的 Pod 过滤机制

ACK 集群支持通过 Label 和注解对 Pod 进行精确过滤，实现细粒度的资源管理和监控。

**Label 过滤机制**：用户可以为 Pod 定义特定的 Label 标签，系统根据这些标签进行资源调度和监控过滤。在 GPU 监控场景中，用户可以通过设置 app: pytorchjob 和 job-name: dolphin 这样的 Label 来标识特定的 GPU 工作负载，监控系统根据这些 Label 自动识别和采集相关 Pod 的 GPU 指标[(2)](http://m.toutiao.com/group/6321548847668396289/?upstream_biz=doubao)。

**注解（Annotation）机制**：注解用于存储非标识性的元数据，在 GPU 监控场景中，可以通过注解[arena.kubeflow.org/username](https://arena.kubeflow.org/username): [system:serviceaccount:kube-ai:t-wanghai-1015944683219615.onaliyun.com](https://system:serviceaccount:kube-ai:t-wanghai-1015944683219615.onaliyun.com)来关联用户身份信息[(2)](http://m.toutiao.com/group/6321548847668396289/?upstream_biz=doubao)。这种机制在多租户场景下特别有用，可以实现 GPU 资源使用的用户级追踪和计费。

在实际实现中，监控系统通过 Kubernetes API 获取所有 Pod 的清单，然后根据预设的 Label 选择器和注解过滤器进行筛选。只有同时满足 Label 条件（app=pytorchjob 且 job-name=dolphin）和注解条件（[arena.kubeflow.org/username](https://arena.kubeflow.org/username)匹配特定用户）的 Pod 才会被纳入监控范围。

### 2.3 监控粒度与数据采集频率

根据用户需求，监控粒度设置为小时级别，这意味着系统每小时采集一次 GPU 相关指标。在实际实现中，需要考虑以下几个方面：

**数据采集频率配置**：Prometheus 的抓取频率通过 scrape\_interval 参数配置，默认值为 15 秒[(87)](https://juejin.cn/post/7474554863448604722)。为了实现小时级监控粒度，需要在 Prometheus 配置中设置适当的抓取频率，建议设置为 1 分钟或更短，以确保小时级聚合数据的准确性。同时，需要配置合理的 evaluation\_interval 参数，控制规则评估的频率。

**数据聚合策略**：对于小时级监控，系统需要对原始的高频采集数据进行聚合处理。常用的聚合方法包括平均值（average）、最大值（max）、最小值（min）和总和（sum）。对于 GPU 利用率，通常使用平均值来反映该小时内的平均使用情况；对于显存使用量，可以使用最大值来识别峰值占用。

**存储策略优化**：由于 GPU 监控数据具有时间序列特性且数据量较大，需要合理配置存储策略。ARMS 平台提供了灵活的存储周期选择，指标数据可选择存储 30、90、180 或 365 天[(90)](https://help.aliyun.com/zh/arms/application-monitoring/product-overview/billing-faq)。对于小时级监控数据，建议根据业务需求选择合适的存储周期，平衡数据保留需求和成本。

**告警触发机制**：基于小时级监控数据的告警需要考虑数据的时间窗口。例如，当 GPU 利用率在过去 1 小时内的平均值超过 80% 时触发告警，或者当显存占用率在过去 1 小时内的最大值超过 90% 时触发告警。这种基于时间窗口的告警机制能够有效避免瞬时波动导致的误告警。

## 3. ARMS API 接口调研与数据读取

### 3.1 ARMS API 体系与认证机制

ARMS 平台提供了完整的 OpenAPI 接口体系，支持通过 API 方式查询监控指标、管理监控配置等操作。ARMS OpenAPI 采用 RPC 签名风格，开发者可以通过 SDK 或直接调用 API 的方式访问平台功能。

**API 认证机制**：ARMS API 使用阿里云的 AccessKey 认证机制，需要在请求中包含 AccessKey ID 和 AccessKey Secret 进行身份验证。对于不同版本的 ARMS 服务，认证方式略有差异：V1 版本支持 Token 认证，V2 版本默认必须使用账号的 AccessKey 和 SecretKey 进行访问。在实际开发中，建议使用阿里云官方提供的 SDK，这些 SDK 已经封装了签名机制，简化了 API 调用的复杂度。

**API 接口分类**：ARMS API 主要分为以下几类：环境管理接口（CreateEnvironment、UpdateEnvironment 等）、监控配置接口（CreatePrometheusMonitoring、UpdatePrometheusMonitoring 等）、指标查询接口（QueryCommercialUsage 等）、告警管理接口（CreatePrometheusAlertRule、UpdatePrometheusAlertRule 等）。对于 GPU 监控场景，最常用的是指标查询接口，用于获取 GPU 相关的时序数据。

**API 调用限制**：ARMS API 有一定的调用频率限制，不同接口的 QPS 限制不同。在开发监控程序时，需要合理设计 API 调用策略，避免因频繁调用导致的限流问题。同时，建议实现重试机制，处理因网络波动或服务端临时问题导致的调用失败。

### 3.2 GPU 相关指标 API 查询方法

ARMS 平台提供了丰富的 API 接口用于查询 GPU 相关监控指标，主要通过 Prometheus API 协议实现。

**Prometheus API 查询方式**：ARMS 兼容 Prometheus 的 HTTP API 规范，支持通过 /api/v1/query 接口进行瞬时查询，通过 /api/v1/query\_range 接口进行范围查询。查询时需要使用 PromQL（Prometheus Query Language）表达式，例如查询 GPU 利用率的表达式可以写作：avg (rate (nvidia\_gpu\_utilization \[5m])) by (pod)。

**GPU 指标查询示例**：



* 查询所有 GPU Pod 的显存使用量：sum by (pod) (nvidia\_gpu\_memory\_used)

* 查询特定 Label 的 GPU Pod 利用率：avg by (pod) (nvidia\_gpu\_utilization) \* on (pod) group\_left () label\_replace (kube\_pod\_labels {label\_app="pytorchjob", label\_job-name="dolphin"}, "pod", "\$1", "pod", "(.\*)")

* 查询 GPU 显存占用率：(sum by (pod) (nvidia\_gpu\_memory\_used) /sum by (pod) (nvidia\_gpu\_memory\_total)) \* 100

**ARMS 特有指标查询**：除了标准的 Prometheus 指标外，ARMS 还提供了一些特有的 GPU 监控指标，如 dcgm\_fi\_dev\_gpu\_util（GPU 利用率）、dcgm\_fi\_dev\_fb\_used（显存已使用量）、dcgm\_custom\_process\_mem\_used（进程显存使用量）等[(186)](https://www.alibabacloud.com/help/en/cs/user-guide/acs-gpu-pod-monitoring-indicators)。这些指标可以通过 ARMS 的指标探索功能进行查询和验证。

**API 调用示例（Python）**：



```
import requests

import time

from datetime import datetime, timedelta

\# ARMS Prometheus API地址

api\_url = "https://arms-prometheus-prod-ap-southeast-1.aliyuncs.com/api/v1/query\_range"

\# 查询参数

query\_params = {

&#x20;   "query": 'avg by (pod) (dcgm\_fi\_dev\_gpu\_util) \* on (pod) group\_left() '

&#x20;            'label\_replace(kube\_pod\_labels{label\_app="pytorchjob", label\_job-name="dolphin"}, "pod", "\$1", "pod", "(.\*)")',

&#x20;   "start": int((datetime.now() - timedelta(hours=1)).timestamp()),

&#x20;   "end": int(datetime.now().timestamp()),

&#x20;   "step": 300  # 5分钟间隔

}

\# 请求头（需要替换为实际的AccessKey认证信息）

headers = {

&#x20;   "Authorization": "Bearer \<your\_access\_key>",

&#x20;   "Content-Type": "application/json"

}

\# 发送查询请求

response = requests.get(api\_url, params=query\_params, headers=headers)

if response.status\_code == 200:

&#x20;   data = response.json()

&#x20;   print("GPU利用率查询结果：")

&#x20;   for result in data.get("data", {}).get("result", \[]):

&#x20;       print(f"Pod: {result\['metric']\['pod']}")

&#x20;       print(f"时间序列数据点数量: {len(result\['values'])}")

&#x20;       print(f"最后一个数据点: {result\['values']\[-1]}")

else:

&#x20;   print(f"查询失败，状态码: {response.status\_code}")

&#x20;   print(response.text)
```

### 3.3 Python 程序访问 ARMS 数据的技术实现

基于 Python 实现 ARMS 数据访问需要使用阿里云官方 SDK 或直接调用 REST API。

**使用阿里云 SDK**：阿里云提供了 Python SDK（aliyun-python-sdk-arms），可以方便地调用 ARMS API。安装方法：pip install aliyun-python-sdk-arms。使用示例：



```
from aliyunsdkcore.client import AcsClient

from aliyunsdkcore.acs\_exception.exceptions import ClientException, ServerException

from aliyunsdkarms.request.v20190808 import QueryMetricRequest

\# 初始化AcsClient

client = AcsClient(

&#x20;   access\_key\_id='\<your\_access\_key\_id>',

&#x20;   access\_key\_secret='\<your\_access\_key\_secret>',

&#x20;   region\_id='\<your\_region\_id>'

)

\# 创建查询请求

request = QueryMetricRequest.QueryMetricRequest()

request.set\_accept\_format('json')

request.set\_Project('arms-prom')

request.set\_Metric('dcgm\_fi\_dev\_gpu\_util')

request.set\_Dimensions('{"pod":"gpu-pod-1"}')

request.set\_StartTime(int((datetime.now() - timedelta(hours=1)).timestamp()))

request.set\_EndTime(int(datetime.now().timestamp()))

request.set\_Period(300)  # 5分钟

try:

&#x20;   response = client.do\_action\_with\_exception(request)

&#x20;   print("ARMS API响应：")

&#x20;   print(response)

except ClientException as e:

&#x20;   print(f"客户端异常: {e}")

except ServerException as e:

&#x20;   print(f"服务端异常: {e}")
```

**直接调用 REST API**：如果不想使用 SDK，也可以直接通过 requests 库调用 ARMS REST API。需要注意的是，ARMS API 需要使用阿里云的签名机制，具体实现可以参考阿里云官方文档中的签名算法说明。

**数据解析与处理**：ARMS API 返回的数据格式为 JSON，需要进行解析和处理。对于时序数据，返回结果包含 metric（指标元数据）和 values（时间序列数据点）两个主要部分。values 字段是一个二维数组，第一维是时间戳（毫秒级），第二维是指标值。在解析时需要注意数据类型转换和异常处理。

## 4. 权限配置与认证体系设计

### 4.1 ACK 集群权限模型与 RBAC 配置

ACK 集群采用 Kubernetes 原生的基于角色的访问控制（RBAC）机制，结合阿里云的资源访问控制（RAM）体系，构建了多层次的权限管理架构。

**RAM 权限配置**：在阿里云环境中，首先需要为监控程序创建相应的 RAM 用户或角色。RAM 权限控制云资源层面的访问权限，包括创建、查看、升级、删除集群等操作。对于 GPU 监控场景，建议创建一个具有最小权限的 RAM 用户，只授予查询监控数据的权限，避免赋予过多的操作权限。

创建 RAM 用户的步骤：



1. 登录阿里云 RAM 控制台

2. 在用户管理页面创建新用户，设置用户名和 AccessKey

3. 为用户附加权限策略，建议使用系统策略 AliyunCloudMonitorReadOnlyAccess，该策略提供云监控只读权限

4. 如果需要访问 ARMS 特定功能，还需要附加 AliyunARMSReadOnlyAccess 等相关策略

**RBAC 权限配置**：RBAC 控制集群内部资源的访问权限，包括对 Pods、Services、Nodes 等 Kubernetes 资源的操作权限。为了让监控程序能够访问 GPU 相关的 Pod 信息，需要创建相应的 Role 和 RoleBinding。

创建 RBAC 权限的示例配置：



```
\# 创建Role，定义对Pods的只读权限

apiVersion: rbac.authorization.k8s.io/v1

kind: Role

metadata:

&#x20; name: gpu-monitor-role

&#x20; namespace: default

rules:

\- apiGroups: \[""]

&#x20; resources: \["pods"]

&#x20; verbs: \["get", "list", "watch"]

\- apiGroups: \[""]

&#x20; resources: \["pods/metrics"]

&#x20; verbs: \["get"]

\# 创建RoleBinding，将Role绑定到Service Account

apiVersion: rbac.authorization.k8s.io/v1

kind: RoleBinding

metadata:

&#x20; name: gpu-monitor-rolebinding

&#x20; namespace: default

subjects:

\- kind: ServiceAccount

&#x20; name: gpu-monitor-sa

&#x20; namespace: default

roleRef:

&#x20; kind: Role

&#x20; name: gpu-monitor-role

&#x20; apiGroup: rbac.authorization.k8s.io
```

**Service Account 配置**：在 Kubernetes 中，Pod 通过 Service Account 进行身份认证。建议为监控程序创建专门的 Service Account，并配置相应的 Token 用于 API 访问。

创建 Service Account 的命令：



```
kubectl create serviceaccount gpu-monitor-sa -n default
```

获取 Service Account 的 Token：



```
kubectl get secret \$(kubectl get serviceaccount gpu-monitor-sa -n default -o jsonpath='{.secrets\[0].name}') -n default -o jsonpath='{.data.token}' | base64 -d
```

### 4.2 ARMS 平台权限管理与认证

ARMS 平台的权限管理涉及多个层面，需要综合考虑集群访问权限、ARMS 服务权限以及具体的监控指标访问权限。

**ARMS 服务访问权限**：ARMS 服务本身需要开通相应的权限才能使用。首次使用 ARMS 时，需要使用阿里云主账号或具有足够权限的 RAM 用户进行授权。ARMS 服务角色 AliyunServiceRoleForARMS 用于允许 ARMS 服务访问相关资源。

**Prometheus 监控权限**：ARMS 的 Prometheus 监控功能需要特定的权限配置。在 ARMS 控制台中，需要为 Prometheus 实例配置正确的访问权限，包括读取 Prometheus 指标、创建告警规则、管理监控配置等。

**跨集群访问权限**：如果监控程序需要访问多个 ACK 集群的 GPU 数据，需要在每个集群中配置相应的权限。可以通过创建 ClusterRole 和 ClusterRoleBinding 来实现跨命名空间的访问权限。

### 4.3 多租户场景下的权限隔离

根据用户提供的注解信息[arena.kubeflow.org/username](https://arena.kubeflow.org/username): [system:serviceaccount:kube-ai:t-wanghai-1015944683219615.onaliyun.com](https://system:serviceaccount:kube-ai:t-wanghai-1015944683219615.onaliyun.com)，可以看出这是一个多租户 Kubeflow 场景。在这种环境下，权限隔离尤为重要。

**基于 Namespace 的隔离**：Kubeflow 多租户模式通常为每个用户创建独立的 Namespace，通过 Namespace 实现资源隔离。监控程序需要能够识别不同用户的 GPU 使用情况，可以通过 Pod 的注解信息来关联用户身份。

**基于 Label 的资源标识**：通过设置 app: pytorchjob 和 job-name: dolphin 这样的 Label，可以精确标识需要监控的 GPU 工作负载。同时，通过[arena.kubeflow.org/username](https://arena.kubeflow.org/username)注解可以实现用户级的资源追踪[(2)](http://m.toutiao.com/group/6321548847668396289/?upstream_biz=doubao)。

**细粒度权限控制**：在多租户场景下，建议实现更细粒度的权限控制：



* 不同用户只能查看自己的 GPU 使用数据

* 管理员用户可以查看所有用户的 GPU 使用情况

* 支持基于项目或团队的分组管理

* 实现 GPU 资源使用的配额管理和计费统计

**安全注意事项**：



1. 避免使用明文存储 AccessKey，建议使用 Kubernetes Secret 进行管理

2. 为不同的监控任务创建独立的 Service Account，避免权限过度集中

3. 定期轮换密钥，提高系统安全性

4. 配置合理的访问控制策略，限制不必要的网络访问

## 5. 监控程序设计与开发

### 5.1 系统架构设计与技术选型

基于用户需求，监控程序需要实现小时级的 GPU 监控，并通过企业微信 webhook 推送告警信息。系统架构设计如下：

**整体架构设计**：监控程序采用模块化设计，主要包括以下几个核心组件：



1. **数据采集模块**：负责从 ARMS API 和 Kubernetes API 采集 GPU 相关指标数据

2. **数据处理模块**：对采集到的数据进行解析、计算和格式化处理

3. **告警判断模块**：基于预设的阈值规则判断是否触发告警

4. **消息推送模块**：通过企业微信 webhook 发送告警信息

5. **定时调度模块**：控制数据采集和处理的执行频率

**技术选型建议**：



* 编程语言：Python 3.8+（建议使用 Python 3.10 及以上版本）

* 框架选择：使用 Flask 或 FastAPI 构建轻量级 Web 服务

* 定时任务：使用 APScheduler 实现定时数据采集

* 依赖管理：使用 Poetry 或 Pipenv 管理项目依赖

* 配置管理：使用 pydantic 进行配置解析和验证

* 日志管理：使用 structlog 或 logging 模块实现结构化日志

### 5.2 Python 监控程序核心实现

监控程序的核心实现包括数据采集、处理和告警推送三个主要功能。

**数据采集实现**：



```
import requests

from datetime import datetime, timedelta

import pandas as pd

class GPUDataCollector:

&#x20;   def \_\_init\_\_(self, arms\_api\_url, access\_token, kube\_config\_path):

&#x20;       self.arms\_api\_url = arms\_api\_url

&#x20;       self.access\_token = access\_token

&#x20;       self.kube\_config\_path = kube\_config\_path

&#x20;      &#x20;

&#x20;   def query\_arms\_metrics(self, query\_expr, start\_time, end\_time, step=300):

&#x20;       """查询ARMS监控指标"""

&#x20;       params = {

&#x20;           "query": query\_expr,

&#x20;           "start": int(start\_time.timestamp()),

&#x20;           "end": int(end\_time.timestamp()),

&#x20;           "step": step

&#x20;       }

&#x20;       headers = {

&#x20;           "Authorization": f"Bearer {self.access\_token}",

&#x20;           "Content-Type": "application/json"

&#x20;       }

&#x20;       response = requests.get(f"{self.arms\_api\_url}/api/v1/query\_range",&#x20;

&#x20;                              params=params, headers=headers)

&#x20;       if response.status\_code != 200:

&#x20;           raise Exception(f"ARMS API query failed: {response.status\_code}")

&#x20;       return response.json()

&#x20;  &#x20;

&#x20;   def get\_gpu\_pods(self, label\_selector="app=pytorchjob,job-name=dolphin"):

&#x20;       """获取符合条件的GPU Pod列表"""

&#x20;       # 这里需要实现Kubernetes API访问逻辑

&#x20;       # 可以使用kubernetes-python库或直接调用Kubernetes REST API

&#x20;       pass

&#x20;  &#x20;

&#x20;   def collect\_gpu\_metrics(self):

&#x20;       """采集GPU相关指标"""

&#x20;       end\_time = datetime.now()

&#x20;       start\_time = end\_time - timedelta(hours=1)

&#x20;      &#x20;

&#x20;       # 查询GPU利用率

&#x20;       gpu\_util\_query = 'avg by (pod) (dcgm\_fi\_dev\_gpu\_util) \* on (pod) group\_left() ' \\

&#x20;                       'label\_replace(kube\_pod\_labels{label\_app="pytorchjob", label\_job-name="dolphin"}, ' \\

&#x20;                       '"pod", "\$1", "pod", "(.\*)")'

&#x20;      &#x20;

&#x20;       # 查询显存使用量

&#x20;       memory\_used\_query = 'sum by (pod) (dcgm\_fi\_dev\_fb\_used) \* on (pod) group\_left() ' \\

&#x20;                          'label\_replace(kube\_pod\_labels{label\_app="pytorchjob", label\_job-name="dolphin"}, ' \\

&#x20;                          '"pod", "\$1", "pod", "(.\*)")'

&#x20;      &#x20;

&#x20;       # 查询显存总量

&#x20;       memory\_total\_query = 'sum by (pod) (dcgm\_custom\_dev\_fb\_total) \* on (pod) group\_left() ' \\

&#x20;                           'label\_replace(kube\_pod\_labels{label\_app="pytorchjob", label\_job-name="dolphin"}, ' \\

&#x20;                           '"pod", "\$1", "pod", "(.\*)")'

&#x20;      &#x20;

&#x20;       # 执行查询

&#x20;       gpu\_util\_data = self.query\_arms\_metrics(gpu\_util\_query, start\_time, end\_time)

&#x20;       memory\_used\_data = self.query\_arms\_metrics(memory\_used\_query, start\_time, end\_time)

&#x20;       memory\_total\_data = self.query\_arms\_metrics(memory\_total\_query, start\_time, end\_time)

&#x20;      &#x20;

&#x20;       # 解析数据

&#x20;       results = \[]

&#x20;       for i, pod\_name in enumerate(gpu\_util\_data.get("data", {}).get("result", \[])):

&#x20;           pod\_metrics = {

&#x20;               "pod\_name": pod\_name\["metric"]\["pod"],

&#x20;               "gpu\_utilization": pod\_name\["values"]\[-1]\[1],  # 最后一个数据点

&#x20;               "memory\_used": memory\_used\_data\["data"]\["result"]\[i]\["values"]\[-1]\[1],

&#x20;               "memory\_total": memory\_total\_data\["data"]\["result"]\[i]\["values"]\[-1]\[1],

&#x20;               "timestamp": datetime.fromtimestamp(int(pod\_name\["values"]\[-1]\[0]))

&#x20;           }

&#x20;           # 计算显存占用率

&#x20;           pod\_metrics\["memory\_usage\_rate"] = (float(pod\_metrics\["memory\_used"]) /&#x20;

&#x20;                                              float(pod\_metrics\["memory\_total"])) \* 100

&#x20;           results.append(pod\_metrics)

&#x20;      &#x20;

&#x20;       return results
```

**告警判断实现**：



```
class AlertManager:

&#x20;   def \_\_init\_\_(self, alert\_rules):

&#x20;       self.alert\_rules = alert\_rules  # 告警规则配置

&#x20;  &#x20;

&#x20;   def check\_alerts(self, metrics\_data):

&#x20;       """检查是否触发告警"""

&#x20;       alerts = \[]

&#x20;       for pod\_data in metrics\_data:

&#x20;           pod\_name = pod\_data\["pod\_name"]

&#x20;          &#x20;

&#x20;           # 检查GPU利用率告警

&#x20;           if float(pod\_data\["gpu\_utilization"]) > self.alert\_rules\["gpu\_utilization\_threshold"]:

&#x20;               alerts.append({

&#x20;                   "type": "GPU\_UTILIZATION\_HIGH",

&#x20;                   "level": "WARNING",

&#x20;                   "message": f"Pod {pod\_name} GPU利用率过高: {pod\_data\['gpu\_utilization']}%",

&#x20;                   "pod": pod\_name,

&#x20;                   "value": pod\_data\["gpu\_utilization"],

&#x20;                   "threshold": self.alert\_rules\["gpu\_utilization\_threshold"]

&#x20;               })

&#x20;          &#x20;

&#x20;           # 检查显存占用率告警

&#x20;           if float(pod\_data\["memory\_usage\_rate"]) > self.alert\_rules\["memory\_usage\_rate\_threshold"]:

&#x20;               alerts.append({

&#x20;                   "type": "MEMORY\_USAGE\_RATE\_HIGH",

&#x20;                   "level": "CRITICAL",

&#x20;                   "message": f"Pod {pod\_name} 显存占用率过高: {pod\_data\['memory\_usage\_rate']}%",

&#x20;                   "pod": pod\_name,

&#x20;                   "value": pod\_data\["memory\_usage\_rate"],

&#x20;                   "threshold": self.alert\_rules\["memory\_usage\_rate\_threshold"]

&#x20;               })

&#x20;      &#x20;

&#x20;       return alerts
```

### 5.3 企业微信 Webhook 集成实现

企业微信提供了群机器人功能，通过 Webhook URL 可以实现外部系统向企业微信群发送消息。

**企业微信机器人配置**：



1. 在企业微信客户端中选择需要接收告警的群聊

2. 点击群聊右上角的 "..." 图标，选择 "添加机器人"

3. 填写机器人名称和简介，创建后会生成一个 Webhook URL

4. 记录该 URL，用于后续的消息推送

**消息推送实现**：



```
import requests

import json

class WeComBot:

&#x20;   def \_\_init\_\_(self, webhook\_url):

&#x20;       self.webhook\_url = webhook\_url

&#x20;  &#x20;

&#x20;   def send\_text\_message(self, content, mentioned\_mobiles=None):

&#x20;       """发送文本消息"""

&#x20;       message = {

&#x20;           "msgtype": "text",

&#x20;           "text": {

&#x20;               "content": content

&#x20;           }

&#x20;       }

&#x20;       if mentioned\_mobiles:

&#x20;           message\["text"]\["mentioned\_mobiles"] = mentioned\_mobiles

&#x20;       self.\_send\_message(message)

&#x20;  &#x20;

&#x20;   def send\_markdown\_message(self, content):

&#x20;       """发送Markdown格式消息"""

&#x20;       message = {

&#x20;           "msgtype": "markdown",

&#x20;           "markdown": {

&#x20;               "content": content

&#x20;           }

&#x20;       }

&#x20;       self.\_send\_message(message)

&#x20;  &#x20;

&#x20;   def \_send\_message(self, message):

&#x20;       """发送消息到企业微信"""

&#x20;       headers = {

&#x20;           "Content-Type": "application/json"

&#x20;       }

&#x20;       response = requests.post(self.webhook\_url,&#x20;

&#x20;                               data=json.dumps(message),&#x20;

&#x20;                               headers=headers)

&#x20;       if response.status\_code != 200:

&#x20;           raise Exception(f"企业微信消息发送失败: {response.status\_code}")

&#x20;       result = response.json()

&#x20;       if result\["errcode"] != 0:

&#x20;           raise Exception(f"企业微信API错误: {result\['errcode']}, {result\['errmsg']}")

\# 使用示例

if \_\_name\_\_ == "\_\_main\_\_":

&#x20;   # 初始化企业微信机器人

&#x20;   webhook\_url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=your\_webhook\_key"

&#x20;   wecom\_bot = WeComBot(webhook\_url)

&#x20;  &#x20;

&#x20;   # 发送告警消息示例

&#x20;   alert\_message = """# ACK集群GPU监控告警\n

&#x20;   \## 告警类型: GPU利用率过高

&#x20;   \*\*Pod名称\*\*: gpu-pod-1

&#x20;   \*\*当前利用率\*\*: 85%

&#x20;   \*\*阈值\*\*: 80%

&#x20;   \*\*时间\*\*: 2024-10-01 15:00:00

&#x20;   """

&#x20;  &#x20;

&#x20;   wecom\_bot.send\_markdown\_message(alert\_message)
```

### 5.4 定时任务与调度框架

为了实现小时级的监控，需要使用定时任务框架来调度数据采集和告警检查。

**使用 APScheduler 实现定时任务**：



```
from apscheduler.schedulers.background import BackgroundScheduler

from apscheduler.triggers.cron import CronTrigger

import logging

class SchedulerManager:

&#x20;   def \_\_init\_\_(self, config):

&#x20;       self.scheduler = BackgroundScheduler()

&#x20;       self.config = config

&#x20;       self.gpu\_collector = GPUDataCollector(

&#x20;           arms\_api\_url=config\["arms\_api\_url"],

&#x20;           access\_token=config\["arms\_access\_token"],

&#x20;           kube\_config\_path=config\["kube\_config\_path"]

&#x20;       )

&#x20;       self.alert\_manager = AlertManager(alert\_rules=config\["alert\_rules"])

&#x20;       self.wecom\_bot = WeComBot(webhook\_url=config\["wecom\_webhook\_url"])

&#x20;      &#x20;

&#x20;   def start\_scheduler(self):

&#x20;       """启动调度器"""

&#x20;       # 创建定时任务

&#x20;       self.scheduler.add\_job(

&#x20;           self.run\_monitoring,

&#x20;           trigger=CronTrigger(hour="\*"),  # 每小时执行一次

&#x20;           name="GPU监控任务"

&#x20;       )

&#x20;       self.scheduler.start()

&#x20;  &#x20;

&#x20;   def run\_monitoring(self):

&#x20;       """执行监控任务"""

&#x20;       try:

&#x20;           logging.info("开始执行GPU监控任务...")

&#x20;          &#x20;

&#x20;           # 1. 采集GPU指标数据

&#x20;           metrics\_data = self.gpu\_collector.collect\_gpu\_metrics()

&#x20;          &#x20;

&#x20;           # 2. 检查告警

&#x20;           alerts = self.alert\_manager.check\_alerts(metrics\_data)

&#x20;          &#x20;

&#x20;           # 3. 发送告警消息

&#x20;           if alerts:

&#x20;               alert\_message = self.\_format\_alert\_message(alerts)

&#x20;               self.wecom\_bot.send\_markdown\_message(alert\_message)

&#x20;               logging.warning(f"发送了 {len(alerts)} 条告警消息")

&#x20;          &#x20;

&#x20;           logging.info("GPU监控任务执行完成")

&#x20;      &#x20;

&#x20;       except Exception as e:

&#x20;           logging.error(f"监控任务执行失败: {str(e)}", exc\_info=True)

&#x20;  &#x20;

&#x20;   def \_format\_alert\_message(self, alerts):

&#x20;       """格式化告警消息"""

&#x20;       message = "# ACK集群GPU监控告警汇总\n"

&#x20;       for alert in alerts:

&#x20;           message += f"\n## {alert\['type']} (级别: {alert\['level']})\n"

&#x20;           message += f"\*\*Pod名称\*\*: {alert\['pod']}\n"

&#x20;           message += f"\*\*当前值\*\*: {alert\['value']}\n"

&#x20;           message += f"\*\*阈值\*\*: {alert\['threshold']}\n"

&#x20;           message += f"\*\*时间\*\*: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

&#x20;           message += f"\*\*描述\*\*: {alert\['message']}\n"

&#x20;       return message

\# 启动调度器

if \_\_name\_\_ == "\_\_main\_\_":

&#x20;   # 配置示例

&#x20;   config = {

&#x20;       "arms\_api\_url": "https://arms-prometheus-prod-ap-southeast-1.aliyuncs.com",

&#x20;       "arms\_access\_token": "your\_access\_token",

&#x20;       "kube\_config\_path": "/path/to/kubeconfig",

&#x20;       "wecom\_webhook\_url": "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=your\_webhook\_key",

&#x20;       "alert\_rules": {

&#x20;           "gpu\_utilization\_threshold": 80,  # GPU利用率阈值

&#x20;           "memory\_usage\_rate\_threshold": 90  # 显存占用率阈值

&#x20;       }

&#x20;   }

&#x20;  &#x20;

&#x20;   scheduler = SchedulerManager(config)

&#x20;   scheduler.start\_scheduler()

&#x20;  &#x20;

&#x20;   # 保持程序运行

&#x20;   try:

&#x20;       while True:

&#x20;           time.sleep(1)

&#x20;   except KeyboardInterrupt:

&#x20;       scheduler.scheduler.shutdown()

&#x20;       logging.info("调度器已停止")
```

### 5.5 配置管理与日志系统

良好的配置管理和日志系统对于监控程序的运维至关重要。

**配置管理实现**：使用 pydantic 库实现配置解析和验证：



```
from pydantic import BaseModel, validator

from typing import List, Dict

class AlertRuleConfig(BaseModel):

&#x20;   gpu\_utilization\_threshold: float = 80.0

&#x20;   memory\_usage\_rate\_threshold: float = 90.0

&#x20;  &#x20;

&#x20;   @validator("gpu\_utilization\_threshold")

&#x20;   def validate\_gpu\_threshold(cls, v):

&#x20;       if not (0 <= v <= 100):

&#x20;           raise ValueError("GPU利用率阈值必须在0-100之间")

&#x20;       return v

&#x20;  &#x20;

&#x20;   @validator("memory\_usage\_rate\_threshold")

&#x20;   def validate\_memory\_threshold(cls, v):

&#x20;       if not (0 <= v <= 100):

&#x20;           raise ValueError("显存占用率阈值必须在0-100之间")

&#x20;       return v

class MonitorConfig(BaseModel):

&#x20;   arms\_api\_url: str

&#x20;   arms\_access\_token: str

&#x20;   kube\_config\_path: str

&#x20;   wecom\_webhook\_url: str

&#x20;   alert\_rules: AlertRuleConfig

&#x20;   log\_level: str = "INFO"

&#x20;  &#x20;

&#x20;   @validator("log\_level")

&#x20;   def validate\_log\_level(cls, v):

&#x20;       valid\_levels = \["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

&#x20;       if v not in valid\_levels:

&#x20;           raise ValueError(f"无效的日志级别: {v}，必须是 {', '.join(valid\_levels)} 之一")

&#x20;       return v

\# 从配置文件加载配置

def load\_config(config\_path: str) -> MonitorConfig:

&#x20;   import yaml

&#x20;   with open(config\_path, "r") as f:

&#x20;       config\_data = yaml.safe\_load(f)

&#x20;   return MonitorConfig(\*\*config\_data)
```

**日志系统配置**：使用 structlog 实现结构化日志：



```
import structlog

import logging

from structlog.processors import JSONRenderer

def configure\_logging(log\_level: str = "INFO"):

&#x20;   """配置日志系统"""

&#x20;   level\_map = {

&#x20;       "DEBUG": logging.DEBUG,

&#x20;       "INFO": logging.INFO,

&#x20;       "WARNING": logging.WARNING,

&#x20;       "ERROR": logging.ERROR,

&#x20;       "CRITICAL": logging.CRITICAL

&#x20;   }

&#x20;  &#x20;

&#x20;   # 设置日志格式

&#x20;   logging.basicConfig(

&#x20;       level=level\_map\[log\_level],

&#x20;       format="%(message)s",

&#x20;       handlers=\[logging.StreamHandler()]

&#x20;   )

&#x20;  &#x20;

&#x20;   # 配置structlog

&#x20;   structlog.configure(

&#x20;       processors=\[

&#x20;           structlog.stdlib.filter\_by\_level,

&#x20;           structlog.stdlib.add\_logger\_name,

&#x20;           structlog.stdlib.add\_log\_level,

&#x20;           structlog.stdlib.PositionalArgumentsFormatter(),

&#x20;           structlog.processors.TimeStamper(fmt="iso"),

&#x20;           structlog.processors.StackInfoRenderer(),

&#x20;           structlog.processors.format\_exc\_info,

&#x20;           JSONRenderer()  # 输出JSON格式日志

&#x20;       ],

&#x20;       context\_class=dict,

&#x20;       logger\_factory=structlog.stdlib.LoggerFactory(),

&#x20;       wrapper\_class=structlog.stdlib.BoundLogger,

&#x20;       cache\_logger\_on\_first\_use=True

&#x20;   )

\# 使用示例

logger = structlog.get\_logger()

logger.info("监控程序启动", version="1.0.0", environment="production")
```

## 6. 系统部署与运维

### 6.1 容器化部署方案

将监控程序容器化部署是最佳实践，可以确保环境一致性和部署便利性。

**Dockerfile 编写**：



```
FROM python:3.10-slim

\# 设置工作目录

WORKDIR /app

\# 安装系统依赖

RUN apt-get update && apt-get install -y \\

&#x20;   python3-dev \\

&#x20;   build-essential \\

&#x20;   && rm -rf /var/lib/apt/lists/\*

\# 安装Python依赖

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

\# 复制应用代码

COPY . .

\# 设置环境变量

ENV PYTHONUNBUFFERED=1

\# 暴露端口（如果需要Web界面）

EXPOSE 8000

\# 启动命令

CMD \["python", "main.py"]
```

**requirements.txt 内容**：



```
kubernetes==26.1.0

requests==2.31.0

apscheduler==3.12.3

pydantic==2.5.3

structlog==23.6.0

python-dotenv==1.0.0
```

**使用 docker-compose 部署**：



```
version: '3'

services:

&#x20; gpu-monitor:

&#x20;   build: .

&#x20;   container\_name: gpu-monitor

&#x20;   restart: always

&#x20;   environment:

&#x20;     - ARM\_API\_URL=https://arms-prometheus-prod-ap-southeast-1.aliyuncs.com

&#x20;     - ARM\_ACCESS\_TOKEN=your\_access\_token

&#x20;     - KUBE\_CONFIG\_PATH=/app/kubeconfig

&#x20;     - WECOM\_WEBHOOK\_URL=https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=your\_webhook\_key

&#x20;     - LOG\_LEVEL=INFO

&#x20;   volumes:

&#x20;     - ./config:/app/config

&#x20;     - ./logs:/app/logs

&#x20;     - \~/.kube/config:/app/kubeconfig
```

**Kubernetes 部署配置**：



```
apiVersion: apps/v1

kind: Deployment

metadata:

&#x20; name: gpu-monitor

&#x20; namespace: monitoring

&#x20; labels:

&#x20;   app: gpu-monitor

spec:

&#x20; replicas: 1

&#x20; selector:

&#x20;   matchLabels:

&#x20;     app: gpu-monitor

&#x20; template:

&#x20;   metadata:

&#x20;     labels:

&#x20;       app: gpu-monitor

&#x20;   spec:

&#x20;     serviceAccountName: gpu-monitor-sa

&#x20;     containers:

&#x20;     - name: gpu-monitor

&#x20;       image: registry.example.com/gpu-monitor:v1.0.0

&#x20;       imagePullPolicy: Always

&#x20;       env:

&#x20;       - name: ARM\_API\_URL

&#x20;         value: "https://arms-prometheus-prod-ap-southeast-1.aliyuncs.com"

&#x20;       - name: ARM\_ACCESS\_TOKEN

&#x20;         valueFrom:

&#x20;           secretKeyRef:

&#x20;             name: arms-secret

&#x20;             key: access\_token

&#x20;       - name: WECOM\_WEBHOOK\_URL

&#x20;         valueFrom:

&#x20;           secretKeyRef:

&#x20;             name: wecom-secret

&#x20;             key: webhook\_url

&#x20;       - name: LOG\_LEVEL

&#x20;         value: "INFO"

&#x20;       volumeMounts:

&#x20;       - name: config-volume

&#x20;         mountPath: /app/config

&#x20;       - name: logs-volume

&#x20;         mountPath: /app/logs

&#x20;     volumes:

&#x20;     - name: config-volume

&#x20;       configMap:

&#x20;         name: gpu-monitor-config

&#x20;     - name: logs-volume

&#x20;       emptyDir: {}

\---

apiVersion: v1

kind: ServiceAccount

metadata:

&#x20; name: gpu-monitor-sa

&#x20; namespace: monitoring

\---

apiVersion: v1

kind: Secret

metadata:

&#x20; name: arms-secret

&#x20; namespace: monitoring

type: Opaque

data:

&#x20; access\_token: \<base64 encoded access token>

\---

apiVersion: v1

kind: Secret

metadata:

&#x20; name: wecom-secret

&#x20; namespace: monitoring

type: Opaque

data:

&#x20; webhook\_url: \<base64 encoded webhook URL>
```

### 6.2 高可用性与故障恢复

监控程序的高可用性对于及时发现 GPU 资源问题至关重要。

**多副本部署**：在 Kubernetes 中部署多个副本，通过 Deployment 的 replicas 字段设置，建议设置为 2-3 个副本。这样即使某个 Pod 出现故障，其他副本可以继续提供监控服务。

**健康检查配置**：为容器配置 livenessProbe 和 readinessProbe，确保容器状态正常：



```
livenessProbe:

&#x20; httpGet:

&#x20;   path: /healthz

&#x20;   port: 8000

&#x20; initialDelaySeconds: 30

&#x20; periodSeconds: 10

&#x20; timeoutSeconds: 5

&#x20; failureThreshold: 3

readinessProbe:

&#x20; httpGet:

&#x20;   path: /readyz

&#x20;   port: 8000

&#x20; initialDelaySeconds: 5

&#x20; periodSeconds: 10

&#x20; timeoutSeconds: 5
```

**数据持久化**：监控程序产生的日志和临时数据需要持久化存储。可以使用 Kubernetes 的 PersistentVolumeClaim 来挂载持久化存储卷：



```
volumeMounts:

\- name: logs-volume

&#x20; mountPath: /app/logs

volumes:

\- name: logs-volume

&#x20; persistentVolumeClaim:

&#x20;   claimName: gpu-monitor-logs
```

**故障恢复机制**：



1. **自动重启**：通过设置 Pod 的 restartPolicy 为 Always，确保容器异常退出时自动重启

2. **备份配置**：定期备份配置文件和密钥，防止配置丢失

3. **告警通知**：为监控程序本身配置健康监控，当程序异常时发送告警通知

4. **版本控制**：使用 Git 进行代码版本控制，便于回滚和问题排查

### 6.3 监控与告警系统自身运维

监控系统本身也需要被监控，确保其正常运行。

**系统监控指标**：



1. 程序运行状态（是否正常运行）

2. 内存使用情况

3. CPU 使用率

4. 网络连接状态（特别是与 ARMS 和企业微信的连接）

5. 数据采集成功率

6. 告警发送成功率

**自定义健康检查端点**：



```
from fastapi import FastAPI, status

from fastapi.responses import JSONResponse

app = FastAPI()

@app.get("/healthz", status\_code=status.HTTP\_200\_OK)

def health\_check():

&#x20;   """健康检查端点"""

&#x20;   status\_info = {

&#x20;       "status": "ok",

&#x20;       "message": "GPU监控服务运行正常",

&#x20;       "timestamp": datetime.now().isoformat()

&#x20;   }

&#x20;   return JSONResponse(content=status\_info)

@app.get("/readyz", status\_code=status.HTTP\_200\_OK)

def readiness\_check():

&#x20;   """就绪检查端点"""

&#x20;   # 检查必要的依赖服务是否可达

&#x20;   arms\_reachable = check\_arms\_connection()

&#x20;   wecom\_reachable = check\_wecom\_connection()

&#x20;  &#x20;

&#x20;   status = "ok" if arms\_reachable and wecom\_reachable else "not ready"

&#x20;   message = "服务已就绪" if status == "ok" else "依赖服务不可达"

&#x20;  &#x20;

&#x20;   status\_info = {

&#x20;       "status": status,

&#x20;       "message": message,

&#x20;       "dependencies": {

&#x20;           "arms": "reachable" if arms\_reachable else "unreachable",

&#x20;           "wecom": "reachable" if wecom\_reachable else "unreachable"

&#x20;       },

&#x20;       "timestamp": datetime.now().isoformat()

&#x20;   }

&#x20;  &#x20;

&#x20;   if status != "ok":

&#x20;       return JSONResponse(content=status\_info, status\_code=status.HTTP\_503\_SERVICE\_UNAVAILABLE)

&#x20;   return JSONResponse(content=status\_info)
```

**日志监控与分析**：



1. 将监控程序的日志接入 ELK 或其他日志分析平台

2. 设置日志告警规则，如错误日志频率过高时触发告警

3. 定期分析日志，识别潜在问题和性能瓶颈

4. 实现日志轮转，避免日志文件过大

**性能优化建议**：



1. 使用连接池复用网络连接，减少建立连接的开销

2. 缓存常用的配置和元数据，避免重复查询

3. 使用异步处理提高并发性能

4. 合理设置超时时间，避免长时间阻塞

5. 实现限流机制，避免对 ARMS API 造成过大压力

## 7. 总结与最佳实践

通过本指南的详细介绍，我们完成了阿里云 ACK 集群 GPU 监控工具的完整方案设计。该监控系统能够实现对带有特定 Label 和注解的 GPU 工作负载进行小时级监控，并通过企业微信 webhook 及时推送告警信息。

**核心技术要点总结**：



1. **数据采集架构**：采用 ACK 默认的 GPU 监控体系，通过 GPU Exporter 采集 DCGM 标准指标和阿里云自定义指标，数据通过 Prometheus 采集并存储在 ARMS 平台，支持通过 ARMS API 进行查询[(191)](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/observability-best-practices)。

2. **精准过滤机制**：通过 Label 选择器 app: pytorchjob 和 job-name: dolphin 实现工作负载的精确识别，通过注解[arena.kubeflow.org/username](https://arena.kubeflow.org/username)实现用户身份关联，确保监控数据的准确性和可追溯性[(2)](http://m.toutiao.com/group/6321548847668396289/?upstream_biz=doubao)。

3. **权限管理体系**：采用 RAM+RBAC 的双重权限控制，通过创建专门的 Service Account 和配置细粒度的 RBAC 规则，实现监控程序的安全访问。在多租户 Kubeflow 环境中，通过 Namespace 和注解实现用户级资源隔离。

4. **技术实现方案**：使用 Python 开发，采用模块化架构，通过 APScheduler 实现定时任务调度，通过企业微信 webhook 实现告警推送。容器化部署确保了环境一致性和部署便利性。

5. **运维保障措施**：通过多副本部署、健康检查、数据持久化、故障恢复机制等措施，确保监控系统的高可用性。同时建立了完善的自身监控体系，实现了监控的监控。

**最佳实践建议**：



1. **监控指标优化**：

* 根据实际业务需求调整告警阈值，避免误告警

* 定期分析监控数据，识别资源使用模式和优化空间

* 保留足够长的历史数据用于趋势分析和容量规划

1. **性能与成本平衡**：

* 合理设置数据采集频率，在数据精度和系统开销间找到平衡

* 利用 ARMS 的存储周期配置，根据业务需求选择合适的存储时长

* 实现数据压缩和聚合，减少存储成本

1. **安全合规要求**：

* 敏感信息（如 AccessKey、Webhook URL）必须使用 Kubernetes Secret 管理

* 定期轮换密钥，提高系统安全性

* 配置合理的网络策略，限制不必要的网络访问

1. **可扩展性设计**：

* 预留扩展接口，支持未来新增监控指标

* 设计灵活的告警规则配置，支持不同场景的定制需求

* 实现多集群监控能力，支持统一管理多个 ACK 集群

1. **文档与知识管理**：

* 编写详细的操作手册和故障处理指南

* 建立知识库，记录常见问题和解决方案

* 定期进行系统运维培训，提高团队技术水平

通过实施本方案，可以有效监控 ACK 集群中 GPU 资源的使用情况，及时发现和处理资源瓶颈，优化资源配置，提高 GPU 利用率，为企业的 AI 工作负载提供稳定可靠的基础设施保障。同时，通过完善的告警机制和可视化展示，大大提升了运维效率，降低了人工成本。

**参考资料&#x20;**

\[1] 从系统监控到业务洞察:ARMS 自定义指标采集功能全解析\_阿里云云原生[ http://m.toutiao.com/group/7579920866576286249/?upstream\_biz=doubao](http://m.toutiao.com/group/7579920866576286249/?upstream_biz=doubao)

\[2] 阿里云中间件产品ARMS公测 实时监控“一站式”解决\_阿里云[ http://m.toutiao.com/group/6321548847668396289/?upstream\_biz=doubao](http://m.toutiao.com/group/6321548847668396289/?upstream_biz=doubao)

\[3] 异构 AI 算力管理困局如何破?国内 Top5 云厂商核心能力全景对比\_品科技生活[ http://m.toutiao.com/group/7588085037103366719/?upstream\_biz=doubao](http://m.toutiao.com/group/7588085037103366719/?upstream_biz=doubao)

\[4] 应对突发流量，如何快速为自建 K8s 添加云上弹性能力\_阿里云云原生[ http://m.toutiao.com/group/7257052166077071883/?upstream\_biz=doubao](http://m.toutiao.com/group/7257052166077071883/?upstream_biz=doubao)

\[5] 阿里云采用以太网取代英伟达NVlink，实现1.5万个GPU互连!\_EETOP半导体社区[ http://m.toutiao.com/group/7386122068653244937/?upstream\_biz=doubao](http://m.toutiao.com/group/7386122068653244937/?upstream_biz=doubao)

\[6] 阿里云渠道商:新手阿里云GPU服务器必做的五项基础配置有哪些?\_国际云优惠[ http://m.toutiao.com/group/7576557547977540122/?upstream\_biz=doubao](http://m.toutiao.com/group/7576557547977540122/?upstream_biz=doubao)

\[7] 边缘GPU节点的可观测原理和最佳实践-阿里云开发者社区[ https://developer.aliyun.com/article/1652818](https://developer.aliyun.com/article/1652818)

\[8] 接入与配置阿里云Prometheus监控-容器服务 Kubernetes 版 ACK-阿里云[ https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/use-alibaba-cloud-prometheus-service-to-monitor-an-ack-cluster](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/use-alibaba-cloud-prometheus-service-to-monitor-an-ack-cluster)

\[9] arms容器服务Kubernetes版pod-阿里云[ https://www.aliyun.com/sswb/1657526\_1.html](https://www.aliyun.com/sswb/1657526_1.html)

\[10] :Best practices for monitoring GPU resources in ACK Edge clusters[ https://www.alibabacloud.com/help/en/ack/ack-edge/use-cases/best-practices-for-monitoring-gpu-resources-in-ack-edge-clusters](https://www.alibabacloud.com/help/en/ack/ack-edge/use-cases/best-practices-for-monitoring-gpu-resources-in-ack-edge-clusters)

\[11] 使用Prometheus开启并查看ACK集群GPU监控-容器服务 Kubernetes 版 ACK-阿里云[ https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/enable-gpu-monitoring-for-a-cluster](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/enable-gpu-monitoring-for-a-cluster)

\[12] 可观测性FAQ-容器服务 Kubernetes 版 ACK(ACK)-阿里云帮助中心[ https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/observability-faqs/](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/observability-faqs/)

\[13] 容器场景可观测最佳实践\_容器服务 Kubernetes 版 ACK(ACK)-阿里云帮助中心[ https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/observability-best-practices](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/observability-best-practices)

\[14] GPU监控2.0指标详解含DCGM与自定义指标-容器服务 Kubernetes 版 ACK-阿里云[ https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/introduction-to-metrics](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/introduction-to-metrics)

\[15] GPU监控面板各维度指标详解-容器服务 Kubernetes 版 ACK-阿里云[ https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/panels](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/panels)

\[16] GPU Pod监控指标采集及Grafana仪表盘搭建\_监控\_最佳实践\_云容器引擎 CCE-华为云[ https://support.huaweicloud.com/intl/zh-cn/bestpractice-cce/cce\_bestpractice\_10061.html](https://support.huaweicloud.com/intl/zh-cn/bestpractice-cce/cce_bestpractice_10061.html)

\[17] 可观测监控Prometheus版支持的容器集群基础指标有哪些-云监控(CMS)-阿里云帮助中心[ https://help.aliyun.com/zh/cms/cloudmonitor-1-0/developer-reference/container-cluster-metrics](https://help.aliyun.com/zh/cms/cloudmonitor-1-0/developer-reference/container-cluster-metrics)

\[18] 监控GPU云服务器-阿里云[ https://www.aliyun.com/sswb/1159657\_1.html](https://www.aliyun.com/sswb/1159657_1.html)

\[19] Container Compute Service:Introduction to metrics of ACS GPU-accelerated pods[ https://www.alibabacloud.com/help/en/cs/user-guide/acs-gpu-pod-monitoring-indicators](https://www.alibabacloud.com/help/en/cs/user-guide/acs-gpu-pod-monitoring-indicators)

\[20] 【新功能发布】支持GPU计算型实例的GPU相关指标监控与报警-CSDN博客[ https://blog.csdn.net/weixin\_33806509/article/details/89686811](https://blog.csdn.net/weixin_33806509/article/details/89686811)

\[21] 使用Prometheus监控GPU指标实现容器弹性伸缩-容器服务Kubernetes版ACK-阿里云[ https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/enable-auto-scaling-based-on-gpu-metrics](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/enable-auto-scaling-based-on-gpu-metrics)

\[22] 云服务帮助中心[ https://doc.hcs.huawei.com/zh-cn/usermanual/cce/cce\_10\_0759.html](https://doc.hcs.huawei.com/zh-cn/usermanual/cce/cce_10_0759.html)

\[23] GPU使用率和GPU显存使用率的区别是什么-CSDN博客[ https://blog.csdn.net/weixin\_44544263/article/details/155096251](https://blog.csdn.net/weixin_44544263/article/details/155096251)

\[24] 768MiB / 6144MiB 是这样 - CSDN文库[ https://wenku.csdn.net/answer/7sij51gbvp](https://wenku.csdn.net/answer/7sij51gbvp)

\[25] AI时代运维工程师的GPU知识与监控指标指南[ http://www.360doc.com/content/25/0330/10/29585900\_1150172101.shtml](http://www.360doc.com/content/25/0330/10/29585900_1150172101.shtml)

\[26] gpu\_utils和gpu\_memory是什么指标 - CSDN文库[ https://wenku.csdn.net/answer/6jfp8yhe5m](https://wenku.csdn.net/answer/6jfp8yhe5m)

\[27] 使用Prometheus监控ACK Edge集群GPU资源-容器服务 Kubernetes 版 ACK-阿里云[ https://help.aliyun.com/zh/ack/ack-edge/use-cases/best-practices-for-monitoring-gpu-resources-in-ack-edge-clusters](https://help.aliyun.com/zh/ack/ack-edge/use-cases/best-practices-for-monitoring-gpu-resources-in-ack-edge-clusters)

\[28] 使用Prometheus监控GPU指标实现HPA弹性伸缩-容器服务Kubernetes版ACK-阿里云[ https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/enable-auto-scaling-based-on-gpu-metrics-1](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/enable-auto-scaling-based-on-gpu-metrics-1)

\[29] 边缘GPU节点的可观测原理和最佳实践-阿里云开发者社区[ https://developer.aliyun.com/article/1652818](https://developer.aliyun.com/article/1652818)

\[30] 【产品变更】可观测监控 Prometheus 版支持的容器服务集群基础指标变更通知-应用实时监控服务-阿里云[ https://help.aliyun.com/zh/arms/product-overview/product-announcement-notification-of-changes-to-basic-container-service-cluster-metrics-supported-by-the-observable-monitoring-prometheus-version](https://help.aliyun.com/zh/arms/product-overview/product-announcement-notification-of-changes-to-basic-container-service-cluster-metrics-supported-by-the-observable-monitoring-prometheus-version)

\[31] Arm streamline performance Advisor (Arm性能顾问使用指南)-CSDN博客[ https://blog.csdn.net/sbwshishi/article/details/125979066](https://blog.csdn.net/sbwshishi/article/details/125979066)

\[32] GPU metrics[ https://learn.arm.com/learning-paths/smartphones-and-mobile/unity\_packages/mali\_metrics](https://learn.arm.com/learning-paths/smartphones-and-mobile/unity_packages/mali_metrics)

\[33] 使用云监控和ARMS为分布式训练任务配置监控与报警-人工智能平台 PAI-阿里云[ https://help.aliyun.com/zh/pai/user-guide/monitoring-and-alerting](https://help.aliyun.com/zh/pai/user-guide/monitoring-and-alerting)

\[34] 通过控制台和API使用PromQL查询Prometheus数据-容器服务 Kubernetes 版 ACK-阿里云[ https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/use-promql-to-query-prometheus-monitoring-data](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/use-promql-to-query-prometheus-monitoring-data)

\[35] 使用 API 和 PromQL 查询 Prometheus 指标 - Azure Monitor | Azure Docs[ https://docs.azure.cn/zh-cn/azure-monitor/metrics/prometheus-api-promql](https://docs.azure.cn/zh-cn/azure-monitor/metrics/prometheus-api-promql)

\[36] 全部API接口列表与调用参考-应用实时监控服务-阿里云-应用实时监控服务(ARMS)-阿里云帮助中心[ https://help.aliyun.com/zh/arms/prometheus-monitoring/api-arms-2019-08-08-overview?scm=20140722.H\_441908.\_.ID\_441908-OR\_rec-V\_1](https://help.aliyun.com/zh/arms/prometheus-monitoring/api-arms-2019-08-08-overview?scm=20140722.H_441908._.ID_441908-OR_rec-V_1)

\[37] HTTP API[ https://prometheus.io/docs/prometheus/1.8/querying/api/](https://prometheus.io/docs/prometheus/1.8/querying/api/)

\[38] Prometheus API 使用介绍|收藏-CSDN博客[ https://blog.csdn.net/qq\_56271699/article/details/135168421](https://blog.csdn.net/qq_56271699/article/details/135168421)

\[39] Query Prometheus metrics using the API and PromQL[ https://docs.azure.cn/en-us/azure-monitor/metrics/prometheus-api-promql](https://docs.azure.cn/en-us/azure-monitor/metrics/prometheus-api-promql)

\[40] prometheus API\_prometheus api接口-CSDN博客[ https://blog.csdn.net/liao\_\_ran/article/details/128831775](https://blog.csdn.net/liao__ran/article/details/128831775)

\[41] 边缘GPU节点的可观测原理和最佳实践-阿里云开发者社区[ https://developer.aliyun.com/article/1652818](https://developer.aliyun.com/article/1652818)

\[42] 基于阿里云构建AI-native应用全栈可观测体系-开发者社区-阿里云[ https://developer.aliyun.com/article/1611462](https://developer.aliyun.com/article/1611462)

\[43] 查看不同GPU申请方式的监控大盘及数据解读-容器服务 Kubernetes 版 ACK-阿里云[ https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/best-practices-for-monitoring-gpu-resources](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/best-practices-for-monitoring-gpu-resources)

\[44] :Best practices for monitoring GPU resources in ACK Edge clusters[ https://www.alibabacloud.com/help/en/ack/ack-edge/use-cases/best-practices-for-monitoring-gpu-resources-in-ack-edge-clusters](https://www.alibabacloud.com/help/en/ack/ack-edge/use-cases/best-practices-for-monitoring-gpu-resources-in-ack-edge-clusters)

\[45] 接入与配置阿里云Prometheus监控-容器服务 Kubernetes 版 ACK-阿里云[ https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/use-alibaba-cloud-prometheus-service-to-monitor-an-ack-cluster](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/use-alibaba-cloud-prometheus-service-to-monitor-an-ack-cluster)

\[46] GPUメトリックに基づく自動スケーリングの有効化 - Container Service for Kubernetes - Alibaba Cloud ドキュメントセンター[ https://www.alibabacloud.com/help/ja/ack/ack-managed-and-ack-dedicated/user-guide/enable-auto-scaling-based-on-gpu-metrics](https://www.alibabacloud.com/help/ja/ack/ack-managed-and-ack-dedicated/user-guide/enable-auto-scaling-based-on-gpu-metrics)

\[47] 容器集群各组件基础监控指标-应用实时监控服务-阿里云[ https://help.aliyun.com/zh/arms/prometheus-monitoring/container-cluster-metrics](https://help.aliyun.com/zh/arms/prometheus-monitoring/container-cluster-metrics)

\[48] 使用Prometheus开启并查看ACK集群GPU监控-容器服务 Kubernetes 版 ACK-阿里云[ https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/enable-gpu-monitoring-for-a-cluster](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/enable-gpu-monitoring-for-a-cluster)

\[49] 接入阿里云Prometheus监控ACK Edge集群并配置告警-容器服务Kubernetes版ACK-阿里云[ https://help.aliyun.com/zh/ack/ack-edge/user-guide/use-prometheus-service-monitoring-to-monitor-ack-edge-clusters](https://help.aliyun.com/zh/ack/ack-edge/user-guide/use-prometheus-service-monitoring-to-monitor-ack-edge-clusters)

\[50] 使用Prometheus监控GPU指标实现容器弹性伸缩-容器服务Kubernetes版ACK-阿里云[ https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/enable-auto-scaling-based-on-gpu-metrics](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/enable-auto-scaling-based-on-gpu-metrics)

\[51] Application Real-Time Monitoring Service:Automatically install an ARMS agent for a Java application deployed in ACK[ https://www.alibabacloud.com/help/en/arms/application-monitoring/user-guide/install-arms-agent-for-java-applications-deployed-in-ack](https://www.alibabacloud.com/help/en/arms/application-monitoring/user-guide/install-arms-agent-for-java-applications-deployed-in-ack)

\[52] Container Service for Kubernetes:Application monitoring overview[ https://www.alibabacloud.com/help/en/ack/ack-managed-and-ack-dedicated/user-guide/application-monitoring/](https://www.alibabacloud.com/help/en/ack/ack-managed-and-ack-dedicated/user-guide/application-monitoring/)

\[53] 阿里云云产品访问ACK集群的RBAC权限策略-容器服务 Kubernetes 版 ACK-阿里云[ https://help.aliyun.com:443/zh/ack/ack-managed-and-ack-dedicated/user-guide/permissions-for-other-cloud-products-to-access-ack-clusters](https://help.aliyun.com:443/zh/ack/ack-managed-and-ack-dedicated/user-guide/permissions-for-other-cloud-products-to-access-ack-clusters)

\[54] 使用Prometheus监控ACK Edge集群GPU资源-容器服务 Kubernetes 版 ACK-阿里云[ https://help.aliyun.com/zh/ack/ack-edge/use-cases/best-practices-for-monitoring-gpu-resources-in-ack-edge-clusters](https://help.aliyun.com/zh/ack/ack-edge/use-cases/best-practices-for-monitoring-gpu-resources-in-ack-edge-clusters)

\[55] 使用Prometheus监控GPU指标实现容器弹性伸缩-容器服务Kubernetes版ACK-阿里云[ https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/enable-auto-scaling-based-on-gpu-metrics](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/enable-auto-scaling-based-on-gpu-metrics)

\[56] 配置与管理ack-nvidia-device-plugin组件-容器服务 Kubernetes 版 ACK-阿里云[ http://help.aliyun.com:443/zh/ack/ack-managed-and-ack-dedicated/user-guide/gpu-device-plugin-related-operations](http://help.aliyun.com:443/zh/ack/ack-managed-and-ack-dedicated/user-guide/gpu-device-plugin-related-operations)

\[57] 配置AHPA实现基于GPU指标的弹性伸缩-容器服务 Kubernetes 版 ACK-阿里云[ https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/use-ahpa-to-perform-predictive-scaling-based-on-gpu-metrics](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/use-ahpa-to-perform-predictive-scaling-based-on-gpu-metrics)

\[58] Monitor GPU metrics from NVIDIA DCGM exporter with Azure Managed Prometheus and Managed Grafana on Azure Kubernetes Service (AKS)[ https://learn.microsoft.com/uk-ua/azure/aks/monitor-gpu-metrics](https://learn.microsoft.com/uk-ua/azure/aks/monitor-gpu-metrics)

\[59] Dimensionamento automático de cargas de trabalho de GPU no AKS usando métricas DCGM e KEDA[ https://learn.microsoft.com/pt-pt/azure/aks/autoscale-gpu-workloads-with-keda](https://learn.microsoft.com/pt-pt/azure/aks/autoscale-gpu-workloads-with-keda)

\[60] NVIDIA GPU Operator中DCGM Exporter服务的流量策略优化解析 - GitCode博客[ https://blog.gitcode.com/6ee3b2ac10730ee63ecbdb0d43f7bc4a.html](https://blog.gitcode.com/6ee3b2ac10730ee63ecbdb0d43f7bc4a.html)

\[61] 腾讯云可观测平台 TKE GPU Exporter 接入\_腾讯云[ https://cloud.tencent.cn/document/product/248/108600](https://cloud.tencent.cn/document/product/248/108600)

\[62] ack-ai-installer组件介绍与变更说明-容器服务 Kubernetes 版 ACK-阿里云[ https://help.aliyun.com/zh/ack/cloud-native-ai-suite/product-overview/ack-ai-installer](https://help.aliyun.com/zh/ack/cloud-native-ai-suite/product-overview/ack-ai-installer)

\[63] Container Service for Kubernetes:GPU sharing overview[ https://www.alibabacloud.com/help/en/ack/ack-managed-and-ack-dedicated/user-guide/cgpu-overview/](https://www.alibabacloud.com/help/en/ack/ack-managed-and-ack-dedicated/user-guide/cgpu-overview/)

\[64] Container Service for Kubernetes:Enable NUMA topology-aware scheduling[ https://www.alibabacloud.com/help/en/ack/ack-managed-and-ack-dedicated/user-guide/enable-numa-topology-aware-scheduling](https://www.alibabacloud.com/help/en/ack/ack-managed-and-ack-dedicated/user-guide/enable-numa-topology-aware-scheduling)

\[65] NVIDIA Kubernetes Device Plugin[ https://catalog.ngc.nvidia.com/orgs/nvidia/containers/k8s-device-plugin?ncid=so-twit-170613](https://catalog.ngc.nvidia.com/orgs/nvidia/containers/k8s-device-plugin?ncid=so-twit-170613)

\[66] Container Service for Kubernetes:Add GPU-accelerated nodes to a cluster[ https://www.alibabacloud.com/help/en/ack/ack-managed-and-ack-dedicated/user-guide/add-gpu-accelerated-nodes-to-a-cluster](https://www.alibabacloud.com/help/en/ack/ack-managed-and-ack-dedicated/user-guide/add-gpu-accelerated-nodes-to-a-cluster)

\[67] Container Service for Kubernetes:GPU FAQ[ https://www.alibabacloud.com/help/en/ack/ack-managed-and-ack-dedicated/user-guide/gpu-faq](https://www.alibabacloud.com/help/en/ack/ack-managed-and-ack-dedicated/user-guide/gpu-faq)

\[68] Container Service for Kubernetes:GPU Device Plugin-related operations[ https://www.alibabacloud.com/help/en/ack/ack-managed-and-ack-dedicated/user-guide/gpu-device-plugin-related-operations](https://www.alibabacloud.com/help/en/ack/ack-managed-and-ack-dedicated/user-guide/gpu-device-plugin-related-operations)

\[69] 阿里云ACK托管集群Pro版共享GPU调度操作指南-阿里云开发者社区[ https://developer.aliyun.com/article/1685728](https://developer.aliyun.com/article/1685728)

\[70] 多个容器共享GPU设备调度隔离-共享GPU调度-容器服务 Kubernetes 版 ACK-阿里云[ https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/cgpu-overview](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/cgpu-overview)

\[71] Container Service for Kubernetes:GPU sharing overview[ https://www.alibabacloud.com/help/en/ack/ack-managed-and-ack-dedicated/user-guide/cgpu-overview/](https://www.alibabacloud.com/help/en/ack/ack-managed-and-ack-dedicated/user-guide/cgpu-overview/)

\[72] Container Service for Kubernetes:Overview of ACK clusters for heterogeneous computing[ https://www.alibabacloud.com/help/en/ack/ack-managed-and-ack-dedicated/user-guide/overview-5/](https://www.alibabacloud.com/help/en/ack/ack-managed-and-ack-dedicated/user-guide/overview-5/)

\[73] GPU共享调度-智算套件-用户指南-AI负载调度 - 天翼云[ https://www.ctyun.cn/document/11083692/11084835](https://www.ctyun.cn/document/11083692/11084835)

\[74] Improvements: Cluster Autoscaling with GPU-sharing Pods & Support for Scheduling Gates #125[ https://github.com/NVIDIA/KAI-Scheduler/discussions/125](https://github.com/NVIDIA/KAI-Scheduler/discussions/125)

\[75] kubernetes GPU云服务器-阿里云[ https://www.aliyun.com/sswb/1182928\_1.html](https://www.aliyun.com/sswb/1182928_1.html)

\[76] ack-ai-installer组件介绍与变更说明-容器服务 Kubernetes 版 ACK-阿里云[ http://help.aliyun.com:443/zh/ack/cloud-native-ai-suite/product-overview/ack-ai-installer](http://help.aliyun.com:443/zh/ack/cloud-native-ai-suite/product-overview/ack-ai-installer)

\[77] 查看不同GPU申请方式的监控大盘及数据解读-容器服务 Kubernetes 版 ACK-阿里云[ https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/best-practices-for-monitoring-gpu-resources](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/best-practices-for-monitoring-gpu-resources)

\[78] 如何在ACK灵骏托管版集群中使用共享GPU调度-容器服务 Kubernetes 版 ACK(ACK)-阿里云帮助中心[ https://help.aliyun.com/zh/ack/ack-lingjun-managed-clusters/user-guide/use-shared-gpu-scheduling#ee7ef23437dwp](https://help.aliyun.com/zh/ack/ack-lingjun-managed-clusters/user-guide/use-shared-gpu-scheduling#ee7ef23437dwp)

\[79] from device plugin to cdi 业务分类: 硬件拓扑感知 硬件类型及特性注册 硬件分配 硬件资源回收 - 掘金[ https://juejin.cn/post/7543911246166376491](https://juejin.cn/post/7543911246166376491)

\[80] Fork of the NVIDIA device plugin for Kubernetes with support for shared GPUs by declaring GPUs multiple times[ https://github.com/Deepomatic/shared-gpu-nvidia-k8s-device-plugin](https://github.com/Deepomatic/shared-gpu-nvidia-k8s-device-plugin)

\[81] 基于GPU监控指标配置工作负载弹性伸缩\_GPU弹性伸缩\_GPU调度\_调度\_用户指南\_云容器引擎 CCE-华为云[ https://support.huaweicloud.com/intl/zh-cn/usermanual-cce/cce\_10\_0844.html](https://support.huaweicloud.com/intl/zh-cn/usermanual-cce/cce_10_0844.html)

\[82] 一文搞懂 GPU 共享方案: NVIDIA Time Slicing-CSDN博客[ https://blog.csdn.net/weixin\_42084779/article/details/148954635](https://blog.csdn.net/weixin_42084779/article/details/148954635)

\[83] 通过Prometheus对GPU集群进行监控以及搭建(小型集群)-CSDN博客[ https://blog.csdn.net/weixin\_42795092/article/details/154662359](https://blog.csdn.net/weixin_42795092/article/details/154662359)

\[84] 【Prometheus监控 运维必备】七、Prometheus 性能优化与高可用\_prometheus高可用-CSDN博客[ https://blog.csdn.net/qq\_58611691/article/details/147148909](https://blog.csdn.net/qq_58611691/article/details/147148909)

\[85] Gegevens bewaken en vastleggen[ https://learn.microsoft.com/nl-nl/azure/aks/hybrid/aks-monitor-logging](https://learn.microsoft.com/nl-nl/azure/aks/hybrid/aks-monitor-logging)

\[86] ROCm系统监控解决方案:Prometheus+Grafana实时性能指标采集-CSDN博客[ https://blog.csdn.net/gitblog\_00430/article/details/152152018](https://blog.csdn.net/gitblog_00430/article/details/152152018)

\[87] 从入门到offer:监控生态面试通关秘籍[ https://juejin.cn/post/7474554863448604722](https://juejin.cn/post/7474554863448604722)

\[88] Azure Monitor 中的默认 Prometheus 指标配置 - Azure Monitor | Azure Docs[ https://docs.azure.cn/zh-CN/azure-monitor/containers/prometheus-metrics-scrape-default](https://docs.azure.cn/zh-CN/azure-monitor/containers/prometheus-metrics-scrape-default)

\[89] 怎么定时导出到Prometheus - CSDN文库[ https://wenku.csdn.net/answer/26zc1e3dce](https://wenku.csdn.net/answer/26zc1e3dce)

\[90] 计费与成本管理FAQ-应用实时监控服务-阿里云[ https://help.aliyun.com/zh/arms/application-monitoring/product-overview/billing-faq](https://help.aliyun.com/zh/arms/application-monitoring/product-overview/billing-faq)

\[91] Azure Monitor 中的指标 - Azure Monitor | Azure Docs[ https://docs.azure.cn/zh-cn/azure-monitor/essentials/data-platform-metrics](https://docs.azure.cn/zh-cn/azure-monitor/essentials/data-platform-metrics)

\[92] 监控数据存活设置 - LarkVR帮助手册3.2.23+ - 平行云手册[ https://docs.pingxingyun.com/doc/1426/](https://docs.pingxingyun.com/doc/1426/)

\[93] NovaGPU Data Retention FAQ[ https://www.ipserverone.info/faq/faq-how-long-is-data-retained-in-a-novagpu-instance-if-unused/](https://www.ipserverone.info/faq/faq-how-long-is-data-retained-in-a-novagpu-instance-if-unused/)

\[94] 请问arms在阿里云的储存时长只有30天时效，我们想把数据在我们数据库备份一份，这个可以操作吗?\_问答-阿里云开发者社区[ https://developer.aliyun.com/ask/466008](https://developer.aliyun.com/ask/466008)

\[95] 突破性能瓶颈:Triton Inference Server时序数据管理与监控优化指南-CSDN博客[ https://blog.csdn.net/gitblog\_00710/article/details/151347643](https://blog.csdn.net/gitblog_00710/article/details/151347643)

\[96] ARM机器使用netdata监控\_netdata arm-CSDN博客[ https://blog.csdn.net/shunnianlv/article/details/124434194](https://blog.csdn.net/shunnianlv/article/details/124434194)

\[97] 阿里云代理商:阿里云产品有哪些监控接口可用?\_石榴云[ http://m.toutiao.com/group/7532798675756876323/?upstream\_biz=doubao](http://m.toutiao.com/group/7532798675756876323/?upstream_biz=doubao)

\[98] 免改造架构:借助KMS与ACK Secret实现数据库密码的安全托管\_新钛云服[ http://m.toutiao.com/group/7576847627103289908/?upstream\_biz=doubao](http://m.toutiao.com/group/7576847627103289908/?upstream_biz=doubao)

\[99] 简明教程:利用 Apifox 设置 OAuth 2.0 并获取访问令牌\_Apifox[ http://m.toutiao.com/group/7358314777452446217/?upstream\_biz=doubao](http://m.toutiao.com/group/7358314777452446217/?upstream_biz=doubao)

\[100] 阿里云渠道商:新手怎么使用阿里云控制台常用功能?\_国际云包打听[ http://m.toutiao.com/group/7577324592776233498/?upstream\_biz=doubao](http://m.toutiao.com/group/7577324592776233498/?upstream_biz=doubao)

\[101] 清理祖传 AK 不怕炸锅:基于 UModel 的云监控 2.0 身份凭证观测实践\_阿里云云原生[ http://m.toutiao.com/group/7567217691589607976/?upstream\_biz=doubao](http://m.toutiao.com/group/7567217691589607976/?upstream_biz=doubao)

\[102] golang对接阿里云私有Bucket上传图片、授权访问图片\_海椰人[ http://m.toutiao.com/group/7082565212247261737/?upstream\_biz=doubao](http://m.toutiao.com/group/7082565212247261737/?upstream_biz=doubao)

\[103] EduSoho阿里云对象存储\_摄影狮少宇[ http://m.toutiao.com/group/6838096319903433224/?upstream\_biz=doubao](http://m.toutiao.com/group/6838096319903433224/?upstream_biz=doubao)

\[104] 权限问题与授权配置FAQ-容器服务 Kubernetes 版 ACK-阿里云[ https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/faq-about-authorization-management](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/faq-about-authorization-management)

\[105] 集群多层次权限管理-授权-容器服务 Kubernetes 版 ACK-阿里云[ https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/authorization-overview](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/authorization-overview)

\[106] 服务账号 | Kubernetes[ https://kubernetes.io/zh-cn/docs/concepts/security/service-accounts/](https://kubernetes.io/zh-cn/docs/concepts/security/service-accounts/)

\[107] ACK场景下应用程序访问云资源最佳实践[ https://help.aliyun.com/zh/landing-zone/solution-115](https://help.aliyun.com/zh/landing-zone/solution-115)

\[108] Container Service for Kubernetes:Authorization overview[ https://www.alibabacloud.com/help/en/ack/authorization-overview](https://www.alibabacloud.com/help/en/ack/authorization-overview)

\[109] Container Service for Kubernetes:RBAC permissions required by the ack-cluster-agent component[ https://www.alibabacloud.com/help/en/ack/distributed-cloud-container-platform-for-kubernetes/user-guide/rbac-permissions-required-by-ack-cluster-agent](https://www.alibabacloud.com/help/en/ack/distributed-cloud-container-platform-for-kubernetes/user-guide/rbac-permissions-required-by-ack-cluster-agent)

\[110] 使用RRSA配置ServiceAccount实现Pod权限隔离-容器服务 Kubernetes 版 ACK-阿里云[ https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/use-rrsa-to-authorize-pods-to-access-different-cloud-services](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/use-rrsa-to-authorize-pods-to-access-different-cloud-services)

\[111] Support Multiple Users Guide[ https://arena-docs.readthedocs.io/en/latest/multiple-users/](https://arena-docs.readthedocs.io/en/latest/multiple-users/)

\[112] Arena Kubeflow Pipeline Notebook demo[ https://notebook.community/kubeflow/kfp-tekton-backend/samples/contrib/arena-samples/standalonejob/standalone\_pipeline](https://notebook.community/kubeflow/kfp-tekton-backend/samples/contrib/arena-samples/standalonejob/standalone_pipeline)

\[113] 为KServe服务配置CPU GPU与定时弹性扩缩容策略-容器服务 Kubernetes 版 ACK-阿里云[ https://help.aliyun.com/zh/ack/cloud-native-ai-suite/user-guide/configure-an-elastic-scaling-policy-for-a-service](https://help.aliyun.com/zh/ack/cloud-native-ai-suite/user-guide/configure-an-elastic-scaling-policy-for-a-service)

\[114] Arena[ https://github.com/kubeflow/arena/blob/master/README\_cn.md](https://github.com/kubeflow/arena/blob/master/README_cn.md)

\[115] Arena[ https://www.npmrc.cn/en/arena.html](https://www.npmrc.cn/en/arena.html)

\[116] Arena在多用户场景下最佳实践-容器服务 Kubernetes 版 ACK(ACK)-阿里云帮助中心[ https://help.aliyun.com/zh/ack/cloud-native-ai-suite/use-cases/best-practices-for-using-arena-in-multi-tenant-scenarios](https://help.aliyun.com/zh/ack/cloud-native-ai-suite/use-cases/best-practices-for-using-arena-in-multi-tenant-scenarios)

\[117] 用户无权限访问NVIDIA GPU性能计数器问题解析\_编程语言-CSDN问答[ https://ask.csdn.net/questions/8478446](https://ask.csdn.net/questions/8478446)

\[118] Arena: 基于Kubernetes的机器学习训练平台\_kubearena-CSDN博客[ https://blog.csdn.net/m0\_75126181/article/details/141892857](https://blog.csdn.net/m0_75126181/article/details/141892857)

\[119] arena/charts/tfjob/values.yaml at master · kubeflow/arena · GitHub[ https://github.com/kubeflow/arena/blob/master/charts/tfjob/values.yaml](https://github.com/kubeflow/arena/blob/master/charts/tfjob/values.yaml)

\[120] TFserving job with prometheus[ https://github.com/kubeflow/arena/blob/master/docs/serving/tfserving/monitor.md](https://github.com/kubeflow/arena/blob/master/docs/serving/tfserving/monitor.md)

\[121] Kubernetes Python Client[ https://kubernetes.readthedocs.io/en/latest/README.html](https://kubernetes.readthedocs.io/en/latest/README.html)

\[122] Kubernetes Python Client 教程-CSDN博客[ https://blog.csdn.net/gitblog\_00058/article/details/141013642](https://blog.csdn.net/gitblog_00058/article/details/141013642)

\[123] 每天只花10分钟，用Python脚本搞定Kubernetes运维，你也能做到!-CSDN博客[ https://blog.csdn.net/simcode/article/details/152416001](https://blog.csdn.net/simcode/article/details/152416001)

\[124] python/kubernetes/README.md at master · kubernetes-client/python · GitHub[ https://github.com/kubernetes-client/python/blob/master/kubernetes/README.md?ref=thechiefio](https://github.com/kubernetes-client/python/blob/master/kubernetes/README.md?ref=thechiefio)

\[125] 클라이언트 라이브러리[ https://kubernetes.io/ko/docs/reference/using-api/client-libraries/](https://kubernetes.io/ko/docs/reference/using-api/client-libraries/)

\[126] kubenetes-client/api.py at master · tkanng/kubenetes-client · GitHub[ https://github.com/tkanng/kubenetes-client/blob/master/api.py](https://github.com/tkanng/kubenetes-client/blob/master/api.py)

\[127] 【Kubernetes运维自动化终极指南】:10个必掌握的Python脚本实战技巧-CSDN博客[ https://blog.csdn.net/InitFlow/article/details/152415884](https://blog.csdn.net/InitFlow/article/details/152415884)

\[128] 阿里云代理商:阿里云产品有哪些监控接口可用?[ http://m.toutiao.com/group/7532798675756876323/?upstream\_biz=doubao](http://m.toutiao.com/group/7532798675756876323/?upstream_biz=doubao)

\[129] 一行代码实现智能异常检测:UModel PaaS API 架构设计与最佳实践\_阿里云云原生[ http://m.toutiao.com/group/7582428191474680361/?upstream\_biz=doubao](http://m.toutiao.com/group/7582428191474680361/?upstream_biz=doubao)

\[130] 从系统监控到业务洞察:ARMS 自定义指标采集功能全解析\_阿里云云原生[ http://m.toutiao.com/group/7579920866576286249/?upstream\_biz=doubao](http://m.toutiao.com/group/7579920866576286249/?upstream_biz=doubao)

\[131] Java 也能快速搭建 AI 应用?一文带你玩转 Spring AI 可观测性\_阿里云云原生[ http://m.toutiao.com/group/7477874641248289290/?upstream\_biz=doubao](http://m.toutiao.com/group/7477874641248289290/?upstream_biz=doubao)

\[132] 阿里云自动巡检\_云掣小助手[ http://m.toutiao.com/group/6883741772950798856/?upstream\_biz=doubao](http://m.toutiao.com/group/6883741772950798856/?upstream_biz=doubao)

\[133] AIOps 智能运维:有没有比专家经验更优雅的错/慢调用分析工具?\_阿里云云原生[ http://m.toutiao.com/group/7345725346383315471/?upstream\_biz=doubao](http://m.toutiao.com/group/7345725346383315471/?upstream_biz=doubao)

\[134] 全链路追踪 & 性能监控，GO 应用可观测全面升级\_阿里云云原生[ http://m.toutiao.com/group/7395492939671093794/?upstream\_biz=doubao](http://m.toutiao.com/group/7395492939671093794/?upstream_biz=doubao)

\[135] 企业微信告警接口调用全解析，基于Python的高可用报警系统设计-CSDN博客[ https://blog.csdn.net/LearnFlow/article/details/152450148](https://blog.csdn.net/LearnFlow/article/details/152450148)

\[136] Python 创建和交互企业微信群机器人的教程\_python 企业微信机器人-CSDN博客[ https://blog.csdn.net/zhangyunchou2015/article/details/147116568](https://blog.csdn.net/zhangyunchou2015/article/details/147116568)

\[137] GitHub - mqzhang/wechat\_work\_webhook\_py: 企业微信群机器人Webhook Python 客户端. 支持文本消息, markdown, 图片, 图文, 文件 消息 ( https://work.weixin.qq.com/api/doc/90000/90136/91770 ).[ https://github.com/mqzhang/wechat\_work\_webhook\_py](https://github.com/mqzhang/wechat_work_webhook_py)

\[138] python实现企业微信回消息\_mob64ca12d8821d的技术博客\_51CTO博客[ https://blog.51cto.com/u\_16213333/13491941](https://blog.51cto.com/u_16213333/13491941)

\[139] Python实现企业微信群告警\_企业微信告警-CSDN博客[ https://blog.csdn.net/wt334502157/article/details/132477893](https://blog.csdn.net/wt334502157/article/details/132477893)

\[140] Python 企业微信通知原来这么简单\_python企业微信推送消息-CSDN博客[ https://blog.csdn.net/python12345\_/article/details/137766029](https://blog.csdn.net/python12345_/article/details/137766029)

\[141] Python实现微信企业号API交互完整源码项目-CSDN博客[ https://blog.csdn.net/weixin\_30661119/article/details/154231087](https://blog.csdn.net/weixin_30661119/article/details/154231087)

\[142] 腾讯云可观测平台 使用企业微信群接收告警通知\_腾讯云[ https://cloud.tencent.com/document/product/248/50413](https://cloud.tencent.com/document/product/248/50413)

\[143] 消息中心 企业微信群机器人接收消息\_腾讯云[ https://cloud.tencent.com/document/product/1263/71731](https://cloud.tencent.com/document/product/1263/71731)

\[144] 企业微信的机器人如何每天定时发送内容到群里面?\_微盛AI研究院[ http://m.toutiao.com/group/7561769631015272979/?upstream\_biz=doubao](http://m.toutiao.com/group/7561769631015272979/?upstream_biz=doubao)

\[145] 企微群中 消息推送机器人如何创建 - CSDN文库[ https://wenku.csdn.net/answer/34j1vbw51y](https://wenku.csdn.net/answer/34j1vbw51y)

\[146] 企业微信机器人推送 - CSDN文库[ https://wenku.csdn.net/answer/ndygj92zvb](https://wenku.csdn.net/answer/ndygj92zvb)

\[147] 企业微信二次开发:外部群消息推送实现指南-AI.x-AIGC专属社区-51CTO.COM[ https://www.51cto.com/aigc/9578.html](https://www.51cto.com/aigc/9578.html)

\[148] java实现信息推送至webhook企业微信机器人\_企业微信机器人webhook-CSDN博客[ https://blog.csdn.net/qq\_37557563/article/details/141223119](https://blog.csdn.net/qq_37557563/article/details/141223119)

\[149] 用 Python 实现定时任务:APScheduler 配置与实战案例\_小雪的技术博客\_51CTO博客[ https://blog.51cto.com/u\_17353607/14201459](https://blog.51cto.com/u_17353607/14201459)

\[150] Python实用技巧:如何使用Python进行定时任务调度\_鹤上江的技术博客\_51CTO博客[ https://blog.51cto.com/u\_17069749/13148900](https://blog.51cto.com/u_17069749/13148900)

\[151] 定时任务专家:使用APScheduler-CSDN博客[ https://blog.csdn.net/qq\_42568323/article/details/153832808](https://blog.csdn.net/qq_42568323/article/details/153832808)

\[152] Python定时任务实战:APScheduler从入门到精通​ 在开发Web应用时，常遇到这样的需求:每天凌晨3点自动备 - 掘金[ https://juejin.cn/post/7558852538026016768](https://juejin.cn/post/7558852538026016768)

\[153] Python定时任务框架APScheduler详解-CSDN博客[ https://blog.csdn.net/kobepaul123/article/details/123616575](https://blog.csdn.net/kobepaul123/article/details/123616575)

\[154] 17. python APScheduler定时任务 - 逃离这世界\~ - 博客园[ https://www.cnblogs.com/supershy/p/18730291](https://www.cnblogs.com/supershy/p/18730291)

\[155] Python中如何实现定时任务?APScheduler详细配置-Python教程-PHP中文网[ https://m.php.cn/faq/1410149.html](https://m.php.cn/faq/1410149.html)

\[156] Celery 全面指南:Python 分布式任务队列详解\_mob6454cc6eb555的技术博客\_51CTO博客[ https://blog.51cto.com/u\_16099258/14227975](https://blog.51cto.com/u_16099258/14227975)

\[157] Python 中的 Celery:分布式任务队列的实践指南\_树言树语Tree[ http://m.toutiao.com/group/7585386830464336430/?upstream\_biz=doubao](http://m.toutiao.com/group/7585386830464336430/?upstream_biz=doubao)

\[158] python 实现 Celery 任务队列系统\_python3 celery-CSDN博客[ https://blog.csdn.net/hzether/article/details/146925177](https://blog.csdn.net/hzether/article/details/146925177)

\[159] 基于Python的Celery分布式任务队列系统实现 - CSDN文库[ https://wenku.csdn.net/doc/u39is7jffv](https://wenku.csdn.net/doc/u39is7jffv)

\[160] Celery入门指南:异步任务处理与分布式调度Celery入门指南:异步任务处理与分布式调度 什么是Celery Cel - 掘金[ https://juejin.cn/post/7485655863363387402](https://juejin.cn/post/7485655863363387402)

\[161] 任务调度 - 标签 - 腾讯云开发者社区-腾讯云[ https://cloud.tencent.com/developer/tag/10878?entry=ask](https://cloud.tencent.com/developer/tag/10878?entry=ask)

\[162] Celery，一个异步任务操作的 Python 库! - 腾讯云开发者社区-腾讯云[ https://cloud.tencent.com/developer/news/2072864](https://cloud.tencent.com/developer/news/2072864)

\[163] 【操作系统09】GPU占用率与显存占用率-CSDN博客[ https://zhengjunxue.blog.csdn.net/article/details/145541881](https://zhengjunxue.blog.csdn.net/article/details/145541881)

\[164] gpu\_utils和gpu\_memory是什么指标 - CSDN文库[ https://wenku.csdn.net/answer/6jfp8yhe5m](https://wenku.csdn.net/answer/6jfp8yhe5m)

\[165] gpu-memory-utilization参数是? - CSDN文库[ https://wenku.csdn.net/answer/6jwn3ftwrm](https://wenku.csdn.net/answer/6jwn3ftwrm)

\[166] 深度学习中GPU和显存分析-腾讯云开发者社区-腾讯云[ https://cloud.tencent.com/developer/article/2507458](https://cloud.tencent.com/developer/article/2507458)

\[167] 技巧-GPU显存和利用率如何提高和batch\_size/num\_works等参数的实验测试\_numworkers设置多少-CSDN博客[ https://blog.csdn.net/zwhdldz/article/details/134711996](https://blog.csdn.net/zwhdldz/article/details/134711996)

\[168] 768MiB / 6144MiB 是这样 - CSDN文库[ https://wenku.csdn.net/answer/7sij51gbvp](https://wenku.csdn.net/answer/7sij51gbvp)

\[169] GPU使用率和GPU显存使用率的区别是什么-CSDN博客[ https://blog.csdn.net/weixin\_44544263/article/details/155096251](https://blog.csdn.net/weixin_44544263/article/details/155096251)

\[170] 我测试了RTX4090显卡的显存占用情况-CSDN博客[ https://blog.csdn.net/weixin\_29476595/article/details/152051990](https://blog.csdn.net/weixin_29476595/article/details/152051990)

\[171] 神经网络显存占用分析:从原理到优化的实战指南\_一般软件的显存占用-CSDN博客[ https://blog.csdn.net/qq\_45464126/article/details/150491744](https://blog.csdn.net/qq_45464126/article/details/150491744)

\[172] 怎么看手机GPU带宽 手机gpu显存 查看\_mob64ca13f6bbea的技术博客\_51CTO博客[ https://blog.51cto.com/u\_16213577/10079338](https://blog.51cto.com/u_16213577/10079338)

\[173] linux 查看显卡使用率 - CSDN文库[ https://wenku.csdn.net/answer/739wt5tcsw](https://wenku.csdn.net/answer/739wt5tcsw)

\[174] 查看显存占用情况的命令是什么 - CSDN文库[ https://wenku.csdn.net/answer/4fz7f43bbx](https://wenku.csdn.net/answer/4fz7f43bbx)

\[175] 【GPU】\_显存优化-CSDN博客[ https://blog.csdn.net/bryant\_meng/article/details/111627794](https://blog.csdn.net/bryant_meng/article/details/111627794)

\[176] 了解 NVIDIA GPU 性能:利用率与饱和度[ https://www.vxworks.net/ai/1245-understanding-gpu-performance](https://www.vxworks.net/ai/1245-understanding-gpu-performance)

\[177] 使用云监控和ARMS为分布式训练任务配置监控与报警-人工智能平台 PAI-阿里云[ https://help.aliyun.com/zh/pai/user-guide/training-monitoring-and-alerting](https://help.aliyun.com/zh/pai/user-guide/training-monitoring-and-alerting)

\[178] GPU metrics | Arm Learning Paths[ https://learn.arm.com/learning-paths/smartphones-and-mobile/unity\_packages/mali\_metrics/](https://learn.arm.com/learning-paths/smartphones-and-mobile/unity_packages/mali_metrics/)

\[179] 【产品变更】可观测监控prometheus版支持的容器服务集群基础指标变更通知[ https://help.aliyun.com/zh/arms/product-overview/product-announcement-notification-of-changes-to-basic-container-service-cluster-metrics-supported-by-the-observable-monitoring-prometheus-version](https://help.aliyun.com/zh/arms/product-overview/product-announcement-notification-of-changes-to-basic-container-service-cluster-metrics-supported-by-the-observable-monitoring-prometheus-version)

\[180] Mali GPU counters reference[ https://github.com/needle-mirror/com.unity.profiling.systemmetrics.mali/blob/master/Documentation\~/metrics-guide.md](https://github.com/needle-mirror/com.unity.profiling.systemmetrics.mali/blob/master/Documentation~/metrics-guide.md)

\[181] Container Insights または Managed Prometheus を使用して GPU 監視を構成する[ https://learn.microsoft.com/ja-jp/Azure/azure-monitor/containers/container-insights-gpu-monitoring](https://learn.microsoft.com/ja-jp/Azure/azure-monitor/containers/container-insights-gpu-monitoring)

\[182] AmlComputeCpuGpuUtilization[ https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables/AMLComputeCpuGpuUtilization](https://learn.microsoft.com/en-us/azure/azure-monitor/reference/tables/AMLComputeCpuGpuUtilization)

\[183] Configuración de la supervisión de GPU con Container Insights o Prometheus administrado[ https://learn.microsoft.com/es-es/azure/azure-monitor/containers/container-insights-gpu-monitoring](https://learn.microsoft.com/es-es/azure/azure-monitor/containers/container-insights-gpu-monitoring)

\[184] 配置HPA使用Prometheus的GPU指标实现容器弹性伸缩-容器服务Kubernetes版ACK-阿里云[ https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/enable-auto-scaling-based-on-gpu-metrics-1](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/enable-auto-scaling-based-on-gpu-metrics-1)

\[185] 可观测监控Prometheus版支持的容器集群基础指标有哪些-云监控(CMS)-阿里云帮助中心[ https://help.aliyun.com/zh/cms/cloudmonitor-1-0/developer-reference/container-cluster-metrics](https://help.aliyun.com/zh/cms/cloudmonitor-1-0/developer-reference/container-cluster-metrics)

\[186] Container Compute Service:Introduction to metrics of ACS GPU-accelerated pods[ https://www.alibabacloud.com/help/en/cs/user-guide/acs-gpu-pod-monitoring-indicators](https://www.alibabacloud.com/help/en/cs/user-guide/acs-gpu-pod-monitoring-indicators)

\[187] Container Service for Kubernetes:Use AHPA to perform predictive scaling based on GPU metrics[ https://www.alibabacloud.com/help/en/ack/ack-managed-and-ack-dedicated/user-guide/use-ahpa-to-perform-predictive-scaling-based-on-gpu-metrics](https://www.alibabacloud.com/help/en/ack/ack-managed-and-ack-dedicated/user-guide/use-ahpa-to-perform-predictive-scaling-based-on-gpu-metrics)

\[188] GPU监控面板各维度指标详解-容器服务 Kubernetes 版 ACK-阿里云[ https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/panels](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/panels)

\[189] 基于阿里云容器服务监控 Kubernetes集群GPU指标-阿里云开发者社区[ https://developer.aliyun.com/article/647565](https://developer.aliyun.com/article/647565)

\[190] 使用Prometheus监控ACK Edge集群GPU资源-容器服务 Kubernetes 版 ACK-阿里云[ https://help.aliyun.com/zh/ack/ack-edge/use-cases/best-practices-for-monitoring-gpu-resources-in-ack-edge-clusters](https://help.aliyun.com/zh/ack/ack-edge/use-cases/best-practices-for-monitoring-gpu-resources-in-ack-edge-clusters)

\[191] 容器场景可观测最佳实践\_容器服务 Kubernetes 版 ACK(ACK)-阿里云帮助中心[ https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/observability-best-practices](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/observability-best-practices)

\[192] 接入与配置阿里云Prometheus监控-容器服务 Kubernetes 版 ACK-阿里云[ https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/use-alibaba-cloud-prometheus-service-to-monitor-an-ack-cluster](https://help.aliyun.com/zh/ack/ack-managed-and-ack-dedicated/user-guide/use-alibaba-cloud-prometheus-service-to-monitor-an-ack-cluster)

\[193] 如何专业化监控一个 Kubernetes 集群?-CSDN博客[ https://blog.csdn.net/weixin\_43970890/article/details/117807466](https://blog.csdn.net/weixin_43970890/article/details/117807466)

\[194] 为ACK Serverless集群接入阿里云Prometheus监控并配置告警与自定义指标-容器服务 Kubernetes 版 ACK-阿里云[ https://help.aliyun.com/zh/ack/serverless-kubernetes/user-guide/enable-prometheus-service](https://help.aliyun.com/zh/ack/serverless-kubernetes/user-guide/enable-prometheus-service)

\[195] 启用对 AKS 群集的监视 - Azure Monitor | Microsoft Learn[ https://docs.microsoft.com/zh-cn/azure/azure-monitor/containers/kubernetes-monitoring-enable](https://docs.microsoft.com/zh-cn/azure/azure-monitor/containers/kubernetes-monitoring-enable)

\[196] 管理新式应用程序平台解决方案，以实现最佳性能和可靠性 - Cloud Adoption Framework | Microsoft Learn[ https://learn.microsoft.com/zh-cn/azure/cloud-adoption-framework/scenarios/app-platform/manage](https://learn.microsoft.com/zh-cn/azure/cloud-adoption-framework/scenarios/app-platform/manage)

\[197] Container Service for Kubernetes:Monitoring management[ https://www.alibabacloud.com/help/en/ack/ack-managed-and-ack-dedicated/user-guide/monitoring-management/](https://www.alibabacloud.com/help/en/ack/ack-managed-and-ack-dedicated/user-guide/monitoring-management/)

\[198] 基于RBAC的k8s服务账号授权示例\_kubernetes 的账号-CSDN博客[ https://blog.csdn.net/Sebastien23/article/details/128513724](https://blog.csdn.net/Sebastien23/article/details/128513724)

\[199] Kubernetes 服务账号深度解析:原理与实践指南-CSDN博客[ https://blog.csdn.net/gitblog\_00547/article/details/148548708](https://blog.csdn.net/gitblog_00547/article/details/148548708)

\[200] Menggunakan Otorisasi RBAC[ https://kubernetes.io/id/docs/reference/access-authn-authz/rbac/](https://kubernetes.io/id/docs/reference/access-authn-authz/rbac/)

\[201] 使用 RBAC 授权 | Kubernetes (K8s) 容器编排系统[ https://kubernetes.ac.cn/docs/reference/access-authn-authz/rbac/](https://kubernetes.ac.cn/docs/reference/access-authn-authz/rbac/)

\[202] Exercise 4: Service Accounts and RBAC[ http://microsoft.github.io/k8s-on-azure-workshop/lab-3/4\_service\_account\_rbac/index.html](http://microsoft.github.io/k8s-on-azure-workshop/lab-3/4_service_account_rbac/index.html)

\[203] k8s分配指定命名空间的操作权限 - 高佳丰 - 博客园[ https://www.cnblogs.com/ggborn-001/p/18880316](https://www.cnblogs.com/ggborn-001/p/18880316)

\[204] 已启用 Azure Arc 的 Kubernetes 群集上的 Azure RBAC - Azure Arc | Azure Docs[ https://docs.azure.cn/zh-cn/azure-arc/kubernetes/azure-rbac](https://docs.azure.cn/zh-cn/azure-arc/kubernetes/azure-rbac)

> （注：文档部分内容可能由 AI 生成）