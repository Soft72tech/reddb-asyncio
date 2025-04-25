# TODO: investigate server side cursors
# TODO: connection characreristic


import importlib
from typing import Type
from sqlalchemy.engine import URL, Dialect, default
from sqlalchemy.sql import sqltypes

from sqlalchemy.connectors.asyncio import (
    AsyncAdapt_dbapi_connection,
    AsyncAdapt_dbapi_cursor,
    AsyncAdapt_dbapi_ss_cursor,
)
from sqlalchemy.engine import reflection
from sqlalchemy.sql import compiler
from sqlalchemy.util.concurrency import await_


class FirebirdCompiler(compiler.SQLCompiler):
    def render_bind_cast(self, type_, dbapi_type, sqltext) -> str:
        return f"""CAST({sqltext}) AS {
            self.dialect.type_compiler_instance.process(
                dbapi_type, identifier_preparer=self.preparer
            )
        }"""

    def visit_empty_set_expr(self, element_types, **kwargs) -> str:
        return "SELECT 1 FROM rdb$database WHERE 1 != 1"

    def default_from(self) -> str:
        return " FROM rdb$database"

    def for_update_clause(self, select, **kw):
        for_update_clause = super().for_update_clause(select, **kw)

        if select._for_update_args.nowait:
            for_update_clause = f"{for_update_clause} WITH LOCK"

        if select._for_update_args.skip_locked:
            for_update_clause = f"{for_update_clause} WITH LOCK SKIP LOCKED"

        return for_update_clause

    def visit_sequence(self, sequence, **kwargs) -> str:
        return f"GEN_ID({self.preparer.format_sequence(sequence)}, 1)"

    def visit_substring_func(self, func, **kwargs) -> str:
        s = self.process(func.clauses.clauses[0], **kwargs)
        start = self.process(func.clauses.clauses[1], **kwargs)

        if len(func.clauses.clauses) > 2:
            length = self.process(func.clauses.clauses[2], **kwargs)

            return f"SUBSTRING({s} FROM {start} FOR {length})"

        else:
            return f"SUBSTRING({s} FROM {start})"

    def visit_mod_binary(self, binary, operator, **kw):
        return f"MOD({self.process(binary.left, **kw)}, {self.process(binary.right, **kw)})"

    def visit_bitwise_xor_op_binary(self, binary, operator, **kw):
        return f"BIN_XOR({self.process(binary.left, **kw)}, {self.process(binary.right, **kw)})"

    def visit_now_func(self, func, **kw):
        return "CURRENT_TIMESTAMP"

    def visit_char_length_func(self, fn, **kw):
        return f"CHAR_LENGTH{self.function_argspec(fn, **kw)}"

    def visit_length_func(self, fn, **kw):
        return f"CHAR_LENGTH{self.function_argspec(fn, **kw)}"

    # TODO: check limit/offset fetch clause
    # TODO: check other possible visit_* methods with docs


class FirebirdDDLCompiler(compiler.DDLCompiler):
    # TODO: implement
    ...


class FirebirdTypeCompiler(compiler.GenericTypeCompiler):
    # TODO: implement
    ...


class FirebirdIdentifierPreparer(compiler.IdentifierPreparer):
    reserved_words = {
        "add",
        "admin",
        "all",
        "alter",
        "and",
        "any",
        "as",
        "at",
        "avg",
        "begin",
        "between",
        "bigint",
        "binary",
        "bit_length",
        "blob",
        "boolean",
        "both",
        "by",
        "case",
        "cast",
        "char",
        "char_length",
        "character",
        "character_length",
        "check",
        "close",
        "collate",
        "column",
        "comment",
        "commit",
        "connect",
        "constraint",
        "corr",
        "count",
        "covar_pop",
        "covar_samp",
        "create",
        "cross",
        "current",
        "current_connection",
        "current_date",
        "current_role",
        "current_time",
        "current_timestamp",
        "current_transaction",
        "current_user",
        "cursor",
        "date",
        "day",
        "dec",
        "decfloat",
        "decimal",
        "declare",
        "default",
        "delete",
        "deleting",
        "deterministic",
        "disconnect",
        "distinct",
        "double",
        "drop",
        "else",
        "end",
        "escape",
        "execute",
        "exists",
        "external",
        "extract",
        "false",
        "fetch",
        "filter",
        "float",
        "for",
        "foreign",
        "from",
        "full",
        "function",
        "gdscode",
        "global",
        "grant",
        "group",
        "having",
        "hour",
        "in",
        "index",
        "inner",
        "insensitive",
        "insert",
        "inserting",
        "int",
        "int128",
        "integer",
        "into",
        "is",
        "join",
        "lateral",
        "leading",
        "left",
        "like",
        "local",
        "localtime",
        "localtimestamp",
        "long",
        "lower",
        "max",
        "merge",
        "min",
        "minute",
        "month",
        "national",
        "natural",
        "nchar",
        "no",
        "not",
        "null",
        "numeric",
        "octet_length",
        "of",
        "offset",
        "on",
        "only",
        "open",
        "or",
        "order",
        "outer",
        "over",
        "parameter",
        "plan",
        "position",
        "post_event",
        "precision",
        "primary",
        "procedure",
        "publication",
        "rdb$db_key",
        "rdb$error",
        "rdb$get_context",
        "rdb$get_transaction_cn",
        "rdb$record_version",
        "rdb$role_in_use",
        "rdb$set_context",
        "rdb$system_privilege",
        "real",
        "record_version",
        "recreate",
        "recursive",
        "references",
        "regr_avgx",
        "regr_avgy",
        "regr_count",
        "regr_intercept",
        "regr_r2",
        "regr_slope",
        "regr_sxx",
        "regr_sxy",
        "regr_syy",
        "release",
        "resetting",
        "return",
        "returning_values",
        "returns",
        "revoke",
        "right",
        "rollback",
        "row",
        "row_count",
        "rows",
        "savepoint",
        "scroll",
        "second",
        "select",
        "sensitive",
        "set",
        "similar",
        "smallint",
        "some",
        "sqlcode",
        "sqlstate",
        "start",
        "stddev_pop",
        "stddev_samp",
        "sum",
        "table",
        "then",
        "time",
        "timestamp",
        "timezone_hour",
        "timezone_minute",
        "to",
        "trailing",
        "trigger",
        "trim",
        "true",
        "unbounded",
        "union",
        "unique",
        "unknown",
        "update",
        "updating",
        "upper",
        "user",
        "using",
        "value",
        "values",
        "var_pop",
        "var_samp",
        "varbinary",
        "varchar",
        "variable",
        "varying",
        "view",
        "when",
        "where",
        "while",
        "window",
        "with",
        "without",
        "year",
    }
    # TODO: implement


class FirebirdInspector(reflection.Inspector):
    dialect: "FirebirdDialect"
    # TODO: implement


class FirebirdExecutionContext(default.DefaultExecutionContext):
    # TODO: implement
    ...


# TODO: clean up redunant types
# TODO: check render_bind_cast options


class FirebirdString(sqltypes.String):
    pass


class FirebirdCHARACTER(sqltypes.CHAR):
    __visit_name__ = "CHARACTER"


class FirebirdBINARY(sqltypes.BINARY):
    # charset OCTETS
    pass


class FirebirdNCHAR(sqltypes.NCHAR):
    # charset ISO8859_1
    pass


class FirebirdVARCHAR(sqltypes.VARCHAR):
    pass


class FirebirdVARBINARY(sqltypes.VARBINARY):
    # charset OCTETS
    pass


class FirebirdNVARCHAR(sqltypes.NVARCHAR):
    # charset ISO8859_1
    pass


class FirebirdNumeric(sqltypes.Numeric):
    pass


class FirebirdFLOAT(sqltypes.FLOAT):
    pass


class FirebirdDOUBLE_PRECISION(sqltypes.DOUBLE_PRECISION):
    pass


class FirebirdDECFLOAT(FirebirdNumeric):
    __visit_name__ = "DECFLOAT"


class FirebirdREAL(sqltypes.REAL):
    pass


class FirebirdDECIMAL(sqltypes.DECIMAL):
    pass


class FirebirdDATE(sqltypes.DATE):
    pass


class FirebirdTIME(sqltypes.TIME):
    pass


class FirebirdTIMESTAMP(sqltypes.TIMESTAMP):
    pass


class FirebirdInteger(sqltypes.Integer):
    render_bind_cast = True


class FirebirdSMALLINT(sqltypes.SMALLINT):
    pass


class FirebirdINTEGER(sqltypes.INTEGER):
    pass


class FirebirdBIGINT(sqltypes.BIGINT):
    pass


class FirebirdINT128(sqltypes.Integer):
    __visit_name__ = "INT128"


class FirebirdBOOLEAN(sqltypes.BOOLEAN):
    pass


class FirebirdLargeBinary(sqltypes.LargeBinary):
    pass


class FirebirdBLOB(sqltypes.BLOB):
    # SUB_TYPE BINARY
    pass


class FirebirdTEXT(sqltypes.TEXT):
    # SUB_TYPE TEXT
    # SEGMENT SIZE {}
    __visit_name__ = "BLOB"


class FirebirdNumericInterval(sqltypes.Numeric):
    # NUMERIC(18,9)
    pass


# TODO datetime
# TODO json
# TODO uuid
# TODO interval ?
# TODO: array


class FirebirdDialect(default.DefaultDialect):
    name = "firebird"

    max_identifier_length = 63

    supports_statement_cache = True
    supports_alter = True
    supports_sane_rowcount = True
    supports_sane_multi_rowcount = False

    supports_native_boolean = True
    supports_native_decimal = True
    supports_native_enum = False
    supports_native_uuid = False

    supports_schemas = False
    supports_sequences = True
    sequences_optional = False
    supports_comments = True
    supports_default_values = True
    supports_default_metavalue = True
    supports_identity_columns = True
    supports_empty_insert = False
    supports_is_distinct_from = True

    postfetch_lastrowid = False
    use_insertmanyvalues = False
    requires_name_normalize = True

    update_returning = True
    delete_returning = True
    insert_returning = True

    execution_ctx_cls = FirebirdExecutionContext

    statement_compiler = FirebirdCompiler
    ddl_compiler = FirebirdDDLCompiler
    type_compiler_cls = FirebirdTypeCompiler
    preparer = FirebirdIdentifierPreparer

    ischema_names = {
        "bigint": sqltypes.BIGINT,
        "blob": sqltypes.BLOB,
        "boolean": sqltypes.BOOLEAN,
        "character": FirebirdCHARACTER,
        "char": sqltypes.CHAR,
        "date": sqltypes.DATE,
        "decfloat": FirebirdDECFLOAT,
        "decimal": sqltypes.DECIMAL,
        "double precision": sqltypes.DOUBLE_PRECISION,
        "float": sqltypes.FLOAT,
        "integer": sqltypes.INTEGER,
        "int": sqltypes.INT,
        "int128": FirebirdINT128,
        "numeric": sqltypes.NUMERIC,
        "real": sqltypes.REAL,
        "smallint": sqltypes.SMALLINT,
        "time": sqltypes.TIME,
        "time with time zone": sqltypes.TIME(timezone=True),
        "timestamp": sqltypes.TIMESTAMP,
        "timestamp with time zone": sqltypes.TIMESTAMP(timezone=True),
        "varbinary": FirebirdVARBINARY,
        "binary varying": FirebirdVARBINARY,
        "varchar": FirebirdVARCHAR,
        "char varying": FirebirdVARCHAR,
        "character varying": FirebirdVARCHAR,
    }

    # TODO: all colspecs
    colspecs = {
        sqltypes.BinInteger: sqltypes.BIGINT,
        sqltypes.BLOB: sqltypes.BLOB,
        sqltypes.DateTime: sqltypes.TIMESTAMP,
        sqltypes.Date: sqltypes.DATE,  # ?
        sqltypes.Time: sqltypes.TIME,
    }

    @classmethod
    def import_dbapi(cls):
        # Implemented at the driver level
        raise NotImplementedError()

    @classmethod
    def get_async_dialect_cls(cls, url: URL) -> Type[Dialect]:
        return FirebirdDialectAsync_firebirdsql

    # TODO: isolation level
    # TODO: check connection behaviors
    # TODO: readonly and deferrable


class FirebirdDialect_firebirdsql(FirebirdDialect):
    driver = "firebirdsql"

    @classmethod
    def import_dbapi(cls):
        return importlib.import_module("firebirdsql")


class AsyncAdapt_firebirdsql_ss_cursor(AsyncAdapt_dbapi_ss_cursor):
    __slots__ = ()


class AsyncAdapt_firebirdsql_cursor(AsyncAdapt_dbapi_cursor):
    __slots__ = ()


class AsyncAdapt_firebirdsql_connection(AsyncAdapt_dbapi_connection):
    __slots__ = ()

    _cursor_cls = AsyncAdapt_firebirdsql_cursor
    _ss_cursor_cls = AsyncAdapt_firebirdsql_ss_cursor

    # TODO: isolation level


class AsyncAdapt_firebirdsql_dbapi:
    def __init__(self, firebirdsql):
        self.firebirdsql = firebirdsql
        self._init_dbapi_attributes()

    def _init_dbapi_attributes(self):
        for error in (
            "Error",
            "InterfaceError",
            "DatabaseError",
            "DataError",
            "OperationalError",
            "IntegrityError",
            "InternalError",
            "ProgrammingError",
            "NotSupportedError",
        ):
            setattr(self, error, getattr(self.firebirdsql, error))

        self.firebirdsql_version = getattr(self.firebirdsql, "__version__")
        self.paramstyle = "qmark"

    def connect(self, *args, **kwargs):
        creator_fn = kwargs.pop("async_creator_fn", self.firebirdsql.aio.connect)

        return AsyncAdapt_firebirdsql_connection(
            self, await_(creator_fn(*args, **kwargs))
        )


class FirebirdExecutionContextAsync(FirebirdExecutionContext): ...


class FirebirdDialectAsync_firebirdsql(FirebirdDialect_firebirdsql):
    is_async = True

    supports_statement_cache = True
    supports_server_side_cursors = False

    execution_ctx_cls = FirebirdExecutionContextAsync

    @classmethod
    def import_dbapi(cls):
        return AsyncAdapt_firebirdsql_dbapi(importlib.import_module("firebirdsql.aio"))


dialect = FirebirdDialect_firebirdsql
dialect_async = FirebirdDialectAsync_firebirdsql
