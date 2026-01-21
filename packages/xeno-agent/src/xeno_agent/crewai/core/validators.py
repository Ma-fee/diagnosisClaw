"""
Output validation layer for agent outputs.

Implements validators for Markdown formatting and citation requirements
as specified in RFC 002.
"""

import re

from ..utils.logging import get_logger

logger = get_logger(__name__)


class OutputValidator:
    """Agent 输出验证器"""

    # Markdown 基本格式模式
    HEADING_PATTERN = r"^#{1,6}\s+.+$"
    LIST_PATTERN = r"^\s*[-*+]\s+.+$|^(\d+[\.)])\s+.+$"
    TABLE_PATTERN = r"^\|.*\|$"

    @staticmethod
    def validate_markdown(content: str) -> tuple[bool, list[str | None]]:
        """
        验证 Markdown 格式。

        检查内容包括：
        - 是否包含标题
        - 是否包含列表
        - 是否包含表格（如果需要）
        - 基本格式语法

        Args:
            content: Agent 输出内容

        Returns:
            (is_valid, errors)
        """
        errors = []
        lines = content.split("\n")

        has_heading = any(re.match(OutputValidator.HEADING_PATTERN, line) for line in lines)
        has_list = any(re.match(OutputValidator.LIST_PATTERN, line) for line in lines)
        has_table = any(re.match(OutputValidator.TABLE_PATTERN, line) for line in lines)

        # 基本格式检查
        if not has_heading:
            errors.append("输出缺少标题，建议使用 Markdown 标题格式 (# 标题)")

        # 对于技术性输出，通常包含列表或表格
        if not (has_list or has_table):
            errors.append("输出建议使用列表或表格来展示结构化信息")

        return len(errors) == 0, errors

    @staticmethod
    def validate_citation(content: str, requires_citation: bool = True) -> tuple[bool, list[str | None]]:
        """
        验证引用格式。

        要求:
        - Material Assistant: 必须引用 (requires_citation=True)
        - 其它专家: 建议引用 (requires_citation=False，但仍会警告)

        格式: [来源描述/标识]

        Args:
            content: Agent 输出内容
            requires_citation: 是否强制要求引用（对于 Material Assistant 为 True）

        Returns:
            (is_valid, errors)
        """
        errors: list[str | None] = []

        # 查找所有 [来源] 格式的引用
        citations = re.findall(r"\[([^\]]+)\]", content)

        # 过滤掉非引用的括号（如链接、脚注等）
        valid_citations = [citation for citation in citations if any(keyword in citation for keyword in ["批次号", "手册", "图纸", "页码", "来源", "URL", "source"])]

        if requires_citation:
            if not valid_citations:
                errors.append("输出缺少引用，请添加 [来源描述/标识]，例如：[手册批次号: PM-2023-042]")
        else:
            if citations and not valid_citations:
                # 如果有括号但看起来不像引用，不报错
                pass
            elif not valid_citations:
                # 建议性警告，不是错误
                errors.append("(未检测到引用，建议为关键信息添加引用以增强可信度，例如：[来源: 官方技术手册]")

        return len(errors) == 0, errors

    @staticmethod
    def validate_role_output(content: str, role_name: str) -> tuple[bool, list[str | None]]:
        """
        为特定角色验证输出。

        Args:
            content: Agent 输出内容
            role_name: 角色名称

        Returns:
            (is_valid, all_errors)
        """
        all_errors = []

        # Markdown 格式验证（所有角色）
        is_md_valid, md_errors = OutputValidator.validate_markdown(content)
        all_errors.extend(md_errors)

        # 引用要求验证
        if role_name == "material_assistant":
            # Material Assistant: 必须引用
            is_citation_valid, citation_errors = OutputValidator.validate_citation(content, requires_citation=True)
            all_errors.extend(citation_errors)

        elif role_name == "equipment_expert" or role_name == "fault_expert":
            # 专家：建议引用，但不强制
            is_citation_valid, citation_errors = OutputValidator.validate_citation(content, requires_citation=False)
            all_errors.extend(citation_errors)

        return len(all_errors) == 0 or len(all_errors) == 1, all_errors
