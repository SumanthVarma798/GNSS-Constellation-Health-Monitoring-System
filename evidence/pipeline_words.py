"""Plain and technical wording for each live-pipeline stage.

Each entry is keyed by the stage key from evidence/pipeline.py.
"""

PLAIN_STATES = {
    "running now": "working now",
    "done": "finished fine",
    "failed": "had a problem",
    "waiting": "waiting",
    "off": "switched off",
}

SETTING_SENTENCES = {
    "ACTIONS": "What each decision choice does to the pull request after the decision comment is written.",
    "ARCHIVE_OBJECTS_DIR": "Folder name inside the archive repository where raw copies are stored by fingerprint.",
    "ARCHIVE_RUNS_DIR": "Folder name inside the archive repository where run-log CSV files are kept.",
    "ARCHIVE_RUN_COLUMNS": "Exact column order used when writing each run-log line.",
    "ARCHIVE_VERSIONS_FILE": "CSV file name inside the archive repository that records every change (a changed copy or a page becoming gone).",
    "BACKOFF_FIRST": "How long a source is held off after its first refusal before it may be asked again.",
    "BACKOFF_LONGEST": "Maximum refusal back-off wait, even after repeated refusals.",
    "CHOICES": "Decision words shown to reviewers for approve, approve-after-changes, or reject.",
    "DECISION_MARKER": "HTML marker added to decision comments so outcomes can be counted later.",
    "DOWNLOAD_TRIES": "How many times one failed download is attempted in a single run.",
    "GROUPS": "Display groups and order used on the Approvals page.",
    "KINDS": "Maps each decision label kind to the group shown on the Approvals page.",
    "LABEL_PREFIX": "Prefix that marks pull-request labels as decision labels.",
    "MAX_COPY_BYTES": "Largest raw copy size accepted before a fetch is stopped.",
    "MERGE_METHOD": "GitHub merge method used when an approved pull request is merged.",
    "MIN_GAP_BETWEEN_DOWNLOADS": "Per-site minimum wait between two requests to the same site (a named host or any host under it).",
    "NEVER_FETCH": "Host-name fragments the archive fetcher refuses before any request, including redirects to them.",
    "REFUSAL_STATUSES": "HTTP statuses treated as refusals that trigger persistent back-off.",
    "REGISTRY_CONSTELLATIONS_FILE": "Registry file name that maps system letters to constellation names.",
    "REGISTRY_DASHBOARD_SATELLITES_FILE": "Registry file name listing satellites shown on the dashboard, in display order.",
    "REGISTRY_SATELLITES_FILE": "Registry table file name for core satellite identity rows.",
    "REGISTRY_SIGNAL_IDS_FILE": "Registry table file name for signal-ID history rows.",
    "REQUEST_TIMEOUT_SECONDS": "Per-request timeout for calls to outside servers.",
    "REQUIRED_CHECK": "Name of the GitHub check that must pass before merge approval can merge.",
    "TESTS_WORKFLOW": "Workflow file name treated as the tests-on-main source in the console.",
    "WAIT_BETWEEN_TRIES_SECONDS": "Base pause between download tries inside one run.",
    "WAIT_WARN_DAYS": "Days a waiting decision item may wait before it is shown as overdue (warning once it has waited longer than this).",
}

STAGES = {
    "archive_documents": {
        "plain_name": "Collect official documents",
        "what_happens": [
            "Once a day, a program downloads the official satellite metadata file.",
            "It saves a new dated copy only when that file changed.",
            "It writes one run-log line so people can see what happened.",
        ],
        "why_it_matters": "This file is the main reference for which satellite is which.",
        "technical": {
            "workflow_file": ".github/workflows/archive.yml",
            "workflow_job": "archive",
            "schedule_group": "documents",
            "commands": ["python scripts/archive_sources.py --archive archive --group documents"],
            "inputs": [
                "Group 'documents' in evidence/sources.py",
                "Source limits from evidence/settings.py",
            ],
            "outputs": [
                "Archive objects and versions in the private archive repository",
                "Run log line in archive/runs/archive.csv",
            ],
            "repositories": [
                "SumanthVarma798/GNSS-Constellation-Health-Monitoring-System",
                "SumanthVarma798/GNSS-Constellation-Health-Monitoring-System-archive",
            ],
            "settings": [
                "REQUEST_TIMEOUT_SECONDS",
                "DOWNLOAD_TRIES",
                "WAIT_BETWEEN_TRIES_SECONDS",
                "MIN_GAP_BETWEEN_DOWNLOADS",
                "MAX_COPY_BYTES",
            ],
            "settings_files": ["evidence/settings.py"],
            "paths": [
                ".github/workflows/archive.yml",
                "scripts/archive_sources.py",
                "evidence/settings.py",
                "evidence/sources.py",
            ],
            "limits": [
                "Scheduled runs can start late on GitHub Actions.",
                "A source can fail all retries and stop this stage with a failure result.",
            ],
        },
    },
    "archive_catalogues": {
        "plain_name": "Collect satellite catalogues",
        "what_happens": [
            "Once a day, a program downloads two public satellite catalogue files.",
            "It saves a new copy only when a downloaded file changed.",
            "It records the run outcome in the archive run log.",
        ],
        "why_it_matters": "These files add owner and status details used in checks.",
        "technical": {
            "workflow_file": ".github/workflows/archive.yml",
            "workflow_job": "archive",
            "schedule_group": "catalogues",
            "commands": ["python scripts/archive_sources.py --archive archive --group catalogues"],
            "inputs": [
                "Group 'catalogues' in evidence/sources.py",
                "Source limits from evidence/settings.py",
            ],
            "outputs": [
                "Archive objects and versions in the private archive repository",
                "Run log line in archive/runs/archive.csv",
            ],
            "repositories": [
                "SumanthVarma798/GNSS-Constellation-Health-Monitoring-System",
                "SumanthVarma798/GNSS-Constellation-Health-Monitoring-System-archive",
            ],
            "settings": [
                "DOWNLOAD_TRIES",
                "WAIT_BETWEEN_TRIES_SECONDS",
                "MIN_GAP_BETWEEN_DOWNLOADS",
                "MAX_COPY_BYTES",
            ],
            "settings_files": ["evidence/settings.py"],
            "paths": [
                ".github/workflows/archive.yml",
                "scripts/archive_sources.py",
                "evidence/settings.py",
                "evidence/sources.py",
            ],
            "limits": [
                "The catalogue can change layout or availability without notice.",
                "This run can finish late if earlier scheduled jobs are delayed.",
            ],
        },
    },
    "archive_orbital": {
        "plain_name": "Collect orbit data",
        "what_happens": [
            "Once a day, a program downloads GNSS orbit records from CelesTrak.",
            "It saves a new copy only when the data changed, then logs the run.",
            "For this source, the two-hour site gap means one try per run.",
        ],
        "why_it_matters": "These records are kept for archive history and later checks.",
        "technical": {
            "workflow_file": ".github/workflows/archive.yml",
            "workflow_job": "archive",
            "schedule_group": "orbital",
            "commands": ["python scripts/archive_sources.py --archive archive --group orbital"],
            "inputs": [
                "Group 'orbital' in evidence/sources.py",
                "Source limits from evidence/settings.py",
            ],
            "outputs": [
                "Archive objects and versions in the private archive repository",
                "Run log line in archive/runs/archive.csv",
            ],
            "repositories": [
                "SumanthVarma798/GNSS-Constellation-Health-Monitoring-System",
                "SumanthVarma798/GNSS-Constellation-Health-Monitoring-System-archive",
            ],
            "settings": [
                "REQUEST_TIMEOUT_SECONDS",
                "MIN_GAP_BETWEEN_DOWNLOADS",
            ],
            "settings_files": ["evidence/settings.py"],
            "paths": [
                ".github/workflows/archive.yml",
                "scripts/archive_sources.py",
                "evidence/settings.py",
                "evidence/sources.py",
            ],
            "limits": [
                "CelesTrak is rate-limited in settings to one request every 2 hours.",
                "If CelesTrak is down, the dashboard keeps its own held rows and bundled data files, not this private archive.",
            ],
        },
    },
    "archive_news": {
        "plain_name": "Collect news",
        "what_happens": [
            "Every three hours, a program visits news and official feed pages from the news list.",
            "It saves changed copies and records the full run result.",
            "A failed news source is recorded, but this stage fails only if the run breaks or every tried source fails.",
        ],
        "why_it_matters": "This keeps a dated record of reports that can support later human review.",
        "technical": {
            "workflow_file": ".github/workflows/archive.yml",
            "workflow_job": "archive",
            "schedule_group": "news",
            "commands": ["python scripts/archive_sources.py --archive archive --group news"],
            "inputs": [
                "Group 'news' in evidence/sources.py",
                "Candidate-source list in evidence/source_candidates.csv",
                "Source limits from evidence/settings.py",
            ],
            "outputs": [
                "Archive objects and versions in the private archive repository",
                "Run log line in archive/runs/archive.csv",
            ],
            "repositories": [
                "SumanthVarma798/GNSS-Constellation-Health-Monitoring-System",
                "SumanthVarma798/GNSS-Constellation-Health-Monitoring-System-archive",
            ],
            "settings": [
                "DOWNLOAD_TRIES",
                "WAIT_BETWEEN_TRIES_SECONDS",
                "REFUSAL_STATUSES",
                "BACKOFF_FIRST",
                "BACKOFF_LONGEST",
                "NEVER_FETCH",
            ],
            "settings_files": ["evidence/settings.py"],
            "paths": [
                ".github/workflows/archive.yml",
                "scripts/archive_sources.py",
                "evidence/settings.py",
                "evidence/sources.py",
                "evidence/source_candidates.csv",
            ],
            "limits": [
                "Some sources can repeatedly fail and remain visible as failed in the run result.",
                "Two blocked tracker hosts are never fetched by policy in settings.",
            ],
        },
    },
    "archive_social": {
        "plain_name": "Collect social posts",
        "what_happens": [
            "Once a day, a program reads social feeds and saves changed copies.",
            "It logs the run result even when nothing changed.",
            "These posts are kept mainly so their links can be checked later.",
        ],
        "why_it_matters": "This helps catch new links early while treating social posts as pointers, not final proof.",
        "technical": {
            "workflow_file": ".github/workflows/archive.yml",
            "workflow_job": "archive",
            "schedule_group": "social",
            "commands": ["python scripts/archive_sources.py --archive archive --group social"],
            "inputs": [
                "Group 'social' in evidence/sources.py",
                "Source limits and back-off rules from evidence/settings.py",
            ],
            "outputs": [
                "Archive objects and versions in the private archive repository",
                "Run log line in archive/runs/archive.csv",
            ],
            "repositories": [
                "SumanthVarma798/GNSS-Constellation-Health-Monitoring-System",
                "SumanthVarma798/GNSS-Constellation-Health-Monitoring-System-archive",
            ],
            "settings": [
                "REQUEST_TIMEOUT_SECONDS",
                "MIN_GAP_BETWEEN_DOWNLOADS",
                "REFUSAL_STATUSES",
                "BACKOFF_FIRST",
                "BACKOFF_LONGEST",
                "NEVER_FETCH",
            ],
            "settings_files": ["evidence/settings.py"],
            "paths": [
                ".github/workflows/archive.yml",
                "scripts/archive_sources.py",
                "evidence/settings.py",
                "evidence/sources.py",
            ],
            "limits": [
                "Social feeds can rate-limit quickly, so this stage runs once daily.",
                "Social posts cannot corroborate evidence in current confidence rules.",
            ],
        },
    },
    "archive": {
        "plain_name": "Keep a copy of each archived source",
        "what_happens": [
            "Changed copies are stored in a private history repository.",
            "Each copy is named by fingerprint, so unchanged files are not duplicated.",
            "Run logs are kept so every scheduled run can be traced later.",
        ],
        "why_it_matters": "The archive is the audit trail that lets people verify what was known and when.",
        "technical": {
            "workflow_file": ".github/workflows/archive.yml",
            "workflow_job": "archive",
            "schedule_group": "",
            "commands": ["python scripts/archive_sources.py --archive archive"],
            "inputs": [
                "Fetched source responses from each archive group run",
                "Archive layout settings in evidence/settings.py",
            ],
            "outputs": [
                "objects/ and versions.csv in the private archive repository",
                "runs/archive.csv in the private archive repository",
            ],
            "repositories": ["SumanthVarma798/GNSS-Constellation-Health-Monitoring-System-archive"],
            "settings": [
                "ARCHIVE_OBJECTS_DIR",
                "ARCHIVE_VERSIONS_FILE",
                "ARCHIVE_RUNS_DIR",
                "ARCHIVE_RUN_COLUMNS",
            ],
            "settings_files": ["evidence/settings.py"],
            "paths": [
                ".github/workflows/archive.yml",
                "scripts/archive_sources.py",
                "evidence/settings.py",
            ],
            "limits": [
                "Storage grows over time and is currently managed in git.",
                "Archive writes depend on the deploy key and GitHub push availability.",
            ],
        },
    },
    "registry_update": {
        "plain_name": "Rebuild the satellite list",
        "what_happens": [
            "Once a week, a program rebuilds satellite tables from the latest archived IGS file.",
            "If the tables changed, it opens or updates one GitHub proposal page (pull request).",
            "It runs the full test suite before opening or updating that proposal.",
        ],
        "why_it_matters": "This updates satellite identity data through review instead of direct edits to main.",
        "technical": {
            "workflow_file": ".github/workflows/registry-update.yml",
            "workflow_job": "propose",
            "schedule_group": "",
            "commands": [
                "python scripts/build_registry.py --archive archive --report \"$RUNNER_TEMP/registry-changes.md\"",
                "python -m pytest -q",
                "gh pr edit registry-update --add-label \"decision: registry update\" --body-file \"$RUNNER_TEMP/registry-changes.md\" (when an open PR already exists)",
                "gh pr create --base main --head registry-update --title \"Registry update from the IGS satellite metadata file\" --label \"decision: registry update\" --body-file \"$RUNNER_TEMP/registry-changes.md\" (when no open PR exists)",
            ],
            "inputs": [
                "Latest archived IGS metadata copy in the archive repository",
                "Current registry tables in registry/",
            ],
            "outputs": [
                "registry/satellites.csv and registry/signal_ids.csv",
                "Pull request from branch registry-update to main",
                "Run log line in archive/runs/registry-update.csv",
            ],
            "repositories": [
                "SumanthVarma798/GNSS-Constellation-Health-Monitoring-System",
                "SumanthVarma798/GNSS-Constellation-Health-Monitoring-System-archive",
            ],
            "settings": [
                "REGISTRY_SATELLITES_FILE",
                "REGISTRY_SIGNAL_IDS_FILE",
                "REGISTRY_CONSTELLATIONS_FILE",
            ],
            "settings_files": ["evidence/settings.py"],
            "paths": [
                ".github/workflows/registry-update.yml",
                "scripts/build_registry.py",
                "registry/satellites.csv",
                "registry/signal_ids.csv",
                "evidence/settings.py",
            ],
            "limits": [
                "If the IGS file layout changes, the build exits and no tables are written.",
                "A proposal is created only when registry/ actually changes.",
            ],
        },
    },
    "decision_waiting": {
        "plain_name": "A change waits for a person",
        "what_happens": [
            "A proposal page on GitHub is marked as waiting for a decision label.",
            "After a decision, it can stay open for requested edits, or later be merged or closed.",
            "The waiting list is shown on the Approvals page.",
        ],
        "why_it_matters": "A person checks each proposed data change before it moves forward.",
        "technical": {
            "workflow_file": "",
            "workflow_job": "",
            "schedule_group": "",
            "commands": [
                "Label-based queue in GitHub pull requests (decision: <kind>)",
            ],
            "inputs": [
                "Open pull requests in the main repository",
                "Decision labels with the configured prefix",
            ],
            "outputs": [
                "Queue of waiting items on console/approvals.py",
            ],
            "repositories": ["SumanthVarma798/GNSS-Constellation-Health-Monitoring-System"],
            "settings": [
                "LABEL_PREFIX",
                "KINDS",
                "GROUPS",
                "WAIT_WARN_DAYS",
            ],
            "settings_files": ["evidence/decision_settings.py"],
            "paths": [
                "evidence/decision_settings.py",
                "evidence/decisions.py",
                "console/approvals.py",
            ],
            "limits": [
                "Queue speed depends on human availability.",
                "Any new decision kind not in KINDS is grouped under Other kinds.",
            ],
        },
    },
    "decision_made": {
        "plain_name": "A person decides",
        "what_happens": [
            "A reviewer records one decision with a reason on the proposal page.",
            "The choice can approve, ask for changes, or reject.",
            "The decision stays attached to that proposal record.",
        ],
        "why_it_matters": "Every approved or rejected change has a human reason attached.",
        "technical": {
            "workflow_file": "",
            "workflow_job": "",
            "schedule_group": "",
            "commands": [
                "Decision action in console/approvals.py via evidence/decisions.py",
            ],
            "inputs": [
                "Selected waiting pull request",
                "Decision choice and required reason",
            ],
            "outputs": [
                "Decision comment marker and pull-request state update in GitHub",
            ],
            "repositories": ["SumanthVarma798/GNSS-Constellation-Health-Monitoring-System"],
            "settings": [
                "CHOICES",
                "ACTIONS",
                "DECISION_MARKER",
                "REQUIRED_CHECK",
                "MERGE_METHOD",
            ],
            "settings_files": ["evidence/decision_settings.py"],
            "paths": [
                "evidence/decision_settings.py",
                "evidence/decisions.py",
                "console/approvals.py",
            ],
            "limits": [
                "A missing reason blocks the decision action.",
                "Merge approval is gated by the configured required check.",
            ],
        },
    },
    "merged_main": {
        "plain_name": "The change goes live",
        "what_happens": [
            "After approval, the proposal is merged into main.",
            "A push to main starts the tests job for that merged commit.",
            "The merge event is visible in the proof feed.",
        ],
        "why_it_matters": "This is the handoff from reviewed proposal to the live branch history.",
        "technical": {
            "workflow_file": ".github/workflows/tests.yml",
            "workflow_job": "pytest",
            "schedule_group": "",
            "commands": ["python -m pytest -q"],
            "inputs": [
                "Merged commit on main",
                "Repository code and test dependencies",
            ],
            "outputs": [
                "GitHub check result on the merged commit",
                "Tests run link in GitHub Actions",
            ],
            "repositories": ["SumanthVarma798/GNSS-Constellation-Health-Monitoring-System"],
            "settings": [
                "REQUIRED_CHECK",
                "MERGE_METHOD",
                "TESTS_WORKFLOW",
            ],
            "settings_files": ["evidence/decision_settings.py", "evidence/console_settings.py"],
            "paths": [
                ".github/workflows/tests.yml",
                "evidence/decision_settings.py",
                "evidence/console_settings.py",
            ],
            "limits": [
                "If tests fail on main, the change is merged but flagged as failed.",
                "This stage has no cron and only advances on merge events.",
            ],
        },
    },
    "dashboard": {
        "plain_name": "The dashboard shows it",
        "what_happens": [
            "The merged changes are ready to appear in the dashboard once tests on main pass.",
            "The live pipeline tracks this step from tests on main run results.",
            "People can then see the updated state in the dashboard views.",
        ],
        "why_it_matters": "It confirms that a reviewed and tested change is ready for users.",
        "technical": {
            "workflow_file": ".github/workflows/tests.yml",
            "workflow_job": "pytest",
            "schedule_group": "",
            "commands": ["python -m pytest -q"],
            "inputs": [
                "Registry files in registry/",
                "Bundled orbit files in data/ plus live CelesTrak state",
            ],
            "outputs": [
                "Dashboard pages rendered from current repository data",
                "Tests-on-main proof events in the live pipeline",
            ],
            "repositories": ["SumanthVarma798/GNSS-Constellation-Health-Monitoring-System"],
            "settings": [
                "REGISTRY_DASHBOARD_SATELLITES_FILE",
                "TESTS_WORKFLOW",
            ],
            "settings_files": ["evidence/settings.py", "evidence/console_settings.py"],
            "paths": [
                "dashboard.py",
                "registry/dashboard_satellites.csv",
                "evidence/settings.py",
                "evidence/console_settings.py",
            ],
            "limits": [
                "If tests on main fail, this stage shows a failed state.",
                "Bundled orbit-data refresh workflow can be turned off independently.",
            ],
        },
    },
}
