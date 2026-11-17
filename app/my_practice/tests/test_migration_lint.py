"""Guardrail: a migration may only expand the schema unless it says it is the contract step.

The suite builds its schema from the models, so a migration that drops a column the
previous release still reads, or adds a NOT NULL column the previous release never
fills, passes every test. It only fails when someone puts the older image back
against a database that has already been migrated (a rollback after a bad update),
or when the previous release is still serving while ``migrate`` runs.

A migration that does this on purpose, once no release reads the old name or column
any more, says so in a comment:

    # contract: <what the old code no longer reads, and since when>

The initial migration is exempt: no previous release exists to break.
"""

import re
from pathlib import Path

from django.db import migrations, models
from django.db.migrations.loader import MigrationLoader
from django.db.migrations.operations.base import Operation
from django.db.migrations.state import ProjectState
from django.test import SimpleTestCase

APP = "my_practice"
CONTRACT_MARKER = "# contract:"
DESTRUCTIVE_SQL = re.compile(
    r"\b(DROP\s+(TABLE|COLUMN|VIEW)|RENAME\s+(TO|COLUMN)|SET\s+NOT\s+NULL)\b", re.I
)


def _sql_text(sql) -> str:
    """RunSQL's sql: a string, or a list of strings and (sql, params) pairs."""
    if isinstance(sql, str):
        return sql
    return " ".join(s if isinstance(s, str) else s[0] for s in sql)


def _model_state(state, app: str, model_name: str):
    return state.models.get((app, model_name.lower()))


def _managed(state, app: str, model_name: str) -> bool:
    model = _model_state(state, app, model_name)
    return model is None or model.options.get("managed", True)


def breaking_changes(app: str, op: Operation, state) -> list[str]:
    """What ``op`` does to the database that the previous release can't live with.

    ``state`` is the project state just before the migration.
    """
    if isinstance(op, migrations.SeparateDatabaseAndState):
        return [p for db_op in op.database_operations for p in breaking_changes(app, db_op, state)]
    if isinstance(op, migrations.RunSQL):
        return [f"RunSQL: {m.group(0)}" for m in DESTRUCTIVE_SQL.finditer(_sql_text(op.sql))]
    model_name = (
        getattr(op, "model_name", None)
        or getattr(op, "name", None)
        or getattr(op, "old_name", None)
    )
    if model_name and not _managed(state, app, model_name):
        return []  # unmanaged: the operation only changes Django's state
    if isinstance(
        op,
        (
            migrations.RemoveField,
            migrations.DeleteModel,
            migrations.RenameField,
            migrations.RenameModel,
            migrations.AlterModelTable,
        ),
    ):
        return [op.describe()]
    if isinstance(op, migrations.AddField):
        field = op.field
        if not field.null and not field.has_db_default() and not field.many_to_many:
            # A Python-side default only backfills: Django drops it from the column
            # afterwards, and the previous release's inserts leave it out.
            return [f"{op.describe()}: NOT NULL without db_default"]
    if isinstance(op, migrations.AlterField):
        model = _model_state(state, app, op.model_name)
        old = model.fields.get(op.name) if model else None
        if old is not None:
            if old.null and not op.field.null:
                return [f"{op.describe()}: becomes NOT NULL"]
            if old.db_column != op.field.db_column:
                return [f"{op.describe()}: renames the column"]
    return []


def migration_problems(loader: MigrationLoader | None = None) -> dict[str, list[str]]:
    """``{migration name: what breaks}`` for every unmarked migration of the app."""
    loader = loader or MigrationLoader(None, ignore_no_migrations=True)
    problems: dict[str, list[str]] = {}
    for (app, name), migration in sorted(loader.disk_migrations.items()):
        if app != APP:
            continue
        module = __import__(migration.__module__, fromlist=["_"])
        if migration.initial or CONTRACT_MARKER in Path(module.__file__).read_text():
            continue
        state = loader.project_state((app, name), at_end=False)
        found: list[str] = []
        for op in migration.operations:
            found += breaking_changes(app, op, state)
            op.state_forwards(app, state)
        if found:
            problems[name] = found
    return problems


class MigrationLintTests(SimpleTestCase):
    def test_migrations_only_expand_unless_marked_as_contract(self):
        problems = migration_problems()
        self.assertFalse(
            problems,
            "These migrations would break the release still reading the old schema. Split them "
            f"into expand and contract steps, or mark the contract step with '{CONTRACT_MARKER} …':\n  "
            + "\n  ".join(f"{n}: {p}" for n, ps in problems.items() for p in ps),
        )


class BreakingChangesTests(SimpleTestCase):
    """The lint flags what the previous release can't live with, and only that."""

    @staticmethod
    def state_with_note():
        state = ProjectState()
        create = migrations.CreateModel(
            "Note",
            [
                ("id", models.AutoField(primary_key=True)),
                ("body", models.TextField(null=True)),
            ],
        )
        create.state_forwards(APP, state)
        return state

    def flagged(self, op) -> bool:
        return bool(breaking_changes(APP, op, self.state_with_note()))

    def test_flags_dropping_and_renaming(self):
        self.assertTrue(self.flagged(migrations.RemoveField("note", "body")))
        self.assertTrue(self.flagged(migrations.RenameField("note", "body", "text")))
        self.assertTrue(self.flagged(migrations.DeleteModel("Note")))

    def test_flags_a_not_null_column_without_a_database_default(self):
        self.assertTrue(
            self.flagged(
                migrations.AddField("note", "title", models.CharField(max_length=20, default=""))
            )
        )

    def test_allows_nullable_and_database_default_columns(self):
        self.assertFalse(
            self.flagged(
                migrations.AddField("note", "title", models.CharField(max_length=20, null=True))
            )
        )
        self.assertFalse(
            self.flagged(
                migrations.AddField("note", "title", models.CharField(max_length=20, db_default=""))
            )
        )

    def test_flags_a_column_that_becomes_not_null(self):
        self.assertTrue(
            self.flagged(migrations.AlterField("note", "body", models.TextField(default="")))
        )

    def test_flags_destructive_sql(self):
        self.assertTrue(self.flagged(migrations.RunSQL("ALTER TABLE note DROP COLUMN body")))
        self.assertFalse(self.flagged(migrations.RunSQL("UPDATE note SET body = ''")))
