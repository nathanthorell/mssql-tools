import hashlib
from typing import Dict, Set

import pyodbc
from prettytable import PrettyTable

from utils.utils import Connection


def fetch_stored_procs(conn: pyodbc.Connection, schema_name: str) -> Dict[str, str]:
    query = f"""
    SELECT ROUTINE_NAME, ROUTINE_DEFINITION
    FROM INFORMATION_SCHEMA.ROUTINES
    WHERE ROUTINE_TYPE = 'PROCEDURE' AND ROUTINE_SCHEMA = '{schema_name}'
    """
    cursor = conn.cursor()
    result = {}
    try:
        cursor.execute(query)
        for row in cursor.fetchall():
            result[row[0]] = row[1]
        return result
    except Exception as e:
        print(f"Error fetching stored procedures for schema '{schema_name}': {e}")
        return {}
    finally:
        cursor.close()


def compare_proc_definitions(connections: Dict[str, Connection], schema_name: str) -> None:
    """
    Compare procedure definitions across all environments using checksums.
    Only compares procedures that exist in multiple environments.
    """
    proc_checksums = {}
    all_proc_names: Set[str] = set()

    # Fetch procedures and calculate checksums for each environment
    for env, connection in connections.items():
        conn = connection.connect()
        procs = fetch_stored_procs(conn, schema_name)
        all_proc_names.update(procs.keys())

        # Calculate checksums
        proc_checksums[env] = {
            proc_name: hashlib.md5(" ".join(definition.split()).encode("utf-8")).hexdigest()[-10:]
            for proc_name, definition in procs.items()
        }

    # Setup table for results
    checksum_table = PrettyTable()
    field_names = ["Procedure Name"] + list(connections.keys())
    checksum_table.field_names = field_names
    for field in field_names:
        checksum_table.align[field] = "l"
    checksum_table.max_width["Procedure Name"] = 60

    has_differences = False
    for proc_name in sorted(all_proc_names):
        # Get checksums for all environments
        checksums = [proc_checksums[env].get(proc_name, "N/A") for env in connections.keys()]

        # Check if there are differences
        valid_checksums = [cs for cs in checksums]
        if len(set(valid_checksums)) > 1:
            has_differences = True
            checksum_table.add_row([proc_name] + checksums)

    if has_differences:
        print(f"\nStored procs with Different Definitions in Schema '{schema_name}':\n")
        print(checksum_table)
    else:
        msg = f"\nNo definition differences found in schema '{schema_name}'"
        print(msg)
