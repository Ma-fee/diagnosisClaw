description: |-
  在单次交互中向用户提出多个结构化问题的工具。

  能够通过包含多种问题类型（单选、多选、文本输入）的问卷格式收集复杂的多字段数据。

  ### **何时使用此工具**

  **当您需要一次性向用户收集多项相关信息时，请使用此工具。**

  **需要强制使用的场景：**

  1. **多字段信息收集**
     - 需要在一次交互中收集几个相关的数据点
     - 示例：设备型号、工作小时数、故障症状和维护记录

  2. **结构化数据录入**
     - 用户输入遵循具有多个字段的预定义模式
     - 示例：包含位置、设备 ID、问题类型和优先级的服务报告表单

  3. **复杂的选项选择**
     - 包含不同选项类型（单选、多选、自由文本）的多个问题
     - 示例：带有条件性后续问题的诊断问卷

  4. **向导式数据收集**
     - 带有验证的逐步引导式数据录入
     - 示例：包含序列号、型号、购买日期的设备注册

  ### **使用指南**

  1. **顺序很重要**：问题将按照它们在 XML 中出现的顺序展示
  2. **对相关字段进行分组**：将相关问题放在同一个问卷中
  3. **最小化问题数量**：每次调用包含 1-5 个问题以获得更好的用户体验
  4. **提供选项**：对于单选/多选类型，提供 2-6 个明确定义的选项
  5. **使用描述**：为建议选项添加描述以提高清晰度
  6. **验证**：谨慎使用 `required="false"` 来设置非必填字段

  ### **应避免的常见陷阱**

  - ❌ 在同一问卷中询问不相关的问题
  - ❌ 使用无法描述该字段的通用标题
  - ❌ 为单选（enum）问题仅提供一个选项
  - ❌ XML 嵌套错误（确保正确的闭合标签）
  - ❌ 使用未正确转义的特殊 XML 字符

name: question_for_user
parameters:
  type: object
  properties:
    questionnaire:
      type: string
      description: |-
        包含结构化问题的 XML 格式问卷。

        **必须包含在 `<questions>` 标签内**，该标签包含一个或多个 `<question>` 元素。
        每个问题可以有带有描述、输入类型和操作的建议（suggest）选项。

        ```xml
        <questions>
          <question header="字段标签" type="enum|multi|input" required="true|false">
            <text>向用户展示的问题文本</text>
            <suggest description="选项解释" type="choice|input|fill" next_action="tool_name">
              选项文本
            </suggest>
            ...
          </question>
          ...
        </questions>
        ```

        #### Question 属性

        - **header**（必填）：问题的简短标签/字段名称
        - **type**（必填）：问题类型
          - `enum`：从选项中单选（单选按钮）
          - `multi`：多选（复选框）
          - `input`：自由文本输入字段
        - **required**（可选）：是否必答，默认为 `true`

        #### Suggest 属性

        - **description**（可选）：选项的详细解释，显示为工具提示/副标题
        - **type**（可选）：选项行为类型
          - `choice`：标准可选项（默认）
          - `input`：打开文本输入框以进行自由形式的录入
          - `fill`：用于结构化数据录入的预填充模板
        - **next_action**（可选）：选择后自动触发的工具名称（例如，`"update_todo_list"`，`"attempt_completion"`）

        ### **示例**

        #### 示例 1：设备信息（单选 + 输入）
        ```xml
        <questions>
          <question header="型号" type="enum" required="true">
            <text>您正在处理哪种设备型号？</text>
            <suggest description="21.5 吨挖掘机">SY215C</suggest>
            <suggest description="36.5 吨挖掘机">SY365H</suggest>
            <suggest type="input">其他型号</suggest>
          </question>
          <question header="工作小时数" type="input" required="true">
            <text>当前的工作小时数是多少？</text>
          </question>
        </questions>
        ```

        #### 示例 2：故障症状（多选）
        ```xml
        <questions>
          <question header="症状" type="multi" required="true">
            <text>请选择所有观察到的症状：</text>
            <suggest description="排气冒黑烟">黑烟</suggest>
            <suggest description="发动机功率下降">动力不足</suggest>
            <suggest description="发动机发出异常声音">异响</suggest>
            <suggest description="发动机温度过高">过热</suggest>
          </question>
        </questions>
        ```

        #### 示例 3：服务报告（混合类型）
        ```xml
        <questions>
          <question header="服务类型" type="enum" required="true">
            <text>需要哪种类型的服务？</text>
            <suggest>定期维护</suggest>
            <suggest>维修</suggest>
            <suggest>检查</suggest>
            <suggest>紧急故障排除</suggest>
          </question>
          <question header="优先级" type="enum" required="true">
            <text>设置服务优先级：</text>
            <suggest description="设备无法运行">严重</suggest>
            <suggest description="功能受限">高</suggest>
            <suggest description="预防性/计划内">普通</suggest>
            <suggest description="时间方便时">低</suggest>
          </question>
          <question header="补充说明" type="input" required="false">
            <text>有任何补充细节或特殊要求吗？</text>
          </question>
        </questions>
        ```
  required:
    - questionnaire
strict: false