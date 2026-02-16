from __future__ import annotations

from typing import TYPE_CHECKING

from beets import config, plugins

if TYPE_CHECKING:
    from .session import ImportSession
    from .tasks import ImportTask

def _apply_choice(session: ImportSession, task: ImportTask):
    """Apply the task's choice to the Album or Item it contains and add
    it to the library.
    """
    if task.skip:
        return

    # Change metadata.
    if task.apply:
        # Store original date values before applying metadata
        original_dates = {}
        for item in task.items:
            original_dates[item] = (
                getattr(item, "year", None),
                getattr(item, "month", None),
                getattr(item, "day", None),
            )

        # Apply metadata normally
        task.apply_metadata()

        # Safety check: prevent incomplete date overwrite
        for item in task.items:
            original_year, original_month, original_day = original_dates[item]

            new_year = getattr(item, "year", None)
            new_month = getattr(item, "month", None)
            new_day = getattr(item, "day", None)

            original_score = sum(
                [
                    1 if original_year else 0,
                    1 if original_month else 0,
                    1 if original_day else 0,
                ]
            )

            new_score = sum(
                [
                    1 if new_year else 0,
                    1 if new_month else 0,
                    1 if new_day else 0,
                ]
            )

            # Restore original date if new date is less complete
            if new_score < original_score:
                item.year = original_year
                item.month = original_month
                item.day = original_day

        plugins.send("import_task_apply", session=session, task=task)

    task.add(session.lib)

    # If ``set_fields`` is set, set those fields to the
    # configured values.
    # NOTE: This cannot be done before the ``task.add()`` call above,
    # because then the ``ImportTask`` won't have an `album` for which
    # it can set the fields.
    if config["import"]["set_fields"]:
        task.set_fields(session.lib)
