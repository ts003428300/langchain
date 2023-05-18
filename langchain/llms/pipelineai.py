"""Wrapper around Pipeline Cloud API."""
import logging
from typing import Any, Dict, List, Mapping, Optional

from pydantic import BaseModel, Extra, Field, root_validator

from langchain.callbacks.manager import CallbackManagerForLLMRun
from langchain.llms.base import StrInStrOutLLM
from langchain.llms.utils import enforce_stop_tokens
from langchain.utils import get_from_dict_or_env

logger = logging.getLogger(__name__)


class PipelineAI(StrInStrOutLLM, BaseModel):
    """Wrapper around PipelineAI large language models.

    To use, you should have the ``pipeline-ai`` python package installed,
    and the environment variable ``PIPELINE_API_KEY`` set with your API key.

    Any parameters that are valid to be passed to the call can be passed
    in, even if not explicitly saved on this class.

    Example:
        .. code-block:: python
            from langchain import PipelineAI
            pipeline = PipelineAI(pipeline_key="")
    """

    pipeline_key: str = ""
    """The id or tag of the target pipeline"""

    pipeline_kwargs: Dict[str, Any] = Field(default_factory=dict)
    """Holds any pipeline parameters valid for `create` call not
    explicitly specified."""

    pipeline_api_key: Optional[str] = None

    class Config:
        """Configuration for this pydantic config."""

        extra = Extra.forbid

    @root_validator(pre=True)
    def build_extra(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        """Build extra kwargs from additional params that were passed in."""
        all_required_field_names = {field.alias for field in cls.__fields__.values()}

        extra = values.get("pipeline_kwargs", {})
        for field_name in list(values):
            if field_name not in all_required_field_names:
                if field_name in extra:
                    raise ValueError(f"Found {field_name} supplied twice.")
                logger.warning(
                    f"""{field_name} was transfered to pipeline_kwargs.
                    Please confirm that {field_name} is what you intended."""
                )
                extra[field_name] = values.pop(field_name)
        values["pipeline_kwargs"] = extra
        return values

    @root_validator()
    def validate_environment(cls, values: Dict) -> Dict:
        """Validate that api key and python package exists in environment."""
        pipeline_api_key = get_from_dict_or_env(
            values, "pipeline_api_key", "PIPELINE_API_KEY"
        )
        values["pipeline_api_key"] = pipeline_api_key
        return values

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        """Get the identifying parameters."""
        return {
            **{"pipeline_key": self.pipeline_key},
            **{"pipeline_kwargs": self.pipeline_kwargs},
        }

    @property
    def _llm_type(self) -> str:
        """Return type of llm."""
        return "pipeline_ai"

    def _generate_str_in_str_out(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
    ) -> str:
        """Call to Pipeline Cloud endpoint."""
        try:
            from pipeline import PipelineCloud
        except ImportError:
            raise ValueError(
                "Could not import pipeline-ai python package. "
                "Please install it with `pip install pipeline-ai`."
            )
        client = PipelineCloud(token=self.pipeline_api_key)
        params = self.pipeline_kwargs or {}

        run = client.run_pipeline(self.pipeline_key, [prompt, params])
        try:
            text = run.result_preview[0][0]
        except AttributeError:
            raise AttributeError(
                f"A pipeline run should have a `result_preview` attribute."
                f"Run was: {run}"
            )
        if stop is not None:
            # I believe this is required since the stop tokens
            # are not enforced by the pipeline parameters
            text = enforce_stop_tokens(text, stop)
        return text
