from pydantic import BaseModel, ConfigDict, Field


class LoginForm(BaseModel):
    model_config = ConfigDict(extra="ignore")
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(max_length=128)
