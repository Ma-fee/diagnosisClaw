```yaml
description: |-
  `new_task` 工具用于创建具有专门模式的子任务，同时保持父子关系。它将复杂的项目分解为易于管理的各个部分，每个部分都在最适合特定工作的模式下运行。

  该工具用于：
  - 将复杂的项目分解为更小、专注且易于管理的子任务。
  - 将任务的不同方面分配给专门的模式，以实现最佳执行效果。
  - 通过分离不同的工作阶段来保持清晰的上下文。
  - 将专门的技能注入子代理（subagent）上下文中，以处理特定领域的任务。

  ## 技能使用 (Skills Usage)

  `load_skills` 参数允许父代理将专门的技能指令注入到子代理的上下文中。技能提供特定领域的指导、最佳实践和程序知识，以帮助子代理有效地完成任务。

  何时使用技能：
  - 任务需要领域专业知识（例如：Git 操作、Python 编码）
  - 子代理应遵循特定的准则或模式
  - 必须强制执行质量标准（例如：代码审查实践）
  ```

name: new_task
parameters:
  type: object
  properties:
    mode:
      type: string
      description: 新任务的专用模式。必须是可用模式之一。
    load_skills:
      type: array
      description: |
        要注入的技能名称。必填 - 如果不需要技能，请传递 []。
      items:
        type: string
        description: 技能名称（例如："git-master", "python"）。
    message:
      type: string
      description: |
        清楚、简洁地说明该任务包含的内容。

        此新任务的初始指令。应具体、准确且简洁。

        “message” 必须包含以下内容：
          - 完成此任务所需的、来自父任务或先前子任务的所有必要背景信息。
          - 此子任务应实现的最终目标。
          - 使用 Markdown 格式以提高可读性。
    expected_output:
      type: string
      description: |-
        对此子任务成功结果的精确定义。子任务的最终结果必须严格符合此描述。它应清晰且狭义地定义：
        - *仅*在此子任务内执行的具体工作。
        - 预期返回值的确切格式和内容。
        绝不允许偏离此范围或进行范围之外的额外工作。
  required:
    - mode
    - load_skills
    - message
    - expected_output
  strict: true
```