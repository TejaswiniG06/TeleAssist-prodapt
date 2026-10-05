"""Validated HTTP inputs shared by both service modes."""
from typing import Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from teleassist.resolution.pipeline import Classification


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000)
    mode: Literal['keyword', 'semantic', 'hybrid'] = 'hybrid'
    query_mode: Literal['raw', 'enriched'] = 'raw'
    classification: Classification | None = None
    limit: int = Field(default=4, ge=1, le=20)
    min_semantic_score: float = Field(default=0.30, ge=0, le=1)
    product: str | None = None
    record_type: Literal['article', 'resolved_ticket', 'unverified_ticket', 'unresolved_ticket'] | None = None
    exclude_source_ids: list[str] = Field(default_factory=list, max_length=50)

    expected_index_version: int | None = Field(default=None, ge=1)

    @field_validator('query')
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError('Query must not be blank.')
        return value

    @model_validator(mode='after')
    def enrichment_input(self):
        if self.query_mode == 'enriched' and self.classification is None:
            raise ValueError('Enriched search requires an existing classification; search never calls the LLM.')
        return self



class ResolveRequest(BaseModel):
    complaint: str = Field(min_length=1, max_length=5000)
    observations: str = Field(default='', max_length=3000)
    exclude_source_ids: list[str] = Field(default_factory=list, max_length=50)
    query_mode: Literal['raw', 'enriched'] = 'enriched'

    @field_validator('complaint')
    @classmethod
    def not_blank(cls, value):
        if not value.strip():
            raise ValueError('Complaint must not be blank.')
        return value



class TopicObservation(BaseModel):
    complaint: str = Field(min_length=10, max_length=5000)

