# SPDX-FileCopyrightText: Copyright (c) 2026, NVIDIA CORPORATION & AFFILIATES.
# All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Enforce column and row access policies on SQL before it reaches a database.

Enforcement sits on the connector (:class:`PolicyEnforcingConnector`), not in
any one agent: the chat pipeline issues SQL from several places — the answer
query, value probes, empty-result repair — and a policy that only guarded the
answer query would leak through the probes into the model's context.

The rules, per statement, for a non-admin caller:

* **Column policy** — a restricted column may not be read. A statement that
  references a table carrying one is rejected when it names the column anywhere
  (select list, filter, join, ordering) or projects ``*`` over it. Names are
  compared without regard to which table they qualify, so a same-named column
  on another table is refused too: the check errs towards refusing.
* **Row policy** — each reference to a table carrying row policies is replaced
  by a subquery over that table filtered to the rows the caller may see (the OR
  of their policies' predicates, or nothing at all when none applies).
* **Mask policy** — a table carrying masked columns is read through a subquery
  that lists every column, the masked ones replaced by a masking expression
  under their own name, so every later use of the column — select list,
  grouping, filters, joins — sees only the masked value. A row policy on the
  same table goes into the same subquery.

Anything that cannot be analysed with certainty is refused rather than run:
unparseable SQL, more than one statement, or a policy table the SQL reaches by a
path the rewrite could not account for.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

import pandas as pd
import sqlglot
from sqlglot import exp

from auto_ontology.connectors.base import SQLDatabase

DECISION_ALLOWED = "allowed"
DECISION_FILTERED = "filtered"
DECISION_BLOCKED = "blocked"


class AccessDeniedError(PermissionError):
    """A statement was refused by an access policy. The message is user-facing."""


@dataclass(frozen=True)
class ColumnRule:
    policy_id: str
    database: str
    schema: str
    table: str
    column: str


@dataclass(frozen=True)
class RowRule:
    """The rows of one table a caller may see; ``predicate`` None means none."""

    policy_ids: tuple[str, ...]
    database: str
    schema: str
    table: str
    predicate: Optional[str]


#: Masking styles, chosen per column (see :func:`detect_mask_style`).
MASK_STYLES = ("phone", "email", "id_number", "name", "address", "partial", "full")


@dataclass(frozen=True)
class MaskRule:
    """Show *column* of one table masked in *style*.

    ``columns`` is the table's whole column list, in order: the subquery that
    masks one column has to project the others unchanged, and a table whose
    columns are unknown cannot be read safely at all.
    """

    policy_id: str
    database: str
    schema: str
    table: str
    column: str
    style: str
    columns: tuple[str, ...]


@dataclass
class AccessContext:
    """The policies that bind one caller, already resolved for their groups.

    Plain data so it crosses the chat worker's process boundary as a dict
    (:meth:`to_dict` / :meth:`from_dict`).
    """

    is_admin: bool = False
    columns: list[ColumnRule] = field(default_factory=list)
    rows: list[RowRule] = field(default_factory=list)
    masks: list[MaskRule] = field(default_factory=list)

    @property
    def unrestricted(self) -> bool:
        return self.is_admin or (not self.columns and not self.rows and not self.masks)

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_admin": self.is_admin,
            "columns": [vars(c) for c in self.columns],
            "rows": [{**vars(r), "policy_ids": list(r.policy_ids)} for r in self.rows],
            "masks": [{**vars(m), "columns": list(m.columns)} for m in self.masks],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "AccessContext":
        if not data:
            return cls()
        return cls(
            is_admin=bool(data.get("is_admin")),
            columns=[ColumnRule(**c) for c in data.get("columns") or []],
            rows=[
                RowRule(**{**r, "policy_ids": tuple(r.get("policy_ids") or ())})
                for r in data.get("rows") or []
            ],
            masks=[
                MaskRule(**{**m, "columns": tuple(m.get("columns") or ())})
                for m in data.get("masks") or []
            ],
        )

    def for_database(self, database: str | None) -> "AccessContext":
        """The rules that apply to tables in *database* (case-insensitive)."""
        db = (database or "").casefold()
        return AccessContext(
            is_admin=self.is_admin,
            columns=[c for c in self.columns if c.database.casefold() == db],
            rows=[r for r in self.rows if r.database.casefold() == db],
            masks=[m for m in self.masks if m.database.casefold() == db],
        )


@dataclass
class Enforcement:
    sql: str
    decision: str
    reason: str = ""
    policy_ids: list[str] = field(default_factory=list)


def _fold(value: str | None) -> str:
    return (value or "").strip().strip('"`[]').casefold()


def _matches(table: exp.Table, schema: str, name: str, database: str) -> bool:
    """Whether a table reference in the SQL is the policy's table.

    The name must match; each qualifier the SQL spells out must match too. An
    unqualified reference matches by name alone — the connector's default
    schema decides what it resolves to, and erring towards matching keeps the
    policy applied.
    """
    if _fold(table.name) != _fold(name):
        return False
    if table.db and _fold(table.db) != _fold(schema):
        return False
    if table.catalog and _fold(table.catalog) != _fold(database):
        return False
    return True


def _cte_names(tree: exp.Expression) -> set[str]:
    return {_fold(cte.alias) for cte in tree.find_all(exp.CTE) if cte.alias}


def _real_tables(tree: exp.Expression) -> list[exp.Table]:
    """Table references that read a relation, i.e. not a CTE by name."""
    ctes = _cte_names(tree)
    return [
        t
        for t in tree.find_all(exp.Table)
        if t.name and not (not t.db and _fold(t.name) in ctes)
    ]


def _projects_star(tree: exp.Expression) -> bool:
    """Whether any SELECT list contains ``*`` or ``t.*`` (not ``COUNT(*)``)."""
    for select in tree.find_all(exp.Select):
        for projection in select.expressions:
            if isinstance(projection, exp.Star):
                return True
            if isinstance(projection, exp.Column) and isinstance(
                projection.this, exp.Star
            ):
                return True
    return False


def _referenced_columns(tree: exp.Expression) -> set[str]:
    return {_fold(c.name) for c in tree.find_all(exp.Column) if c.name}


def _parse(sql: str, dialect: str | None) -> exp.Expression:
    statements = [s for s in sqlglot.parse(sql, read=dialect or None) if s is not None]
    if len(statements) != 1:
        raise ValueError(f"expected one statement, got {len(statements)}")
    return statements[0]


def _row_condition(rule: RowRule, dialect: str | None) -> exp.Expression:
    if rule.predicate is None:
        return exp.false()
    return sqlglot.parse_one(rule.predicate, read=dialect or None)


_MASK_NAME_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("phone", ("phone", "mobile", "tel", "cell", "手机", "电话")),
    ("email", ("email", "e_mail", "mail", "邮箱")),
    (
        "id_number",
        (
            "id_card",
            "idcard",
            "id_no",
            "id_number",
            "ssn",
            "passport",
            "身份证",
            "证件",
        ),
    ),
    ("address", ("address", "addr", "地址")),
    ("name", ("name", "姓名", "名字")),
)


def detect_mask_style(column: str) -> str:
    """The masking style that fits *column*, by its name.

    Checked in order, so ``contact_phone`` is a phone and ``customer_name`` a
    name; anything unrecognised keeps its first and last character.
    """
    lowered = column.casefold()
    for style, needles in _MASK_NAME_PATTERNS:
        if any(n in lowered for n in needles):
            return style
    return "partial"


def _lit(value: Any) -> exp.Expression:
    return (
        exp.Literal.number(value)
        if isinstance(value, int)
        else exp.Literal.string(value)
    )


def _substr(text: exp.Expression, start: Any, length: Any) -> exp.Expression:
    start = start if isinstance(start, exp.Expression) else _lit(start)
    return exp.Substring(this=text.copy(), start=start, length=_lit(length))


def _concat(*parts: exp.Expression) -> exp.Expression:
    return exp.Concat(expressions=list(parts), safe=True, coalesce=False)


def mask_expression(column: str, style: str) -> exp.Expression:
    """A dialect-neutral expression showing *column* masked in *style*.

    Built as a sqlglot tree so each dialect renders its own spelling of
    SUBSTRING / LENGTH / POSITION. NULL stays NULL; a value too short for the
    style is replaced outright rather than half-shown.
    """
    col = exp.column(column, quoted=True)
    text = exp.cast(col.copy(), "VARCHAR")
    length = exp.Length(this=text.copy())

    def tail(n: int) -> exp.Expression:
        return _substr(text, exp.Sub(this=length.copy(), expression=_lit(n - 1)), n)

    def when_longer(n: int, then: exp.Expression, otherwise: str) -> exp.Expression:
        return (
            exp.case()
            .when(exp.GT(this=length.copy(), expression=_lit(n)), then)
            .else_(_lit(otherwise))
        )

    if style == "phone":
        masked = when_longer(
            6, _concat(_substr(text, 1, 3), _lit("****"), tail(4)), "****"
        )
    elif style == "email":
        at = exp.StrPosition(this=text.copy(), substr=_lit("@"))
        masked = (
            exp.case()
            .when(
                exp.GT(this=at, expression=_lit(1)),
                _concat(
                    _substr(text, 1, 1),
                    _lit("***"),
                    exp.Substring(this=text.copy(), start=at.copy()),
                ),
            )
            .else_(_lit("***"))
        )
    elif style == "id_number":
        masked = when_longer(
            8, _concat(_substr(text, 1, 4), _lit("**********"), tail(4)), "****"
        )
    elif style == "name":
        masked = _concat(_substr(text, 1, 1), _lit("**"))
    elif style == "address":
        masked = _concat(_substr(text, 1, 6), _lit("****"))
    elif style == "full":
        masked = _lit("******")
    else:
        masked = when_longer(
            2, _concat(_substr(text, 1, 1), _lit("***"), tail(1)), "***"
        )
    return (
        exp.case()
        .when(exp.Is(this=col.copy(), expression=exp.null()), exp.null())
        .else_(masked)
    )


def _masked_projection(masks: list[MaskRule]) -> list[exp.Expression]:
    """Every column of the masked table, the masked ones under their own name."""
    styles = {_fold(m.column): m.style for m in masks}
    projection: list[exp.Expression] = []
    for name in masks[0].columns:
        style = styles.get(_fold(name))
        if style is None:
            projection.append(exp.column(name, quoted=True))
        else:
            projection.append(
                exp.alias_(mask_expression(name, style), name, quoted=True)
            )
    return projection


def validate_predicate(predicate: str, dialect: str | None = None) -> str | None:
    """``None`` when *predicate* is a usable row filter, else why it is not."""
    try:
        parsed = sqlglot.parse_one(predicate, read=dialect or None)
    except Exception as exc:  # noqa: BLE001 - surfaced to the admin form
        return f"无法解析过滤条件：{exc}"
    if isinstance(parsed, (exp.Select, exp.Union, exp.Insert, exp.Update, exp.Delete)):
        return "过滤条件只能是一个布尔表达式，例如 province = '浙江'"
    if parsed.find(exp.Select):
        return "过滤条件中不能包含子查询"
    return None


def enforce_sql(sql: str, dialect: str | None, ctx: AccessContext) -> Enforcement:
    """Check and rewrite one statement for *ctx*'s policies (one database's)."""
    if ctx.unrestricted:
        return Enforcement(sql=sql, decision=DECISION_ALLOWED)

    try:
        tree = _parse(sql, dialect)
    except Exception:  # noqa: BLE001 - unparseable SQL is refused, not guessed at
        return Enforcement(
            sql=sql,
            decision=DECISION_BLOCKED,
            reason="查询语句无法解析，出于数据权限保护未执行。",
        )

    tables = _real_tables(tree)

    # Columns first: a refused statement must not be rewritten and run.
    referenced = _referenced_columns(tree)
    star = _projects_star(tree)
    denied: list[ColumnRule] = []
    for rule in ctx.columns:
        if not any(_matches(t, rule.schema, rule.table, rule.database) for t in tables):
            continue
        if star or _fold(rule.column) in referenced:
            denied.append(rule)
    if denied:
        names = "、".join(sorted({f"{r.table}.{r.column}" for r in denied}))
        hint = "（查询使用了 *，请改为列出具体字段）" if star else ""
        return Enforcement(
            sql=sql,
            decision=DECISION_BLOCKED,
            reason=f"你没有权限查看以下字段：{names}{hint}",
            policy_ids=sorted({r.policy_id for r in denied}),
        )

    applied: list[str] = []
    for table in tables:
        row = next(
            (r for r in ctx.rows if _matches(table, r.schema, r.table, r.database)),
            None,
        )
        masks = [m for m in ctx.masks if _matches(table, m.schema, m.table, m.database)]
        if row is None and not masks:
            continue
        if masks and not masks[0].columns:
            return Enforcement(
                sql=sql,
                decision=DECISION_BLOCKED,
                reason=f"无法确定 {table.name} 的字段列表，出于脱敏保护未执行。",
                policy_ids=sorted({m.policy_id for m in masks}),
            )
        projection = _masked_projection(masks) if masks else [exp.Star()]
        inner = table.copy()
        inner.set("alias", None)
        select = exp.select(*projection).from_(inner)
        if row is not None:
            select = select.where(_row_condition(row, dialect))
            applied.extend(row.policy_ids)
        applied.extend(m.policy_id for m in masks)
        table.replace(
            exp.Subquery(
                this=select,
                alias=exp.TableAlias(this=exp.to_identifier(table.alias or table.name)),
            )
        )

    if not applied:
        return Enforcement(sql=sql, decision=DECISION_ALLOWED)
    return Enforcement(
        sql=tree.sql(dialect=dialect or None),
        decision=DECISION_FILTERED,
        policy_ids=sorted(set(applied)),
    )


def hide_restricted_columns(
    tables: Iterable[dict[str, Any]], ctx: AccessContext
) -> list[dict[str, Any]]:
    """*tables* (``relevant_tables`` dicts) without columns *ctx* may not read.

    Keeps the generator from reaching for a column the connector would refuse:
    what the model never sees, it does not try to select.
    """
    tables = list(tables)
    if ctx.unrestricted or not ctx.columns:
        return tables
    out = []
    for table in tables:
        hidden = {
            _fold(r.column)
            for r in ctx.columns
            if _fold(r.table) == _fold(table.get("name"))
            and _fold(r.schema) == _fold(table.get("schema_name"))
            and _fold(r.database) == _fold(table.get("database_name"))
        }
        if hidden:
            table = {
                **table,
                "columns": [
                    c
                    for c in table.get("columns") or []
                    if _fold(c.get("name")) not in hidden
                ],
            }
        out.append(table)
    return out


class PolicyEnforcingConnector(SQLDatabase):
    """A connector that runs every statement through :func:`enforce_sql`.

    Delegates everything else to the wrapped connector. ``log`` receives one
    entry per statement — what was asked, what ran, and what the policy layer
    did — which the chat worker attaches to the answer for the audit trail.
    """

    def __init__(  # noqa: D107 - see class docstring
        self, inner: SQLDatabase, ctx: AccessContext, log: list[dict[str, Any]]
    ) -> None:
        self._inner = inner
        self._ctx = ctx.for_database(inner.database_name)
        self._log = log

    # Class attributes on SQLDatabase would shadow __getattr__, so the two the
    # pipeline reads are forwarded explicitly.
    @property
    def supports_statement_timeout(self) -> bool:  # type: ignore[override]
        return bool(getattr(self._inner, "supports_statement_timeout", False))

    @property
    def table_filter(self):  # type: ignore[override]
        return getattr(self._inner, "table_filter", None)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def execute(self, sql: str, parameters: Optional[list] = None, **kwargs: Any):
        result = enforce_sql(sql, self._inner.dialect, self._ctx)
        self._log.append(
            {
                "database": self._inner.database_name,
                "sql": sql,
                "executed_sql": None
                if result.decision == DECISION_BLOCKED
                else result.sql,
                "decision": result.decision,
                "reason": result.reason,
                "policy_ids": result.policy_ids,
            }
        )
        if result.decision == DECISION_BLOCKED:
            raise AccessDeniedError(result.reason)
        if parameters is None:
            return self._inner.execute(result.sql, **kwargs)
        return self._inner.execute(result.sql, parameters, **kwargs)

    def get_tables(self) -> pd.DataFrame:
        return self._inner.get_tables()

    def get_columns(self) -> pd.DataFrame:
        return self._inner.get_columns()

    def get_queries(self, hours: int = 24) -> pd.DataFrame:
        return self._inner.get_queries(hours)

    def get_views(self) -> pd.DataFrame:
        return self._inner.get_views()

    def get_pks(self) -> pd.DataFrame:
        return self._inner.get_pks()

    def get_fks(self) -> pd.DataFrame:
        return self._inner.get_fks()

    @property
    def dialect(self) -> str:
        return self._inner.dialect

    @property
    def database_name(self) -> str:
        return self._inner.database_name

    def qualify(self, schema: Optional[str], table: str) -> str:
        return self._inner.qualify(schema, table)

    def close(self) -> None:
        self._inner.close()


def wrap_connectors(
    connectors: list[SQLDatabase], ctx: AccessContext, log: list[dict[str, Any]]
) -> list[SQLDatabase]:
    """*connectors* behind policy enforcement.

    Wrapped for an admin too: nothing is checked or rewritten for them, but
    what they ran still belongs in the audit trail.
    """
    return [PolicyEnforcingConnector(c, ctx, log) for c in connectors]


def summarize(log: list[dict[str, Any]]) -> dict[str, Any]:
    """One audit verdict for a question from its per-statement *log*."""
    decisions = {entry["decision"] for entry in log}
    if DECISION_BLOCKED in decisions:
        decision = DECISION_BLOCKED
    elif DECISION_FILTERED in decisions:
        decision = DECISION_FILTERED
    else:
        decision = DECISION_ALLOWED
    reasons = [e["reason"] for e in log if e.get("reason")]
    return {
        "decision": decision,
        "reason": reasons[-1] if reasons else "",
        "policy_ids": sorted({p for e in log for p in e.get("policy_ids") or []}),
        "statements": log,
    }
