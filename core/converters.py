import inspect
import typing
from copy import deepcopy
from typing import Annotated, Any, Optional, Tuple, Type

from pydantic import BaseModel, Field, create_model
from pydantic._internal._generics import PydanticGenericMetadata
from pydantic._internal._model_construction import ModelMetaclass
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined, PydanticUndefinedType


class UnitValue(BaseModel):
    unit: str
    value: int | float


class UnitValuePercent(UnitValue):
    usage_percent: Annotated[float, Field(ge=0, le=1)]


filesystem_units = ["B", "KB", "MB", "GB", "TB"]


def convert_bytes(size: int) -> UnitValue:
    for unit in filesystem_units:
        if size < 1024:
            return UnitValue(
                unit=unit, value=size if unit == "B" else float(f"{size:.1f}")
            )

        size >>= 10

    else:
        return UnitValue(unit=unit, value=float(f"{size:.1f}"))


def make_field_optional(field: FieldInfo, default: Any = None) -> Tuple[Any, FieldInfo]:
    new = deepcopy(field)
    if not isinstance(field.default, PydanticUndefinedType):
        new.default = field.default
    else:
        new.default = default
    new.annotation = Optional[field.annotation]  # type: ignore
    return (new.annotation, new)


def make_model_optional[BaseModelT](
    name: str, model: Type[BaseModelT]
) -> Type[BaseModelT]:
    return create_model(
        name,
        __base__=model,
        __module__=model.__module__,
        **{  # type: ignore
            field_name: make_field_optional(field_info)
            for field_name, field_info in model.model_fields.items()
        },
    )


class ModelOptionalMeta(ModelMetaclass):
    def __new__(
        mcs,  # noqa: N804
        cls_name: str,
        bases: tuple[type[typing.Any], ...],
        namespace: dict[str, typing.Any],
        __pydantic_generic_metadata__: typing.Optional[PydanticGenericMetadata] = None,
        __pydantic_reset_parent_namespace__: bool = True,
        _create_model_module: typing.Optional[str] = None,
        **kwargs: typing.Any,
    ) -> type:
        if len(bases) > 1:
            raise NotImplementedError(
                "`MakeOptional` can't work with more then one base class"
            )
        if not bases or not issubclass(bases[0], pd.BaseModel):
            raise TypeError("Must be inherited from pydantic.BaseModel")

        annotations: dict[str, object] = {}

        for base in inspect.getmro(bases[0]):
            if not issubclass(base, pd.BaseModel):
                continue

            annotations.update(getattr(base, "__annotations__", {}))
            for field_name in getattr(base, "__annotations__", {}):
                if field_name.startswith("__"):
                    continue
                field_info = base.model_fields.get(field_name)
                if not field_info:
                    continue
                field_info.annotation = typing.Optional[field_info.annotation]  # type: ignore
                new_annotation = field_info.rebuild_annotation()
                new_field = FieldInfo.from_annotation(field_info.rebuild_annotation())
                if new_field.default is PydanticUndefined:
                    new_field.default = None
                annotations[field_name] = new_annotation
                setattr(base, field_name, new_field)
        namespace["__annotations__"] = annotations
        return super().__new__(
            mcs,
            cls_name,
            bases,
            namespace,
            __pydantic_generic_metadata__,
            __pydantic_reset_parent_namespace__,
            _create_model_module,
            **kwargs,
        )
