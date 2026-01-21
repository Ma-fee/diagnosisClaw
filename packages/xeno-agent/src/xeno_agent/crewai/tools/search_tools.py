from crewai.tools import BaseTool

from ..core.tool_decorator import configured_tool


@configured_tool("search_engine")
class SearchEngineTool(BaseTool):
    """
    【搜索引擎工具】
    模拟从外部知识库、手册或互联网检索技术信息。
    """

    def _run(self, query: str) -> str:
        """
        Search for technical information.

        Args:
            query: The search query string.

        Returns:
            Search results with citations.
        """
        # Mock search results based on query keywords
        query_lower = query.lower()

        if "spec" in query_lower or "规格" in query_lower:
            return """
**检索结果**:
1. [官方手册] Fanuc 0i-MD 规格说明书 (PDF) - 第 24 页
   - X轴伺服电机型号: Beta iS 8/3000
   - 额定扭矩: 8 Nm
   - 编码器分辨率: 1,000,000 p/rev

2. [技术论坛] 伺服电机选型指南
   - 对应驱动器型号: A06B-6117-H105
"""
        if "drawing" in query_lower or "图纸" in query_lower or "结构" in query_lower:
            return """
**检索结果**:
1. [维护手册] 机床结构图集 - 编号: MEC-2023-X01
   - 包含 X 轴传动链结构图 (丝杠、轴承、电机连接)
   - 关键部件: 滚珠丝杠 (THK), 联轴器 (KTR)

2. [装配图] X轴总成
   - 图号: ASSY-X-002
"""

        return f"Found 3 generic results for '{query}'. Please refine query for specific manuals or specs."
