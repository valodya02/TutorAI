from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Level = Literal["начинающий", "средний", "продвинутый"]
ShortText = Annotated[str, Field(min_length=1, max_length=300)]


class Goal(BaseModel):
    goal: str = Field(min_length=1, max_length=500)
    level: Level = "начинающий"

    @field_validator("goal")
    @classmethod
    def goal_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Введите цель обучения")
        return value


class BookGoal(Goal):
    book_id: str = Field(pattern=r"^[0-9a-f]{8}$")


class TopicRequest(Goal):
    size: str = Field(default="", max_length=20)
    topics: list[ShortText] = Field(max_length=30)
    topic: ShortText
    summary: str = Field(default="", max_length=1000)


class ModuleBook(BaseModel):
    section: int
    page_start: int
    page_end: int


class ModuleRequest(Goal):
    topic: ShortText
    modules: list[ShortText] = Field(max_length=30)
    module: ShortText | dict = Field(default="", max_length=500)
    summary: str = Field(default="", max_length=1000)
    kind: str = Field(default="concept", max_length=20)
    also: str = Field(default="", max_length=20)


class Course(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=1, max_length=500)
    level: Level
    plan: dict = Field(max_length=200)

    @field_validator("goal")
    @classmethod
    def course_goal_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Введите цель обучения")
        return value

    @model_validator(mode="after")
    def limit_serialized_plan(self):
        import json

        if len(json.dumps(self.plan, ensure_ascii=False).encode("utf-8")) > 200_000:
            raise ValueError("План курса слишком велик (максимум 200 КБ)")
        return self


# Одна JSON-запись не должна занимать больше 256 КБ даже с полями-обёртками.
MAX_COURSE_BYTES = 256_000
