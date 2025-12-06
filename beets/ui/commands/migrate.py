"""The 'migrate' command: migrate library data for format changes."""

from beets import logging, ui
from beets.autotag import correct_list_fields

# Global logger.
log = logging.getLogger("beets")


def migrate_genres(lib, pretend=False):
    """Migrate comma-separated genre strings to genres list.

    For users upgrading from previous versions, their genre field may
    contain comma-separated values (e.g., "Rock, Alternative, Indie").
    This command splits those values into the genres list, avoiding
    the need to reimport the entire library.
    """
    items = lib.items()
    migrated_count = 0
    total_items = 0

    ui.print_("Scanning library for items with comma-separated genres...")

    for item in items:
        total_items += 1
        genre_val = item.genre or ""
        genres_val = item.genres or []

        # Check if migration is needed
        needs_migration = False
        if not genres_val and genre_val:
            for separator in [", ", "; ", " / "]:
                if separator in genre_val:
                    split_genres = [
                        g.strip()
                        for g in genre_val.split(separator)
                        if g.strip()
                    ]
                    if len(split_genres) > 1:
                        needs_migration = True
                        break

        if needs_migration:
            migrated_count += 1
            old_genre = item.genre
            old_genres = item.genres or []

            if pretend:
                # Just show what would change
                ui.print_(
                    f"  Would migrate: {item.artist} - {item.title}\n"
                    f"    genre: {old_genre!r} -> {split_genres[0]!r}\n"
                    f"    genres: {old_genres!r} -> {split_genres!r}"
                )
            else:
                # Actually migrate
                correct_list_fields(item)
                item.store()
                log.debug(
                    "migrated: {} - {} ({} -> {})",
                    item.artist,
                    item.title,
                    old_genre,
                    item.genres,
                )

    # Show summary
    if pretend:
        ui.print_(
            f"\nWould migrate {migrated_count} of {total_items} items "
            f"(run without --pretend to apply changes)"
        )
    else:
        ui.print_(
            f"\nMigrated {migrated_count} of {total_items} items with "
            f"comma-separated genres"
        )


def migrate_func(lib, opts, args):
    """Handle the migrate command."""
    if not args or args[0] == "genres":
        migrate_genres(lib, pretend=opts.pretend)
    else:
        raise ui.UserError(f"unknown migration target: {args[0]}")


migrate_cmd = ui.Subcommand(
    "migrate", help="migrate library data for format changes"
)
migrate_cmd.parser.add_option(
    "-p",
    "--pretend",
    action="store_true",
    help="show what would be changed without applying",
)
migrate_cmd.parser.usage = "%prog migrate genres [options]"
migrate_cmd.func = migrate_func
