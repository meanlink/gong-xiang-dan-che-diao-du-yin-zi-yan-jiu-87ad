from pydantic import BaseModel, Field


class StationInitial(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    initial_bikes: int = Field(ge=0, le=1000000)


class TransferInput(BaseModel):
    job_id: int
    origin: str = Field(min_length=1, max_length=120)
    destination: str = Field(min_length=1, max_length=120)
    quantity: int = Field(ge=1, le=100000)
    stations: list[StationInitial] = Field(min_length=1, max_length=20)


class TransferBatchInput(BaseModel):
    batch_key: str = Field(min_length=1, max_length=120)
    quantity: int = Field(ge=1, le=100000)
