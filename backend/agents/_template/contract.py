from pydantic import BaseModel


class TemplateInput(BaseModel):
    user_id: str


class TemplateOutput(BaseModel):
    result: str
