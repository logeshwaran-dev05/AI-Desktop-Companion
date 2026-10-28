"""
Application Catalogue Module for Windows Automation.

Maintains indexed application records and provides safe, disambiguated target resolution.
"""

import os
from typing import Dict, List, Optional
from windows_automation.schemas import ApplicationRecord, ResolutionResult
from windows_automation.discovery import normalize_app_name


class ApplicationCatalogue:
    """
    Indexed collection of discovered application records providing safe resolution.
    """

    def __init__(self, records: Optional[List[ApplicationRecord]] = None, include_builtins: bool = True):
        self._records_by_id: Dict[str, ApplicationRecord] = {}
        self._records_by_name: Dict[str, ApplicationRecord] = {}
        self._records_by_alias: Dict[str, List[ApplicationRecord]] = {}

        if include_builtins:
            from windows_automation.discovery import ApplicationDiscoverer
            builtins_map: Dict[str, ApplicationRecord] = {}
            ApplicationDiscoverer()._discover_builtins(builtins_map)
            for b_rec in builtins_map.values():
                self.add_record(b_rec)

        if records:
            for rec in records:
                self.add_record(rec)

    def add_record(self, record: ApplicationRecord):
        """Add or update an application record in the catalogue."""
        self._records_by_id[record.app_id] = record
        self._records_by_name[record.normalized_name] = record

        for alias in record.aliases:
            norm_alias = normalize_app_name(alias)
            if norm_alias not in self._records_by_alias:
                self._records_by_alias[norm_alias] = []
            if record not in self._records_by_alias[norm_alias]:
                self._records_by_alias[norm_alias].append(record)

    def get_by_id(self, app_id: str) -> Optional[ApplicationRecord]:
        """Direct lookup by stable application ID."""
        return self._records_by_id.get(app_id)

    def get_all(self) -> List[ApplicationRecord]:
        """Return all catalogue records sorted alphabetically."""
        return sorted(self._records_by_id.values(), key=lambda a: a.display_name.lower())

    def count(self) -> int:
        """Return total number of applications in catalogue."""
        return len(self._records_by_id)

    def resolve(self, query: str, verify_existence: bool = True) -> ResolutionResult:
        """
        Resolve an application name, alias, or identifier against catalogue records.
        Distinguishes unique resolution from ambiguous matches or missing entries.
        """
        if not query or not query.strip():
            return ResolutionResult(
                status="not_found",
                query=query or "",
                matched_record=None,
                candidates=[],
                reason="Search query cannot be empty.",
            )

        clean_query = query.strip()
        norm_query = normalize_app_name(clean_query)

        # 1. Exact match by app_id
        if clean_query in self._records_by_id:
            rec = self._records_by_id[clean_query]
            return self._validate_and_return_match(norm_query, rec, verify_existence=verify_existence)

        # 2. Exact match by normalized display name
        if norm_query in self._records_by_name:
            rec = self._records_by_name[norm_query]
            return self._validate_and_return_match(norm_query, rec, verify_existence=verify_existence)

        # 3. Exact alias match
        if norm_query in self._records_by_alias:
            matched_list = self._records_by_alias[norm_query]
            if len(matched_list) == 1:
                return self._validate_and_return_match(norm_query, matched_list[0], verify_existence=verify_existence)
            elif len(matched_list) > 1:
                return ResolutionResult(
                    status="ambiguous",
                    query=clean_query,
                    matched_record=None,
                    candidates=matched_list,
                    reason=f"Query '{clean_query}' matches multiple applications: {[m.display_name for m in matched_list]}",
                )

        # 4. Prefix or substring matching
        candidates = []
        for rec in self._records_by_id.values():
            if norm_query in rec.normalized_name:
                candidates.append(rec)
            else:
                for al in rec.aliases:
                    if norm_query in al:
                        if rec not in candidates:
                            candidates.append(rec)
                        break

        if len(candidates) == 1:
            return self._validate_and_return_match(norm_query, candidates[0], verify_existence=verify_existence)
        elif len(candidates) > 1:
            # Check if one candidate is an exact word prefix
            exact_prefixes = [c for c in candidates if c.normalized_name.startswith(norm_query)]
            if len(exact_prefixes) == 1:
                return self._validate_and_return_match(norm_query, exact_prefixes[0], verify_existence=verify_existence)

            return ResolutionResult(
                status="ambiguous",
                query=clean_query,
                matched_record=None,
                candidates=candidates,
                reason=f"Ambiguous query '{clean_query}' matched {len(candidates)} candidates.",
            )

        # 5. Not found
        return ResolutionResult(
            status="not_found",
            query=clean_query,
            matched_record=None,
            candidates=[],
            reason=f"No installed application found matching '{clean_query}'.",
        )

    def _validate_and_return_match(
        self,
        query: str,
        rec: ApplicationRecord,
        verify_existence: bool = True,
    ) -> ResolutionResult:
        """Validate target executable existence and return resolved outcome."""
        # For system built-ins like notepad.exe or calc.exe, verify executable
        exe_path = rec.executable_path
        if not exe_path:
            return ResolutionResult(
                status="unsupported",
                query=query,
                matched_record=rec,
                candidates=[rec],
                reason=f"Application '{rec.display_name}' has no defined executable target.",
            )

        # If it's a full path, check existence on disk if verify_existence is True
        if verify_existence and (":" in exe_path or "\\" in exe_path) and not os.path.exists(exe_path):
            rec.status = "target_missing"
            return ResolutionResult(
                status="unsupported",
                query=query,
                matched_record=rec,
                candidates=[rec],
                reason=f"Target executable does not exist at '{exe_path}'.",
            )

        rec.status = "available"
        return ResolutionResult(
            status="resolved",
            query=query,
            matched_record=rec,
            candidates=[rec],
            reason=None,
        )
