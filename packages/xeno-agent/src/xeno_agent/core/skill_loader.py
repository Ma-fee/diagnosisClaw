from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from xeno_agent.utils.logging import get_logger

logger = get_logger(__name__)


class SkillMetadata(BaseModel):
    name: str
    description: str
    allowed_tools: list[str] = Field(default_factory=list)


class Skill(BaseModel):
    metadata: SkillMetadata
    instructions: str
    path: Path


class SkillLoader:
    """
    SkillLoader loads Claude Skills from the filesystem.

    A Skill is defined by a SKILL.md file with YAML frontmatter.
    Format:
    ---
    name: skill-name
    description: Description
    allowed-tools:
      - tool1
    ---

    # Title

    ## Instructions
    ...
    """

    def __init__(self, skills_dir: str = "packages/xeno-agent/skills"):
        # Support running from root or package dir
        self.skills_dir = Path(skills_dir)
        if not self.skills_dir.exists():
            # Try relative to package root if running as module
            self.skills_dir = Path(__file__).parent.parent.parent.parent / "skills"

    def load_all(self) -> dict[str, Skill]:
        """
        Load all skills from the skills directory.

        Returns:
            Dict mapping skill names to Skill objects.
        """
        skills = {}
        if not self.skills_dir.exists():
            logger.warning(f"Skills directory not found: {self.skills_dir}")
            return skills

        # Look for SKILL.md files in subdirectories
        for skill_file in self.skills_dir.glob("**/SKILL.md"):
            try:
                skill = self._load_skill(skill_file)
                if skill:
                    skills[skill.metadata.name] = skill
            except Exception:
                logger.exception(f"Failed to load skill from {skill_file}")

        return skills

    def _load_skill(self, file_path: Path) -> Skill | None:
        """
        Parse a SKILL.md file.
        """
        content = file_path.read_text(encoding="utf-8")

        # Split frontmatter and content
        parts = content.split("---", 2)
        if len(parts) < 3:
            logger.warning(f"Invalid SKILL.md format in {file_path}: Missing frontmatter")
            return None

        frontmatter_yaml = parts[1]
        instructions = parts[2].strip()

        try:
            metadata_dict = yaml.safe_load(frontmatter_yaml)
            metadata = SkillMetadata(**metadata_dict)

            # Ensure name matches directory name (convention)
            # parent_name = file_path.parent.name
            # if metadata.name != parent_name:
            #     logger.warning(f"Skill name '{metadata.name}' doesn't match directory '{parent_name}'")

            return Skill(metadata=metadata, instructions=instructions, path=file_path.parent)
        except Exception:
            logger.exception(f"Failed to parse skill metadata in {file_path}")
            return None
