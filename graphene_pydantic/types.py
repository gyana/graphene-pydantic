import typing

import pydantic

import graphene
from graphene.types.objecttype import ObjectTypeOptions
from graphene.types.utils import yank_fields_from_attrs

from .registry import get_global_registry, Registry
from .converters import convert_pydantic_field


class PydanticObjectTypeOptions(ObjectTypeOptions):
    # TODO:
    # It's not clear what purpose this serves within Graphene, or whether
    # it'd be meaningful to construct this from the pydantic.Config associated
    # with a given model
    pass


def construct_fields(
    obj_type: "PydanticObjectType",
    model: pydantic.BaseModel,
    registry: Registry,
    only_fields: typing.Tuple[str],
    exclude_fields: typing.Tuple[str],
) -> typing.Dict[str, graphene.Field]:
    """
    Construct all the fields for a PydanticObjectType.

    Currently simply fetches all the attributes from the Pydantic model's __fields__. In
    the future we hope to implement field-level overrides that we'll have to merge in.
    """
    fields = {}
    for name, field in model.__fields__.items():
        converted = convert_pydantic_field(
            field,
            registry,
        )
        registry.register_orm_field(obj_type, name, field)
        fields[name] = converted
    return fields


# TODO: implement an OverrideField


class PydanticObjectType(graphene.ObjectType):
    @classmethod
    def __init_subclass_with_meta__(
        cls,
        model=None,
        registry=None,
        skip_registry=False,
        only_fields=(),
        exclude_fields=(),
        interfaces=(),
        id=None,
        _meta=None,
        **options,
    ):
        assert issubclass(
            model, pydantic.BaseModel
        ), f'You need to pass a valid Pydantic model in {cls.__name__}.Meta, received "{model}"'

        if not registry:
            registry = get_global_registry()

        assert isinstance(
            registry, Registry
        ), f'The attribute registry in {cls.__name__} needs to be an instance of Registry, received "{registry}".'

        if only_fields and exclude_fields:
            raise ValueError(
                "The options 'only_fields' and 'exclude_fields' cannot be both set on the same type."
            )

        pydantic_fields = yank_fields_from_attrs(
            construct_fields(
                obj_type=cls,
                model=model,
                registry=registry,
                only_fields=only_fields,
                exclude_fields=exclude_fields,
            ),
            _as=graphene.Field,
            sort=False,
        )

        if not _meta:
            _meta = PydanticObjectTypeOptions(cls)

        _meta.model = model
        _meta.registry = registry

        if _meta.fields:
            _meta.fields.update(pydantic_fields)
        else:
            _meta.fields = pydantic_fields

        _meta.id = id or "id"

        # TODO: We don't currently do anything with interfaces, and it would
        # be great to handle them as well. Some options include:
        # - throwing an error if they're present, because we _can't_ handle them
        # - finding a model class with that name and generating an interface
        #   from it
        # - using the nearest common ancestor of multiple types in a Union

        super().__init_subclass_with_meta__(
            _meta=_meta, interfaces=interfaces, **options
        )

        if not skip_registry:
            registry.register(cls)
