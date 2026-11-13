"""
Application Catalogue Module for Windows Automation.

Maintains indexed application records and provides advanced alias matching,
whitespace stripping, prefix resolution, and ambiguity detection.
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
            if not norm_alias:
                continue
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
        Handles case-insensitivity, extra spaces, partial names, and ambiguity.
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
            # Deduplicate by normalized name
            unique_matches = list({m.normalized_name: m for m in matched_list}.values())
            if len(unique_matches) == 1:
                return self._validate_and_return_match(norm_query, unique_matches[0], verify_existence=verify_existence)
            elif len(unique_matches) > 1:
                # Prefer exact normalized name match if present
                exact_name_match = [m for m in unique_matches if m.normalized_name == norm_query]
                if len(exact_name_match) == 1:
                    return self._validate_and_return_match(norm_query, exact_name_match[0], verify_existence=verify_existence)

                # Prefer candidate that starts with the query word (e.g. 'Calculator' for 'calc')
                starts_with_query = [m for m in unique_matches if m.normalized_name.startswith(norm_query) or m.display_name.lower().startswith(clean_query.lower())]
                if len(starts_with_query) == 1:
                    return self._validate_and_return_match(norm_query, starts_with_query[0], verify_existence=verify_existence)

                # Deduplicate candidates pointing to the same binary executable
                all_have_exe = all(bool(m.executable_path and m.executable_path.lower().endswith(".exe")) for m in unique_matches)
                unique_binaries = {
                    os.path.basename(m.executable_path).lower()
                    for m in unique_matches
                    if m.executable_path and os.path.basename(m.executable_path).lower().endswith(".exe")
                }
                if all_have_exe and len(unique_binaries) == 1:
                    preferred = [m for m in unique_matches if m.source in ("start_apps", "start_menu_user", "start_menu_all_users")]
                    return self._validate_and_return_match(norm_query, preferred[0] if preferred else unique_matches[0], verify_existence=verify_existence)

                return ResolutionResult(
                    status="ambiguous",
                    query=clean_query,
                    matched_record=None,
                    candidates=unique_matches,
                    reason=f"Query '{clean_query}' matches multiple applications: {[m.display_name for m in unique_matches]}",
                )

        # 4. Prefix or substring matching across names and aliases
        candidates: List[ApplicationRecord] = []
        for rec in self._records_by_id.values():
            if norm_query in rec.normalized_name:
                candidates.append(rec)
            else:
                for al in rec.aliases:
                    if norm_query in al:
                        if rec not in candidates:
                            candidates.append(rec)
                        break

        # Deduplicate candidates by normalized name
        candidates = list({c.normalized_name: c for c in candidates}.values())

        if len(candidates) == 1:
            return self._validate_and_return_match(norm_query, candidates[0], verify_existence=verify_existence)
        elif len(candidates) > 1:
            # Check if one candidate has an exact alias match
            exact_alias_match = [c for c in candidates if norm_query in [a.lower() for a in c.aliases]]
            if len(exact_alias_match) == 1:
                return self._validate_and_return_match(norm_query, exact_alias_match[0], verify_existence=verify_existence)

            # Check if one candidate is an exact word prefix
            exact_prefixes = [c for c in candidates if c.normalized_name.startswith(norm_query)]
            if len(exact_prefixes) == 1:
                return self._validate_and_return_match(norm_query, exact_prefixes[0], verify_existence=verify_existence)

            # Check if one candidate's display name starts with query
            display_prefixes = [c for c in candidates if c.display_name.lower().startswith(clean_query.lower())]
            if len(display_prefixes) == 1:
                return self._validate_and_return_match(norm_query, display_prefixes[0], verify_existence=verify_existence)

            # Deduplicate candidates pointing to the same binary executable
            all_have_exe = all(bool(c.executable_path and c.executable_path.lower().endswith(".exe")) for c in candidates)
            unique_binaries = {
                os.path.basename(c.executable_path).lower()
                for c in candidates
                if c.executable_path and os.path.basename(c.executable_path).lower().endswith(".exe")
            }
            if all_have_exe and len(unique_binaries) == 1:
                preferred = [c for c in candidates if c.source in ("start_apps", "start_menu_user", "start_menu_all_users")]
                return self._validate_and_return_match(norm_query, preferred[0] if preferred else candidates[0], verify_existence=verify_existence)

            # Exclude auxiliary troubleshooting shortcuts if a clean primary candidate exists
            clean_candidates = [
                c for c in candidates
                if not any(k in c.display_name.lower() for k in ("reset preferences", "cache files", "skinned", "safe mode", "uninstall"))
            ]
            if len(clean_candidates) == 1:
                return self._validate_and_return_match(norm_query, clean_candidates[0], verify_existence=verify_existence)

            return ResolutionResult(
                status="ambiguous",
                query=clean_query,
                matched_record=None,
                candidates=candidates,
                reason=f"Ambiguous query '{clean_query}' matched {len(candidates)} candidates: {[c.display_name for c in candidates]}",
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
        """Validate target executable or shortcut existence and return resolved outcome."""
        # Check shortcut path if application type is shortcut
        if rec.app_type == "shortcut" and rec.shortcut_path:
            if verify_existence and not os.path.exists(rec.shortcut_path):
                rec.status = "target_missing"
                return ResolutionResult(
                    status="unsupported",
                    query=query,
                    matched_record=rec,
                    candidates=[rec],
                    reason=f"Shortcut target does not exist at '{rec.shortcut_path}'.",
                )
            rec.status = "available"
            return ResolutionResult(
                status="resolved",
                query=query,
                matched_record=rec,
                candidates=[rec],
                reason=None,
            )

        # For packaged apps or shell apps folder, target is an AUMID or registered shell ID
        if rec.launch_method in ["appx_packaged", "shell_apps_folder"] or rec.app_type == "packaged_app":
            rec.status = "available"
            return ResolutionResult(
                status="resolved",
                query=query,
                matched_record=rec,
                candidates=[rec],
                reason=None,
            )

        exe_path = rec.executable_path
        if not exe_path:
            return ResolutionResult(
                status="unsupported",
                query=query,
                matched_record=rec,
                candidates=[rec],
                reason=f"Application '{rec.display_name}' has no defined executable or shortcut target.",
            )

        # If it's an absolute path, verify existence
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
