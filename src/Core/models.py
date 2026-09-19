from sqlalchemy import Column, DateTime
from sqlalchemy.sql import func


class Timestamp:
    CreatedAt=Column(DateTime(timezone=True), server_default=func.now(),nullable=False)
    UpdateAt=Column(DateTime(timezone=True),server_default=func.now(), onupdate=func.now(),nullable=False)