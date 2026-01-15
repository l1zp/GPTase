"""Literature agent for extracting and documenting enzyme reaction data.

This agent specializes in:
1. Literature Data Extraction from Markdown enzyme reactions
2. Pipeline Documentation (data flow, steps, validations, transformations)
3. JSON Persistence of extracted data and pipeline summary
"""

from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel

from src.agents.base import BaseAgent
from src.core.constants import STATUS_COMPLETED
from src.core.constants import STATUS_ERROR
from src.core.constants import STATUS_PROCESSING
from src.core.constants import STATUS_STARTED
from src.core.constants import STATUS_SUCCESS
from src.memory.manager import MemoryManager
from src.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)

# Step names
STEP_LOAD_MARKDOWN = "load_markdown"
STEP_PARSE_MARKDOWN = "parse_markdown"
STEP_PERSIST_JSON = "persist_json"

# Tool names
TOOL_DOCUMENT_LOADER = "document_loader"
TOOL_CODE_WRITER = "code_writer"

# Default paths
DEFAULT_DATA_DIR = Path("data") / "extraction"

# Capability descriptions
CAPABILITY_EXTRACTION = "extraction"
CAPABILITY_PIPELINE_DOCUMENTATION = "pipeline_documentation"
CAPABILITY_VALIDATION = "validation"
CAPABILITY_PERSISTENCE = "persistence"

# Local status for step tracking
STATUS_FAILED = "failed"


class LiteratureAgent(BaseAgent):
    """Agent specialized in literature data extraction and pipeline documentation.

    This agent processes Markdown files containing enzyme reaction data,
    validates extracted reactions, documents the extraction pipeline,
    and persists results to JSON files.

    Attributes:
        agent_id: Unique identifier for this agent instance.
        memory_manager: Manager for persistent storage and messaging.
        tool_registry: Registry of available tools.
    """

    def __init__(
        self,
        agent_id: str,
        memory_manager: MemoryManager,
        tool_registry: ToolRegistry,
    ) -> None:
        super().__init__(
            agent_id=agent_id,
            memory_manager=memory_manager,
            tool_registry=tool_registry,
            capabilities=[
                CAPABILITY_EXTRACTION,
                CAPABILITY_PIPELINE_DOCUMENTATION,
                CAPABILITY_VALIDATION,
                CAPABILITY_PERSISTENCE,
            ],
        )
        self.logger = logging.getLogger(__name__)

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Process literature extraction task.

        Expected task shape:
        {
            "files": ["data/example1.md", ...],
            "output_path": "data/extraction/results.json"  # optional
        }

        Args:
            task: Task dictionary with 'files' list and optional 'output_path'.

        Returns:
            Dictionary with status, output_path, reactions_count, errors,
            validations, and pipeline_steps.
        """
        await self.update_status(STATUS_PROCESSING, task.get("id"))

        files: List[str] = task.get("files", [])
        if not files:
            await self.update_status(STATUS_ERROR, task.get("id"))
            return {"status": STATUS_ERROR, "error": "No files provided"}

        errors: List[str] = []
        validations: List[str] = []
        steps: List[Dict[str, Any]] = []
        reactions_all: List[Dict[str, Any]] = []

        for fpath in files:
            result = await self._process_file(fpath, steps, errors, validations,
                                              reactions_all)
            if not result:
                continue

        return await self._persist_results(task, reactions_all, steps, errors,
                                           validations)

    async def _process_file(
        self,
        fpath: str,
        steps: List[Dict[str, Any]],
        errors: List[str],
        validations: List[str],
        reactions_all: List[Dict[str, Any]],
    ) -> bool:
        """Process a single file through load, parse, and validate steps.

        Args:
            fpath: Path to the file to process.
            steps: List to append step records to.
            errors: List to append error messages to.
            validations: List to append validation messages to.
            reactions_all: List to append extracted reactions to.

        Returns:
            True if processing succeeded, False otherwise.
        """
        steps.append(
            self._create_step_record(
                STEP_LOAD_MARKDOWN,
                f"Load {fpath}",
                STATUS_STARTED,
            ))

        load_result = await self._load_file(fpath, steps, errors)
        if not load_result:
            return False

        steps.append(
            self._create_step_record(
                STEP_PARSE_MARKDOWN,
                f"Parse {fpath}",
                STATUS_STARTED,
            ))

        reactions = parse_markdown(load_result, source_file=fpath)
        steps[-1]["status"] = STATUS_COMPLETED

        self._validate_reactions(reactions, fpath, errors, validations)
        reactions_all.extend(reactions)
        return True

    async def _load_file(self, fpath: str, steps: List[Dict[str, Any]],
                         errors: List[str]) -> Optional[str]:
        """Load file content using document loader tool.

        Args:
            fpath: Path to the file.
            steps: Step records list to update.
            errors: Error list to append to.

        Returns:
            File text content or None if loading failed.
        """
        result = await self.tools.execute_tool(
            TOOL_DOCUMENT_LOADER,
            {
                "source_type": "file",
                "path": fpath
            },
        )

        if result.status.value != STATUS_SUCCESS:
            errors.append(f"Failed to read {fpath}: {result.error}")
            steps[-1]["status"] = STATUS_FAILED
            return None

        steps[-1]["status"] = STATUS_COMPLETED
        return result.data.get("text", "")

    def _validate_reactions(
        self,
        reactions: List[Dict[str, Any]],
        fpath: str,
        errors: List[str],
        validations: List[str],
    ) -> None:
        """Validate extracted reactions.

        Args:
            reactions: List of reaction dictionaries.
            fpath: Source file path for error messages.
            errors: List to append validation errors to.
            validations: List to append success messages to.
        """
        for rx in reactions:
            issues = validate_reaction(rx)
            if issues:
                errors.extend([f"{fpath}: {issue}" for issue in issues])
            else:
                validations.append(f"{fpath}: reaction validated OK")

    async def _persist_results(
        self,
        task: Dict[str, Any],
        reactions_all: List[Dict[str, Any]],
        steps: List[Dict[str, Any]],
        errors: List[str],
        validations: List[str],
    ) -> Dict[str, Any]:
        """Persist extraction results to JSON file.

        Args:
            task: Original task dictionary.
            reactions_all: List of all extracted reactions.
            steps: Pipeline step records.
            errors: List of error messages.
            validations: List of validation messages.

        Returns:
            Result dictionary with status and file path.
        """
        steps.append(
            self._create_step_record(
                STEP_PERSIST_JSON,
                "Save results to JSON",
                STATUS_STARTED,
            ))

        try:
            out_path = self._get_output_path(task)
            out_path.parent.mkdir(parents=True, exist_ok=True)

            output_model = build_output(reactions_all,
                                        steps=steps,
                                        validations=validations,
                                        errors=errors)
            payload = json.dumps(output_model.model_dump(), indent=2)

            write_res = await self.tools.execute_tool(
                TOOL_CODE_WRITER,
                {
                    "file_path": str(out_path),
                    "content": payload,
                    "overwrite": True
                },
            )

            if write_res.status.value == STATUS_SUCCESS:
                steps[-1]["status"] = STATUS_COMPLETED
                await self.update_status(STATUS_COMPLETED, task.get("id"))
                return self._create_success_response(str(out_path), len(reactions_all),
                                                     errors, validations, steps)
            else:
                steps[-1]["status"] = STATUS_FAILED
                await self.update_status(STATUS_ERROR, task.get("id"))
                return self._create_error_response(write_res.error, len(reactions_all),
                                                   steps)

        except Exception as e:
            steps[-1]["status"] = STATUS_FAILED
            await self.update_status(STATUS_ERROR, task.get("id"))
            return {"status": STATUS_ERROR, "error": str(e), "pipeline_steps": steps}

    def _get_output_path(self, task: Dict[str, Any]) -> Path:
        """Determine output path for results.

        Args:
            task: Task dictionary that may contain 'output_path'.

        Returns:
            Path where results should be written.
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_out = DEFAULT_DATA_DIR / f"enzyme_extraction_{timestamp}.json"
        return Path(task.get("output_path") or default_out)

    def _create_step_record(self, name: str, description: str,
                            status: str) -> Dict[str, Any]:
        """Create a step record for pipeline documentation.

        Args:
            name: Step identifier.
            description: Human-readable description.
            status: Step status (STATUS_STARTED, STATUS_COMPLETED, etc.).

        Returns:
            Step record dictionary.
        """
        return {"name": name, "description": description, "status": status}

    def _create_success_response(
        self,
        output_path: str,
        reactions_count: int,
        errors: List[str],
        validations: List[str],
        steps: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Create a successful response dictionary.

        Args:
            output_path: Path where results were saved.
            reactions_count: Number of reactions extracted.
            errors: List of errors (may be empty).
            validations: List of validation messages.
            steps: Pipeline step records.

        Returns:
            Success response dictionary.
        """
        return {
            "status": STATUS_SUCCESS,
            "output_path": output_path,
            "reactions_count": reactions_count,
            "errors": errors,
            "validations": validations,
            "pipeline_steps": steps,
        }

    def _create_error_response(self, error: str, reactions_count: int,
                               steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create an error response dictionary.

        Args:
            error: Error message.
            reactions_count: Number of reactions extracted before error.
            steps: Pipeline step records.

        Returns:
            Error response dictionary.
        """
        return {
            "status": STATUS_ERROR,
            "error": error,
            "reactions_count": reactions_count,
            "pipeline_steps": steps,
        }


# Parser and validator functions (would be imported in production)


def parse_markdown(text: str, source_file: str) -> List[Dict[str, Any]]:
    """Parse Markdown text to extract enzyme reactions.

    Args:
        text: Markdown content.
        source_file: Source file path for attribution.

    Returns:
        List of reaction dictionaries.
    """
    # Placeholder - actual implementation would parse markdown
    return []


def validate_reaction(reaction: Dict[str, Any]) -> List[str]:
    """Validate a reaction dictionary.

    Args:
        reaction: Reaction dictionary to validate.

    Returns:
        List of validation issues (empty if valid).
    """
    # Placeholder - actual implementation would validate reaction structure
    return []


class ExtractionOutput(BaseModel):
    """Output model for extraction results."""

    reactions: List[Dict[str, Any]] = []
    pipeline_steps: List[Dict[str, Any]] = []
    validations: List[str] = []
    errors: List[str] = []


def build_output(
    reactions: List[Dict[str, Any]],
    steps: List[Dict[str, Any]],
    validations: List[str],
    errors: List[str],
) -> ExtractionOutput:
    """Build output model from extraction results.

    Args:
        reactions: List of extracted reactions.
        steps: Pipeline step records.
        validations: Validation messages.
        errors: Error messages.

    Returns:
        ExtractionOutput model.
    """
    return ExtractionOutput(reactions=reactions,
                            pipeline_steps=steps,
                            validations=validations,
                            errors=errors)
