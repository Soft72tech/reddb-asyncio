from library.core.database.postgres import AsyncPostgresDatabase
from sqlmodel import MetaData

__all__ = ["AsyncPostgresDatabase"]


def merge_metadata(*original_metadata) -> MetaData:
    merged = MetaData()

    for original_metadatum in original_metadata:
        for table in original_metadatum.tables.values():
            table.to_metadata(merged)

    return merged
