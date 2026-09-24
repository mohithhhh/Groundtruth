from typing import Literal, Optional

from pydantic import BaseModel, Field


class Claim(BaseModel):
    id: str = Field(description="Matches the placeholder token used in narrative, e.g. id 'c1' for the token {c1}.")
    text: str = Field(
        description=(
            "The exact text that replaces the placeholder in the rendered narrative. For a "
            "number, round it to a sensible display precision (e.g. '1.02', not the raw "
            "full-precision value) and this must match value below."
        )
    )
    kind: Literal["entity", "number"]
    value: Optional[float] = Field(default=None, description="Required whenever kind is 'number' -- the tool's raw numeric value, unrounded. Omit only for kind 'entity'.")
    unit: Optional[str] = Field(default=None, description="Required when kind is 'number', e.g. '°C'.")
    tool_result_id: str = Field(description="The exact tool_result_id returned by the tool call this claim cites.")
    path: str = Field(description="Path into that tool result's data, e.g. 'data[0].ward_name' or 'data.lst_mean_c'.")


class Answer(BaseModel):
    narrative: str = Field(
        description=(
            "Plain flowing prose sentences -- never a numbered or bulleted list, and never any "
            "digit used as a list marker or ordinal (no '1.', '2)', 'first,', etc.), because a "
            "verifier scans for every digit in this text and anything not inside a placeholder "
            "token is treated as an unverified figure. Every single number or ward name must "
            "appear as a placeholder token shaped like open-curly-brace, the letter c, a digit, "
            "close-curly-brace -- for example the token {c1} -- never written directly as text. "
            "Each such token must have a matching entry in claims."
        )
    )
    claims: list[Claim] = Field(description="One entry per placeholder token used in narrative.")
    highlight_ward_keys: list[str] = Field(default_factory=list, description="ward_key values most relevant to the answer.")
