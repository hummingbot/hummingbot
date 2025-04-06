import logging
from inspect import getmembers, isabstract, isclass
from pathlib import Path
from shutil import copyfile, move

import pandas as pd
from sqlalchemy.exc import SQLAlchemyError

from hummingbot.client.config.config_helpers import ClientConfigAdapter
from hummingbot.model.db_migration.base_transformation import DatabaseTransformation
from hummingbot.model.sql_connection_manager import SQLConnectionManager, SQLConnectionType


class Migrator:
    @classmethod
    def _get_transformations(cls):
        import hummingbot.model.db_migration.transformations as transformations
        return [o for _, o in getmembers(transformations,
                                         predicate=lambda c: isclass(c) and
                                         issubclass(c, DatabaseTransformation) and
                                         not isabstract(c))]

    def __init__(self):
        self.transformations = [t(self) for t in self._get_transformations()]

    def migrate_db_to_version(self, client_config_map: ClientConfigAdapter, db_handle, from_version, to_version):
        original_db_path = db_handle.db_path
        original_db_name = Path(original_db_path).stem
        backup_db_path = original_db_path + '.backup_' + pd.Timestamp.utcnow().strftime("%Y%m%d-%H%M%S")
        new_db_path = original_db_path + '.new'
        copyfile(original_db_path, new_db_path)
        copyfile(original_db_path, backup_db_path)

        db_handle.engine.dispose()
        new_db_handle = SQLConnectionManager(
            client_config_map, SQLConnectionType.TRADE_FILLS, new_db_path, original_db_name, True
        )

        relevant_transformations = [t for t in self.transformations
                                    if t.does_apply_to_version(from_version, to_version)]
        if relevant_transformations:
            logging.getLogger().info(
                f"Will run DB migration from {from_version} to {to_version}")

        migration_successful = False
        try:
            for transformation in sorted(relevant_transformations):
                logging.getLogger().info(f"Applying {transformation.name} to DB...")
                new_db_handle = transformation.apply(new_db_handle)
                logging.getLogger().info(f"DONE with {transformation.name}")
            migration_successful = True
        except SQLAlchemyError:
            logging.getLogger().error("Unexpected error while checking and upgrading the local database.",
                                      exc_info=True)
        finally:
            try:
                new_db_handle.engine.dispose()
                if migration_successful:
                    move(new_db_path, original_db_path)
                db_handle.__init__(SQLConnectionType.TRADE_FILLS, original_db_path, original_db_name, True)
            except Exception as e:
                logging.getLogger().error(f"Fatal error migrating DB {original_db_path}")
                raise e
        return migration_successful
